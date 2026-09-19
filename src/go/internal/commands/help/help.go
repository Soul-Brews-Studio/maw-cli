package help

import (
	"context"
	"flag"
	"fmt"

	"github.com/Soul-Brews-Studio/maw-herdr/src/go/internal/command"
)

type plugin struct{}

func init() { command.Register(func() command.CommandPlugin { return &plugin{} }) }
func (*plugin) Metadata() command.Metadata {
	return command.Metadata{Name: "help", Summary: "Show command help", Usage: "maw help [command]"}
}
func (*plugin) BindFlags(*flag.FlagSet) {}
func (*plugin) Run(ctx context.Context, i *command.Invocation) int {
	if len(i.Args) == 0 {
		fmt.Fprintln(i.Stdout, "Usage: maw <command> [args]\n\nCommands:")
		for _, cmd := range i.Commands {
			fmt.Fprintf(i.Stdout, "  %-12s %s\n", cmd.Name, cmd.Summary)
		}
		fmt.Fprintln(i.Stdout, "\nRun 'maw help <command>' for command help.\nPlugins: executable maw-<command> files in absolute PATH directories.")
		return 0
	}
	if len(i.Args) != 1 {
		return i.Fail("usage: maw help [command]")
	}
	for _, cmd := range i.Commands {
		if cmd.Name != i.Args[0] {
			continue
		}
		if cmd.Path != "" {
			return i.Execute(ctx, cmd.Name, []string{"--help"})
		}
		fmt.Fprintf(i.Stdout, "Usage: %s\n\n%s\n", cmd.Usage, cmd.Summary)
		return 0
	}
	return i.Fail(fmt.Sprintf("unknown command %q; run 'maw help'", i.Args[0]))
}
