package plugins

import (
	"context"
	"flag"
	"fmt"

	"github.com/Soul-Brews-Studio/maw-cli/src/go/internal/command"
)

type plugin struct{ legacy bool }

func init() {
	command.Register(func() command.CommandPlugin { return &plugin{} })
	command.Register(func() command.CommandPlugin { return &plugin{legacy: true} })
}
func (p *plugin) Metadata() command.Metadata {
	if p.legacy {
		return command.Metadata{Name: "plugins", Summary: "Alias for plugin ls", Usage: "maw plugins [ls] [-v|--verbose] [--all]"}
	}
	return command.Metadata{Name: "plugin", Summary: "List installed plugin metadata", Usage: "maw plugin ls [-v|--verbose] [--all]"}
}
func (*plugin) BindFlags(*flag.FlagSet) {}
func (p *plugin) Run(_ context.Context, i *command.Invocation) int {
	args := i.Args
	if len(args) > 0 && args[0] == "ls" {
		args = args[1:]
	} else if !p.legacy {
		return i.Fail("usage: " + p.Metadata().Usage)
	}
	verbose, all := false, false
	for _, arg := range args {
		if (arg == "-v" || arg == "--verbose") && !verbose {
			verbose = true
		} else if arg == "--all" && !all {
			all = true
		} else {
			return i.Fail("usage: " + p.Metadata().Usage)
		}
	}
	root, config, err := paths()
	if err == nil {
		var disabled map[string]bool
		disabled, err = disabledPlugins(config)
		if err == nil {
			var plugins []installed
			plugins, err = scanInstalled(root, disabled, i.Stderr)
			if err == nil {
				render(i.Stdout, plugins, verbose, all)
				return 0
			}
		}
	}
	fmt.Fprintf(i.Stderr, "maw: %s\n", err)
	return 1
}
