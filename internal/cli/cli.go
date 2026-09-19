// Package cli implements maw's small command registry and executable plugin host.
package cli

import (
	"context"
	"fmt"
	"io"
	"sort"
)

type command struct {
	name, summary, usage, path string
	run                        func([]string) int
}

type registry map[string]command

func (r registry) sorted() []command {
	commands := make([]command, 0, len(r))
	for _, cmd := range r {
		commands = append(commands, cmd)
	}
	sort.Slice(commands, func(i, j int) bool { return commands[i].name < commands[j].name })
	return commands
}

// Run executes a built-in or maw-<command> executable and returns its exit status.
// Plugins are discovered from absolute PATH directories only; no shell is used.
func Run(ctx context.Context, args []string, stdin io.Reader, stdout, stderr io.Writer, version string) int {
	r := registry{}
	fail := func(message string) int { fmt.Fprintln(stderr, "maw:", message); return 2 }
	rootHelp := func() int {
		fmt.Fprintln(stdout, "Usage: maw <command> [args]\n\nCommands:")
		for _, cmd := range r.sorted() {
			fmt.Fprintf(stdout, "  %-12s %s\n", cmd.name, cmd.summary)
		}
		fmt.Fprintln(stdout, "\nRun 'maw help <command>' for command help.\nPlugins: executable maw-<command> files in absolute PATH directories.")
		return 0
	}
	var help func([]string) int
	help = func(args []string) int {
		if len(args) == 0 {
			return rootHelp()
		}
		if len(args) != 1 {
			return fail("usage: maw help [command]")
		}
		cmd, ok := r[args[0]]
		if !ok {
			return fail(fmt.Sprintf("unknown command %q; run 'maw help'", args[0]))
		}
		if cmd.path != "" {
			return cmd.run([]string{"--help"})
		}
		fmt.Fprintf(stdout, "Usage: %s\n\n%s\n", cmd.usage, cmd.summary)
		return 0
	}
	r["help"] = command{name: "help", summary: "Show command help", usage: "maw help [command]", run: help}
	r["version"] = command{name: "version", summary: "Show maw version", usage: "maw version", run: func(args []string) int {
		if len(args) != 0 {
			return fail("usage: maw version")
		}
		fmt.Fprintln(stdout, "maw", version)
		return 0
	}}
	r["plugins"] = command{name: "plugins", summary: "List commands and executable plugin paths", usage: "maw plugins", run: func(args []string) int {
		if len(args) != 0 {
			return fail("usage: maw plugins")
		}
		fmt.Fprintln(stdout, "NAME\tTYPE\tPATH")
		for _, cmd := range r.sorted() {
			kind, path := "builtin", "-"
			if cmd.path != "" {
				kind, path = "external", cmd.path
			}
			fmt.Fprintf(stdout, "%s\t%s\t%s\n", cmd.name, kind, path)
		}
		return 0
	}}
	for name, path := range discover() {
		if _, exists := r[name]; exists {
			continue
		}
		r[name] = command{name: name, summary: "External plugin", path: path, run: func(args []string) int {
			return execute(ctx, path, args, stdin, stdout, stderr)
		}}
	}
	if len(args) == 0 {
		return rootHelp()
	}
	name := args[0]
	if (name == "-h" || name == "--help" || name == "-v" || name == "--version") && len(args) != 1 {
		return fail("global help/version flags do not accept arguments")
	}
	switch name {
	case "-h", "--help":
		name = "help"
	case "-v", "--version":
		name = "version"
	}
	cmd, ok := r[name]
	if !ok {
		return fail(fmt.Sprintf("unknown command %q; run 'maw help'", args[0]))
	}
	if cmd.path == "" && len(args) == 2 && (args[1] == "-h" || args[1] == "--help") {
		return help([]string{name})
	}
	return cmd.run(args[1:])
}
