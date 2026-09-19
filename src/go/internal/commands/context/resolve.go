package contextcmd

import (
	"context"
	"crypto/rand"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"os/exec"
	"strings"
	"time"

	"github.com/Soul-Brews-Studio/maw-herdr/src/go/internal/command"
	"github.com/Soul-Brews-Studio/maw-herdr/src/go/internal/mcp"
)

type resolution struct {
	Provider string          `json:"provider"`
	Tool     string          `json:"tool"`
	Trace    string          `json:"trace_memory"`
	Result   json.RawMessage `json:"result"`
}

type output struct {
	Project     string       `json:"project"`
	Resolutions []resolution `json:"resolutions"`
}

func requireTools(ctx context.Context, client *mcp.Client, names ...string) error {
	tools, err := client.Tools(ctx)
	if err != nil {
		return err
	}
	for _, name := range names {
		found := false
		for _, tool := range tools {
			if tool.Name == name {
				found = true
				break
			}
		}
		if !found {
			return fmt.Errorf("MCP server does not advertise required tool %q", name)
		}
	}
	return nil
}

func (p *plugin) resolve(ctx context.Context, invocation *command.Invocation, config configuration, project, query string) (_ output, failure error) {
	diagnostics := io.Discard
	if p.serverLogs {
		diagnostics = invocation.Stderr
	}
	config.Serena.Dir, config.CodeGraph.Dir = project, project
	if config.CodeGraph.Env == nil {
		config.CodeGraph.Env = map[string]string{}
	}
	config.CodeGraph.Env["DO_NOT_TRACK"], config.CodeGraph.Env["CODEGRAPH_TELEMETRY"] = "1", "0"
	serena, err := mcp.Start(ctx, config.Serena, diagnostics)
	if err != nil {
		return output{}, fmt.Errorf("Serena: %w", err)
	}
	defer func() { failure = errors.Join(failure, serena.Close()) }()
	if err := requireTools(ctx, serena, "initial_instructions", "activate_project", "write_memory"); err != nil {
		return output{}, err
	}
	if _, err := serena.CallTool(ctx, "initial_instructions", map[string]any{}); err != nil {
		return output{}, err
	}
	if _, err := serena.CallTool(ctx, "activate_project", map[string]string{"project": project}); err != nil {
		return output{}, err
	}
	graph, err := mcp.Start(ctx, config.CodeGraph, diagnostics)
	if err != nil {
		return output{}, fmt.Errorf("CodeGraph: %w", err)
	}
	defer func() { failure = errors.Join(failure, graph.Close()) }()
	if err := requireTools(ctx, graph, "codegraph_explore"); err != nil {
		return output{}, err
	}
	revision := "unavailable"
	if commit, err := exec.CommandContext(ctx, "git", "-C", project, "rev-parse", "HEAD").Output(); err == nil {
		revision = strings.TrimSpace(string(commit))
	}
	result := output{Project: project}
	resolve := func(client *mcp.Client, provider, tool string, args any) error {
		started := time.Now()
		value, err := client.CallTool(ctx, tool, args)
		if err != nil {
			return fmt.Errorf("%s %s: %w", provider, tool, err)
		}
		identifier := make([]byte, 12)
		if _, err := rand.Read(identifier); err != nil {
			return err
		}
		name := "learning/traces/" + started.UTC().Format("2006-01-02") + "/" + hex.EncodeToString(identifier)
		queryHash, resultHash := sha256.Sum256([]byte(query)), sha256.Sum256(value)
		record := map[string]any{
			"schema": "maw.context-trace.v1", "id": name, "timestamp": started.UTC().Format(time.RFC3339Nano),
			"project": project, "revision": revision, "provider": provider, "tool": tool,
			"query_sha256": hex.EncodeToString(queryHash[:]), "result_sha256": hex.EncodeToString(resultHash[:]),
			"result_bytes": len(value), "elapsed_ms": float64(time.Since(started).Microseconds()) / 1000,
			"file": p.file, "symbol": p.symbol, "client_version": invocation.Version,
		}
		content, err := json.MarshalIndent(record, "", "  ")
		if err != nil {
			return err
		}
		if _, err := serena.CallTool(ctx, "write_memory", map[string]string{"memory_name": name, "content": string(content)}); err != nil {
			return fmt.Errorf("resolved %s but MCP trace persistence failed: %w", tool, err)
		}
		result.Resolutions = append(result.Resolutions, resolution{provider, tool, name, value})
		return nil
	}
	if err := resolve(graph, "codegraph", "codegraph_explore", map[string]any{"projectPath": project, "query": query, "maxFiles": 4}); err != nil {
		return output{}, err
	}
	if p.symbol != "" {
		if err := requireTools(ctx, serena, "find_symbol"); err != nil {
			return output{}, err
		}
		if err := resolve(serena, "serena", "find_symbol", map[string]any{"name_path_pattern": p.symbol, "relative_path": p.file, "include_body": true}); err != nil {
			return output{}, err
		}
	} else if p.file != "" {
		if err := requireTools(ctx, serena, "get_symbols_overview"); err != nil {
			return output{}, err
		}
		if err := resolve(serena, "serena", "get_symbols_overview", map[string]string{"relative_path": p.file}); err != nil {
			return output{}, err
		}
	}
	return result, nil
}
