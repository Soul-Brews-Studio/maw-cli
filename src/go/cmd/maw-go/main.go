// Command maw-go is the Go implementation of the plugin-oriented maw-cli host.
package main

import (
	"context"
	"os"
	"os/signal"
	"runtime/debug"

	"github.com/Soul-Brews-Studio/maw-cli/src/go/internal/cli"
)

// releaseVersion is set only by prebuilt release builds; remote Go installs retain module build info.
var releaseVersion string

func main() {
	os.Exit(run())
}

func run() int {
	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt)
	defer stop()
	version := releaseVersion
	if version == "" {
		version = "dev"
		if info, ok := debug.ReadBuildInfo(); ok && info.Main.Version != "" && info.Main.Version != "(devel)" {
			version = info.Main.Version
		}
	}
	return cli.Run(ctx, os.Args[1:], os.Stdin, os.Stdout, os.Stderr, version)
}
