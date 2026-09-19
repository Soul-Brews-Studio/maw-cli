// Package indexcmd builds a bounded local index of normalized MCP context JSONL.
package indexcmd

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"flag"
	"fmt"
	"hash/fnv"
	"io"
	"os"
	"sort"
	"strconv"
	"strings"
	"unicode/utf8"

	"github.com/Soul-Brews-Studio/maw-herdr/src/go/internal/command"
)

const maxBytes = 64 * 1024 * 1024

type plugin struct{}

func init() { command.Register(func() command.CommandPlugin { return &plugin{} }) }
func (*plugin) Metadata() command.Metadata {
	return command.Metadata{Name: "index", Summary: "Index normalized MCP context JSONL", Usage: "maw index FILE|-"}
}
func (*plugin) BindFlags(*flag.FlagSet) {}

func (*plugin) Run(ctx context.Context, invocation *command.Invocation) int {
	if len(invocation.Args) != 1 {
		return invocation.Fail("usage: maw index FILE|-")
	}
	var input io.Reader = invocation.Stdin
	if invocation.Args[0] != "-" {
		file, err := os.Open(invocation.Args[0])
		if err != nil {
			fmt.Fprintln(invocation.Stderr, "maw: index:", err)
			return 1
		}
		defer file.Close()
		input = file
	}
	type readResult struct {
		data []byte
		err  error
	}
	completed := make(chan readResult, 1)
	go func() { data, err := io.ReadAll(io.LimitReader(input, maxBytes+1)); completed <- readResult{data, err} }()
	var data []byte
	var err error
	select {
	case result := <-completed:
		data, err = result.data, result.err
	case <-ctx.Done():
		// The CLI owns its input stream; closing it also releases a blocked read.
		if closer, ok := input.(io.Closer); ok {
			_ = closer.Close()
		}
		err = ctx.Err()
	}
	if err == nil && len(data) > maxBytes {
		err = errors.New("input exceeds 64 MiB")
	}
	var result map[string]any
	if err == nil {
		result, err = build(ctx, data)
	}
	if err == nil {
		err = json.NewEncoder(invocation.Stdout).Encode(result)
	}
	if err != nil {
		fmt.Fprintln(invocation.Stderr, "maw: index:", err)
		return 1
	}
	return 0
}

// encoding/json accepts lone surrogate escapes by replacing them. Reject those
// explicitly so every port accepts the same Unicode scalar-value input domain.
func validUnicode(data []byte) bool {
	for i := 0; i < len(data); i++ {
		if data[i] != '\\' {
			continue
		}
		i++
		if i >= len(data) || data[i] != 'u' {
			continue
		}
		if i+4 >= len(data) {
			return false
		}
		value, err := strconv.ParseUint(string(data[i+1:i+5]), 16, 16)
		if err != nil {
			return false
		}
		i += 4
		if value >= 0xdc00 && value <= 0xdfff {
			return false
		}
		if value < 0xd800 || value > 0xdbff {
			continue
		}
		if i+6 >= len(data) || data[i+1] != '\\' || data[i+2] != 'u' {
			return false
		}
		low, err := strconv.ParseUint(string(data[i+3:i+7]), 16, 16)
		if err != nil || low < 0xdc00 || low > 0xdfff {
			return false
		}
		i += 6
	}
	return true
}

// Full-input buffering and real postings storage are intentional for this prototype.
func build(ctx context.Context, data []byte) (map[string]any, error) {
	if !utf8.Valid(data) {
		return nil, errors.New("invalid UTF-8")
	}
	terms := map[string][]int{}
	symbols := map[string]struct{}{}
	records, textBytes, postingCount := 0, 0, 0
	for lineNumber, line := range bytes.Split(data, []byte{'\n'}) {
		if err := ctx.Err(); err != nil {
			return nil, err
		}
		if len(bytes.Trim(line, " \t\r")) == 0 {
			continue
		}
		var record map[string]any
		if !validUnicode(line) || json.Unmarshal(line, &record) != nil {
			return nil, fmt.Errorf("line %d: invalid JSON/Unicode", lineNumber+1)
		}
		result, _ := record["result"].(map[string]any)
		content, _ := result["structuredContent"].(map[string]any)
		file, fileOK := content["file"].(string)
		symbol, symbolOK := content["symbol"].(string)
		text, textOK := content["text"].(string)
		if record["jsonrpc"] != "2.0" || !fileOK || !symbolOK || !textOK || file == "" || symbol == "" || strings.ContainsRune(file, 0) || strings.ContainsRune(symbol, 0) {
			return nil, fmt.Errorf("line %d: invalid context result", lineNumber+1)
		}
		symbols[file+"\x00"+symbol] = struct{}{}
		textBytes += len(text)
		unique := map[string]struct{}{}
		for _, term := range strings.FieldsFunc(text, func(r rune) bool {
			return !(r >= 'A' && r <= 'Z' || r >= 'a' && r <= 'z' || r >= '0' && r <= '9' || r == '_')
		}) {
			unique[strings.ToLower(term)] = struct{}{}
		}
		for term := range unique {
			terms[term] = append(terms[term], records)
			postingCount++
		}
		records++
	}
	keys := make([]string, 0, len(terms))
	for term := range terms {
		keys = append(keys, term)
	}
	sort.Strings(keys)
	checksum := fnv.New64a()
	for _, term := range keys {
		fmt.Fprintf(checksum, "%s:%d\n", term, len(terms[term]))
	}
	return map[string]any{"records": records, "input_bytes": len(data), "text_bytes": textBytes, "unique_symbols": len(symbols), "unique_terms": len(terms), "postings": postingCount, "checksum": fmt.Sprintf("%016x", checksum.Sum64())}, nil
}
