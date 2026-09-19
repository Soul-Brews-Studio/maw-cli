// Package mcp provides a serial, newline-delimited MCP stdio client.
package mcp

import (
	"bufio"
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"os"
	"os/exec"
	"strconv"
	"strings"
	"sync"
	"time"
	"unicode/utf8"
)

type ServerConfig struct {
	Command string            `json:"command"`
	Args    []string          `json:"args"`
	Env     map[string]string `json:"env,omitempty"`
	Dir     string            `json:"cwd,omitempty"`
}

type Tool struct {
	Name        string          `json:"name"`
	InputSchema json.RawMessage `json:"inputSchema"`
}

type message struct {
	JSONRPC string          `json:"jsonrpc"`
	ID      json.RawMessage `json:"id,omitempty"`
	Method  string          `json:"method,omitempty"`
	Result  json.RawMessage `json:"result,omitempty"`
	Error   json.RawMessage `json:"error,omitempty"`
}

type received struct {
	message message
	err     error
}

type Client struct {
	cmd       *exec.Cmd
	stdin     io.WriteCloser
	stdout    io.ReadCloser
	incoming  chan received
	stopped   chan struct{}
	waited    chan error
	mu        sync.Mutex
	nextID    uint64
	closeOnce sync.Once
	closeErr  error
}

// Start starts only the configured process and completes the legacy MCP handshake.
func Start(ctx context.Context, cfg ServerConfig, stderr io.Writer) (*Client, error) {
	if err := ctx.Err(); err != nil {
		return nil, err
	}
	if cfg.Command == "" {
		return nil, errors.New("MCP server command is empty")
	}
	cmd := exec.Command(cfg.Command, cfg.Args...)
	cmd.Dir = cfg.Dir
	cmd.Env = os.Environ()
	for key, value := range cfg.Env {
		cmd.Env = append(cmd.Env, key+"="+value)
	}
	cmd.Stderr = stderr
	// Bound Wait even if a descendant retains the forwarded stderr pipe.
	cmd.WaitDelay = 250 * time.Millisecond
	stdin, err := cmd.StdinPipe()
	if err != nil {
		return nil, err
	}
	// Own the read end so Cmd.Wait cannot close it before buffered responses
	// have been consumed when a server exits immediately after writing.
	stdout, output, err := os.Pipe()
	if err != nil {
		_ = stdin.Close()
		return nil, err
	}
	cmd.Stdout = output
	if err := cmd.Start(); err != nil {
		_ = stdin.Close()
		_ = stdout.Close()
		_ = output.Close()
		return nil, err
	}
	_ = output.Close()
	c := &Client{cmd: cmd, stdin: stdin, stdout: stdout, incoming: make(chan received, 1), stopped: make(chan struct{}), waited: make(chan error, 1)}
	go func() { c.waited <- cmd.Wait() }()
	go c.read()
	result, err := c.request(ctx, "initialize", map[string]any{
		"protocolVersion": "2025-11-25", "capabilities": map[string]any{},
		"clientInfo": map[string]string{"name": "maw", "version": "dev"},
	})
	if err != nil {
		_ = c.Close()
		return nil, err
	}
	var initialized struct {
		ProtocolVersion string                     `json:"protocolVersion"`
		Capabilities    map[string]json.RawMessage `json:"capabilities"`
	}
	if err := json.Unmarshal(result, &initialized); err != nil {
		_ = c.Close()
		return nil, fmt.Errorf("MCP initialize result: %w", err)
	}
	switch initialized.ProtocolVersion {
	case "2025-11-25", "2025-06-18", "2025-03-26", "2024-11-05":
	default:
		_ = c.Close()
		return nil, fmt.Errorf("unsupported MCP protocol %q", initialized.ProtocolVersion)
	}
	tools := bytes.TrimSpace(initialized.Capabilities["tools"])
	if len(tools) == 0 || tools[0] != '{' {
		_ = c.Close()
		return nil, errors.New("MCP server does not advertise tools capability")
	}
	if err := c.write(ctx, map[string]any{"jsonrpc": "2.0", "method": "notifications/initialized"}); err != nil {
		_ = c.Close()
		return nil, err
	}
	return c, nil
}

func (c *Client) read() {
	scanner := bufio.NewScanner(c.stdout)
	scanner.Buffer(make([]byte, 64*1024), 32*1024*1024)
	for scanner.Scan() {
		var msg message
		err := json.Unmarshal(scanner.Bytes(), &msg)
		if !utf8.Valid(scanner.Bytes()) {
			err = errors.New("MCP transport invalid UTF-8")
		}
		if err == nil && msg.JSONRPC != "2.0" {
			err = errors.New("invalid JSON-RPC version")
		}
		if err == nil && msg.Method == "" && (len(msg.ID) == 0 || (len(msg.Result) == 0) == (len(msg.Error) == 0)) {
			err = errors.New("invalid JSON-RPC response")
		}
		if err == nil && len(msg.ID) != 0 {
			var id any
			decoder := json.NewDecoder(bytes.NewReader(msg.ID))
			decoder.UseNumber()
			if decoder.Decode(&id) != nil {
				err = errors.New("invalid JSON-RPC ID")
			} else {
				switch id.(type) {
				case string, json.Number:
				default:
					err = errors.New("invalid JSON-RPC ID type")
				}
			}
		}
		if err == nil && msg.Method != "" && (len(msg.Result) != 0 || len(msg.Error) != 0) {
			err = errors.New("invalid JSON-RPC request")
		}
		select {
		case c.incoming <- received{msg, err}:
		case <-c.stopped:
			return
		}
		if err != nil {
			return
		}
	}
	err := scanner.Err()
	if err == nil {
		err = io.EOF
	}
	select {
	case c.incoming <- received{err: err}:
	case <-c.stopped:
	}
}

func (c *Client) write(ctx context.Context, value any) error {
	data, err := json.Marshal(value)
	if err != nil {
		return err
	}
	data = append(data, '\n')
	done := make(chan error, 1)
	go func() { _, err := c.stdin.Write(data); done <- err }()
	select {
	case err := <-done:
		return err
	case <-ctx.Done():
		return ctx.Err()
	case <-c.stopped:
		return errors.New("MCP client closed")
	}
}

func (c *Client) request(ctx context.Context, method string, params any) (json.RawMessage, error) {
	c.mu.Lock()
	defer c.mu.Unlock()
	if err := ctx.Err(); err != nil {
		return nil, err
	}
	c.nextID++
	// String IDs avoid number precision/coercion and are unique for this session.
	id := strconv.FormatUint(c.nextID, 10)
	err := c.write(ctx, map[string]any{"jsonrpc": "2.0", "id": id, "method": method, "params": params})
	if err != nil {
		_ = c.Close()
		return nil, err
	}
	for {
		select {
		case <-ctx.Done():
			if method != "initialize" {
				cancelCtx, cancel := context.WithTimeout(context.Background(), 50*time.Millisecond)
				_ = c.write(cancelCtx, map[string]any{"jsonrpc": "2.0", "method": "notifications/cancelled", "params": map[string]any{"requestId": id, "reason": "request context cancelled"}})
				cancel()
			}
			_ = c.Close()
			return nil, ctx.Err()
		case <-c.stopped:
			return nil, errors.New("MCP client closed")
		case got := <-c.incoming:
			if got.err != nil {
				_ = c.Close()
				return nil, fmt.Errorf("MCP transport: %w", got.err)
			}
			msg := got.message
			if msg.Method != "" {
				if len(msg.ID) == 0 {
					continue
				}
				response := map[string]any{"jsonrpc": "2.0", "id": msg.ID}
				if msg.Method == "ping" {
					response["result"] = map[string]any{}
				} else {
					response["error"] = map[string]any{"code": -32601, "message": "Method not supported"}
				}
				if err := c.write(ctx, response); err != nil {
					_ = c.Close()
					return nil, err
				}
				continue
			}
			var responseID string
			if json.Unmarshal(msg.ID, &responseID) != nil || responseID != id {
				_ = c.Close()
				return nil, errors.New("MCP response ID mismatch")
			}
			if len(msg.Error) != 0 {
				return nil, fmt.Errorf("MCP %s JSON-RPC error: %s", method, msg.Error)
			}
			return msg.Result, nil
		}
	}
}

// Tools follows pagination, rejecting repeated cursors and excessive page counts.
func (c *Client) Tools(ctx context.Context) ([]Tool, error) {
	var tools []Tool
	params := map[string]any{}
	seen := map[string]bool{}
	for page := 0; page < 1000; page++ {
		result, err := c.request(ctx, "tools/list", params)
		if err != nil {
			return nil, err
		}
		var list struct {
			Tools      []Tool `json:"tools"`
			NextCursor string `json:"nextCursor"`
		}
		if err := json.Unmarshal(result, &list); err != nil {
			return nil, fmt.Errorf("MCP tools/list result: %w", err)
		}
		if list.Tools == nil {
			return nil, errors.New("MCP tools/list missing tools array")
		}
		for _, tool := range list.Tools {
			schema := bytes.TrimSpace(tool.InputSchema)
			if tool.Name == "" || len(schema) == 0 || schema[0] != '{' {
				return nil, errors.New("MCP tools/list invalid tool descriptor")
			}
		}
		tools = append(tools, list.Tools...)
		if list.NextCursor == "" {
			return tools, nil
		}
		if seen[list.NextCursor] {
			return nil, errors.New("MCP tools/list repeated cursor")
		}
		seen[list.NextCursor] = true
		params["cursor"] = list.NextCursor
	}
	return nil, errors.New("MCP tools/list exceeded page limit")
}

// CallTool returns the complete result, including content and structuredContent.
func (c *Client) CallTool(ctx context.Context, name string, args any) (json.RawMessage, error) {
	if args == nil {
		args = map[string]any{}
	}
	result, err := c.request(ctx, "tools/call", map[string]any{"name": name, "arguments": args})
	if err != nil {
		return result, err
	}
	if len(bytes.TrimSpace(result)) == 0 || bytes.TrimSpace(result)[0] != '{' {
		return result, errors.New("MCP tools/call result must be an object")
	}
	var status struct {
		Content json.RawMessage `json:"content"`
		IsError json.RawMessage `json:"isError"`
	}
	if err := json.Unmarshal(result, &status); err != nil {
		return result, fmt.Errorf("MCP tools/call result: %w", err)
	}
	var blocks []json.RawMessage
	if len(bytes.TrimSpace(status.Content)) == 0 || bytes.TrimSpace(status.Content)[0] != '[' || json.Unmarshal(status.Content, &blocks) != nil {
		return result, errors.New("MCP tools/call result requires content array")
	}
	content := make([]map[string]json.RawMessage, 0, len(blocks))
	for _, block := range blocks {
		var item map[string]json.RawMessage
		if json.Unmarshal(block, &item) != nil || item == nil {
			return result, errors.New("MCP invalid content block")
		}
		var kind string
		if json.Unmarshal(item["type"], &kind) != nil || kind == "" {
			return result, errors.New("MCP content block requires type")
		}
		fields := []string{}
		switch kind {
		case "text":
			fields = []string{"text"}
		case "image", "audio":
			fields = []string{"data", "mimeType"}
		case "resource_link":
			fields = []string{"name", "uri"}
		case "resource":
			var resource map[string]json.RawMessage
			if json.Unmarshal(item["resource"], &resource) != nil || resource == nil || !stringField(resource, "uri") || !(stringField(resource, "text") || stringField(resource, "blob")) {
				return result, errors.New("MCP invalid embedded resource")
			}
		default:
			return result, fmt.Errorf("MCP unsupported content type %q", kind)
		}
		for _, field := range fields {
			if !stringField(item, field) {
				return result, fmt.Errorf("MCP %s content requires string %s", kind, field)
			}
		}
		content = append(content, item)
	}
	isError := false
	if len(status.IsError) > 0 {
		if string(status.IsError) != "true" && string(status.IsError) != "false" {
			return result, errors.New("MCP isError must be boolean")
		}
		isError = string(status.IsError) == "true"
	}
	if isError {
		detail := ""
		for _, item := range content {
			if string(item["type"]) == `"text"` {
				_ = json.Unmarshal(item["text"], &detail)
				break
			}
		}
		// Diagnostic text is untrusted; bound it and escape terminal/control bytes.
		if len(detail) > 512 {
			detail = detail[:512] + "…"
		}
		if detail != "" {
			return result, fmt.Errorf("MCP tool %s reported isError=true: %s", name, strconv.Quote(strings.ToValidUTF8(detail, "�")))
		}
		return result, fmt.Errorf("MCP tool %s reported isError=true", name)
	}
	return result, nil
}

func stringField(object map[string]json.RawMessage, name string) bool {
	var value *string
	return json.Unmarshal(object[name], &value) == nil && value != nil
}

// Close closes stdin then allows up to two seconds for server/LSP cleanup before
// killing only the owned server process. Forced/nonzero exits remain errors.
// Descendant processes are not managed; no protocol shutdown method is sent.
func (c *Client) Close() error {
	c.closeOnce.Do(func() {
		close(c.stopped)
		_ = c.stdin.Close()
		select {
		case c.closeErr = <-c.waited:
		case <-time.After(2 * time.Second):
			killErr := c.cmd.Process.Kill()
			select {
			case c.closeErr = <-c.waited:
			case <-time.After(500 * time.Millisecond):
				c.closeErr = errors.New("MCP server did not exit after kill")
			}
			if killErr != nil && !errors.Is(killErr, os.ErrProcessDone) {
				c.closeErr = errors.Join(c.closeErr, killErr)
			}
		}
		_ = c.stdout.Close()
	})
	return c.closeErr
}
