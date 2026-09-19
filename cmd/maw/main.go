// Command maw is the small, plugin-oriented maw-herdr command-line host.
package main

import (
	"context"
	"os"
	"os/signal"
	"runtime/debug"

	"github.com/Soul-Brews-Studio/maw-herdr/internal/cli"
)

func main() {
	os.Exit(run())
}

func run() int {
	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt)
	defer stop()
	version := "dev"
	if info, ok := debug.ReadBuildInfo(); ok && info.Main.Version != "" && info.Main.Version != "(devel)" {
		version = info.Main.Version
	}
	return cli.Run(ctx, os.Args[1:], os.Stdin, os.Stdout, os.Stderr, version)
}
