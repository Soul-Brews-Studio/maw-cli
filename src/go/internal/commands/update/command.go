// Package update implements explicit, Go-only self-update from published releases.
package update

import (
	"context"
	"flag"
	"fmt"
	"runtime"
	"time"

	"github.com/Soul-Brews-Studio/maw-cli/src/go/internal/command"
)

type plugin struct {
	check   bool
	version string
}

func init() { command.Register(func() command.CommandPlugin { return &plugin{} }) }
func (*plugin) Metadata() command.Metadata {
	return command.Metadata{Name: "update", Summary: "Update maw-go from verified alpha release assets (not plugins)", Usage: "maw update [--check] [--version vYY.M.D-alpha.HMM]"}
}
func (p *plugin) BindFlags(flags *flag.FlagSet) {
	flags.BoolVar(&p.check, "check", false, "show the published release without installing")
	flags.StringVar(&p.version, "version", "", "select an exact published alpha tag (allows downgrade/reinstall)")
}
func (p *plugin) Run(ctx context.Context, i *command.Invocation) int {
	if len(i.Args) != 0 || (p.version != "" && !tagPattern.MatchString(p.version)) {
		return i.Fail("usage: " + p.Metadata().Usage)
	}
	if !p.check && i.Version == "dev" {
		return i.Fail("local dev/go run builds are not self-updated; install maw-go with go install first (or use update --check)")
	}
	if (runtime.GOOS != "linux" && runtime.GOOS != "darwin") || (runtime.GOARCH != "amd64" && runtime.GOARCH != "arm64") {
		return i.Fail("self-update supports Linux/macOS amd64/arm64 only")
	}
	ctx, cancel := context.WithTimeout(ctx, 3*time.Minute)
	defer cancel()
	if err := p.update(ctx, i); err != nil {
		fmt.Fprintln(i.Stderr, "maw: update:", err)
		return 1
	}
	return 0
}

func (p *plugin) update(ctx context.Context, i *command.Invocation) error {
	release, err := selectRelease(ctx, p.version)
	if err != nil {
		return err
	}
	asset := "maw-go-" + runtime.GOOS + "-" + runtime.GOARCH + ".tar.gz"
	plan, sums, err := releaseMetadata(ctx, release, asset)
	if err != nil {
		return err
	}
	fmt.Fprintf(i.Stdout, "current\t%s\ntarget\t%s\ncommit\t%s\n", i.Version, plan.Tag, plan.Commit)
	install, status, err := updateStatus(ctx, i.Version, plan, p.version != "")
	if err != nil {
		return err
	}
	fmt.Fprintln(i.Stdout, "status\t"+status)
	if p.check || !install {
		return nil
	}
	path, err := installRelease(ctx, release, plan, sums[asset], asset)
	if err != nil {
		return err
	}
	fmt.Fprintf(i.Stdout, "updated\t%s\n", path)
	return nil
}
