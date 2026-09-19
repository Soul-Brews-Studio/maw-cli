package version

import (
	"context"
	"flag"
	"fmt"

	"github.com/Soul-Brews-Studio/maw-herdr/src/go/internal/command"
)

type plugin struct{}

func init() { command.Register(func() command.CommandPlugin { return &plugin{} }) }
func (*plugin) Metadata() command.Metadata {
	return command.Metadata{Name: "version", Summary: "Show maw version", Usage: "maw version"}
}
func (*plugin) BindFlags(*flag.FlagSet) {}
func (*plugin) Run(_ context.Context, i *command.Invocation) int {
	if len(i.Args) != 0 {
		return i.Fail("usage: maw version")
	}
	fmt.Fprintln(i.Stdout, "maw", i.Version)
	return 0
}
