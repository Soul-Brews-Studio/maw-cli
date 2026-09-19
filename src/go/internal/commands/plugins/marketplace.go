package plugins

import (
	"context"
	"flag"
	"fmt"

	"github.com/Soul-Brews-Studio/maw-cli/src/go/internal/command"
)

const herdrRepository = "https://github.com/Soul-Brews-Studio/maw-herdr-plugin"

type marketplace struct{}

func init() { command.Register(func() command.CommandPlugin { return &marketplace{} }) }
func (*marketplace) Metadata() command.Metadata {
	return command.Metadata{Name: "marketplace", Summary: "List known plugin sources", Usage: "maw marketplace [ls|list]"}
}
func (*marketplace) BindFlags(*flag.FlagSet) {}
func (p *marketplace) Run(_ context.Context, i *command.Invocation) int {
	if len(i.Args) > 1 || (len(i.Args) == 1 && i.Args[0] != "ls" && i.Args[0] != "list") {
		return i.Fail("usage: " + p.Metadata().Usage)
	}
	fmt.Fprintln(i.Stdout, "NAME\tSOURCE")
	fmt.Fprintln(i.Stdout, "herdr\t"+herdrRepository)
	return 0
}
