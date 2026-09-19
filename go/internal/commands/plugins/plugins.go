package plugins

import (
	"context"
	"flag"
	"fmt"

	"github.com/Soul-Brews-Studio/maw-herdr/go/internal/command"
)

type plugin struct{}

func init() { command.Register(func() command.CommandPlugin { return &plugin{} }) }
func (*plugin) Metadata() command.Metadata {
	return command.Metadata{Name: "plugins", Summary: "List commands and executable plugin paths", Usage: "maw plugins"}
}
func (*plugin) BindFlags(*flag.FlagSet) {}
func (*plugin) Run(_ context.Context, i *command.Invocation) int {
	if len(i.Args) != 0 {
		return i.Fail("usage: maw plugins")
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
