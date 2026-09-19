package plugins

import (
	"context"
	"flag"
	"fmt"
	"os"
	"path/filepath"

	"github.com/Soul-Brews-Studio/maw-cli/src/go/internal/command"
)

const herdrRepository = "https://github.com/Soul-Brews-Studio/maw-herdr-plugin"

type marketplace struct{}

func init() { command.Register(func() command.CommandPlugin { return &marketplace{} }) }
func (*marketplace) Metadata() command.Metadata {
	return command.Metadata{Name: "marketplace", Summary: "List known plugin sources", Usage: "maw marketplace [ls|list]"}
}
func (*marketplace) BindFlags(*flag.FlagSet) {}
func (p *marketplace) Run(ctx context.Context, i *command.Invocation) int {
	if len(i.Args) > 1 || (len(i.Args) == 1 && i.Args[0] != "ls" && i.Args[0] != "list") {
		return i.Fail("usage: " + p.Metadata().Usage)
	}
	root, config, err := paths()
	if err != nil {
		return i.Fail(err.Error())
	}
	disabled, err := disabledPlugins(config)
	if err != nil {
		return i.Fail(err.Error())
	}
	plugins, err := scanInstalled(root, disabled, i.Stderr)
	if err != nil {
		return i.Fail(err.Error())
	}
	status, version, ref, commit := "not-installed", "-", "-", "-"
	// A present but unreadable/invalid installation must not look absent.
	if _, err := os.Lstat(filepath.Join(root, "herdr")); !os.IsNotExist(err) {
		status = "invalid"
	}
	for _, plugin := range plugins {
		if plugin.Name != "herdr" {
			continue
		}
		status, version = "installed", plugin.Version
		if !plugin.Enabled {
			status = "disabled"
		}
		ref, commit, err = marketplaceGit(ctx, plugin.Dir)
		if err != nil {
			fmt.Fprintf(i.Stderr, "maw: cannot read herdr Git metadata at %s: %s\n", safePath(plugin.Dir), safePath(err.Error()))
		}
		break
	}
	if status == "invalid" {
		fmt.Fprintln(i.Stderr, "maw: herdr installation is present but has no valid plugin.json")
	}
	fmt.Fprintln(i.Stdout, "NAME\tSTATUS\tVERSION\tREF\tCOMMIT\tSOURCE")
	fmt.Fprintf(i.Stdout, "herdr\t%s\t%s\t%s\t%s\t%s\n", status, version, ref, commit, herdrRepository)
	return 0
}

func marketplaceGit(ctx context.Context, dir string) (string, string, error) {
	real, err := filepath.EvalSymlinks(dir)
	if err != nil {
		return "-", "-", err
	}
	// Never report an enclosing repository's HEAD for a non-Git plugin.
	if _, err := os.Lstat(filepath.Join(real, ".git")); err != nil {
		if os.IsNotExist(err) {
			return "-", "-", nil
		}
		return "-", "-", err
	}
	top, err := pluginGit(ctx, real, "rev-parse", "--show-toplevel")
	if err != nil {
		return "-", "-", err
	}
	top, err = filepath.EvalSymlinks(top)
	if err != nil {
		return "-", "-", err
	}
	if top != real {
		return "-", "-", fmt.Errorf("plugin is not its own Git checkout")
	}
	commit, err := pluginGit(ctx, real, "rev-parse", "--verify", "HEAD^{commit}")
	if err != nil {
		return "-", "-", err
	}
	if !fullCommit.MatchString(commit) {
		return "-", "-", fmt.Errorf("invalid HEAD commit")
	}
	ref, err := pluginGit(ctx, real, "symbolic-ref", "--quiet", "--short", "HEAD")
	if err != nil {
		ref, err = pluginGit(ctx, real, "describe", "--tags", "--exact-match", "HEAD")
		if err != nil {
			ref = "detached"
		}
	}
	return safePath(ref), commit[:12], nil
}
