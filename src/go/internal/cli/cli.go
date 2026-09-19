// Package cli dispatches registered built-ins and executable plugins.
package cli

import (
	"context"
	"flag"
	"fmt"
	"io"
	"sort"

	"github.com/Soul-Brews-Studio/maw-herdr/src/go/internal/command"
	_ "github.com/Soul-Brews-Studio/maw-herdr/src/go/internal/commands"
)

// Run executes one command. External plugin arguments are never parsed.
func Run(ctx context.Context, args []string, stdin io.Reader, stdout, stderr io.Writer, version string) int {
	factories := command.Factories()
	metadata := map[string]command.Metadata{}
	for name, factory := range factories {
		metadata[name] = factory().Metadata()
	}
	for name, path := range discover() {
		if _, exists := metadata[name]; !exists {
			metadata[name] = command.Metadata{Name: name, Summary: "External plugin", Path: path}
		}
	}
	var catalog []command.Metadata
	for _, meta := range metadata {
		catalog = append(catalog, meta)
	}
	sort.Slice(catalog, func(i, j int) bool { return catalog[i].Name < catalog[j].Name })
	base := command.Invocation{Stdin: stdin, Stdout: stdout, Stderr: stderr, Version: version, Commands: catalog}
	base.Execute = func(ctx context.Context, name string, args []string) int {
		meta, exists := metadata[name]
		if !exists {
			return base.Fail(fmt.Sprintf("unknown command %q; run 'maw help'", name))
		}
		if meta.Path != "" {
			return execute(ctx, meta.Path, args, stdin, stdout, stderr)
		}
		if len(args) == 1 && (args[0] == "-h" || args[0] == "--help") {
			return base.Execute(ctx, "help", []string{name})
		}
		plugin := factories[name]()
		flags := flag.NewFlagSet(name, flag.ContinueOnError)
		flags.SetOutput(io.Discard)
		plugin.BindFlags(flags)
		invocation := base
		invocation.Args = args
		// Flagless commands own their positional arguments, including literal --.
		hasFlags := false
		flags.VisitAll(func(*flag.Flag) { hasFlags = true })
		if hasFlags {
			if err := flags.Parse(args); err != nil {
				if err == flag.ErrHelp {
					return base.Execute(ctx, "help", []string{name})
				}
				return base.Fail("usage: " + meta.Usage)
			}
			invocation.Args = flags.Args()
		}
		return plugin.Run(ctx, &invocation)
	}
	if len(args) == 0 {
		return base.Execute(ctx, "help", nil)
	}
	name := args[0]
	if (name == "-h" || name == "--help" || name == "-v" || name == "--version") && len(args) != 1 {
		return base.Fail("global help/version flags do not accept arguments")
	}
	switch name {
	case "-h", "--help":
		name = "help"
	case "-v", "--version":
		name = "version"
	}
	return base.Execute(ctx, name, args[1:])
}
