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
		return command.Metadata{Name: "plugins", Summary: "Alias for plugin ls", Usage: "maw plugins [ls]"}
	}
	return command.Metadata{Name: "plugin", Summary: "List commands and executable plugin paths", Usage: "maw plugin ls"}
}
func (*plugin) BindFlags(*flag.FlagSet) {}
func (p *plugin) Run(_ context.Context, i *command.Invocation) int {
	if !(len(i.Args) == 1 && i.Args[0] == "ls") && !(p.legacy && len(i.Args) == 0) {
		return i.Fail("usage: " + p.Metadata().Usage)
	}
	fmt.Fprintln(i.Stdout, "NAME\tTYPE\tPATH")
	for _, cmd := range i.Commands {
		kind, path := "builtin", "-"
		if cmd.Path != "" {
			kind, path = "external", cmd.Path
		}
		fmt.Fprintf(i.Stdout, "%s\t%s\t%s\n", cmd.Name, kind, path)
	}
	return 0
}
