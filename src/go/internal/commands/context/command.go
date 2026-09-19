// Package contextcmd resolves code context and persists metadata through MCP.
package contextcmd

import (
	"context"
	"encoding/json"
	"flag"
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"time"

	"github.com/Soul-Brews-Studio/maw-cli/src/go/internal/command"
)

type plugin struct {
	config, project, file, symbol string
	timeout                       time.Duration
	serverLogs                    bool
}

func init() { command.Register(func() command.CommandPlugin { return &plugin{} }) }

func (*plugin) Metadata() command.Metadata {
	return command.Metadata{Name: "context", Summary: "Resolve code context and store an MCP trace", Usage: "maw context [--config FILE] [--project DIR] [--file PATH] [--symbol NAME] [--timeout 60s] [--server-logs] <query>"}
}

func (p *plugin) BindFlags(flags *flag.FlagSet) {
	config := os.Getenv("MAW_MCP_CONFIG")
	if config == "" {
		if home, err := os.UserHomeDir(); err == nil {
			config = filepath.Join(home, ".config", "maw", "mcp.json")
		}
	}
	flags.StringVar(&p.config, "config", config, "trusted local MCP command configuration")
	flags.StringVar(&p.project, "project", ".", "source project directory")
	flags.StringVar(&p.file, "file", "", "project-relative source file for Serena overview")
	flags.StringVar(&p.symbol, "symbol", "", "Serena symbol name (optionally scoped by --file)")
	flags.DurationVar(&p.timeout, "timeout", time.Minute, "deadline for the complete resolution")
	flags.BoolVar(&p.serverLogs, "server-logs", false, "forward server diagnostics to stderr")
}

func (p *plugin) Run(ctx context.Context, invocation *command.Invocation) int {
	query := strings.Join(invocation.Args, " ")
	if query == "" {
		query = p.symbol
	}
	if query == "" {
		query = p.file
	}
	if query == "" || p.timeout <= 0 || p.timeout > 10*time.Minute {
		return invocation.Fail("context requires a query/file/symbol and a timeout between 0 and 10m")
	}
	project, err := sourcePath(p.project, p.file)
	if err != nil {
		return invocation.Fail(err.Error())
	}
	config, err := loadConfig(p.config)
	if err != nil {
		fmt.Fprintln(invocation.Stderr, "maw: context:", err)
		return 1
	}
	ctx, cancel := context.WithTimeout(ctx, p.timeout)
	defer cancel()
	result, err := p.resolve(ctx, invocation, config, project, query)
	if err != nil {
		fmt.Fprintln(invocation.Stderr, "maw: context:", err)
		return 1
	}
	encoder := json.NewEncoder(invocation.Stdout)
	encoder.SetIndent("", "  ")
	if err := encoder.Encode(result); err != nil {
		fmt.Fprintln(invocation.Stderr, "maw: context output:", err)
		return 1
	}
	return 0
}
