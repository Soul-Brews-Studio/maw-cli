package plugins

import (
	"context"
	"errors"
	"fmt"
	"io"
	"os"
	"os/exec"
	"path/filepath"
	"regexp"
	"runtime"
)

var commandName = regexp.MustCompile(`^[a-z][a-z0-9-]*$`)

// ExecuteInstalled resolves a standalone installed CLI only after builtin/PATH lookup.
func ExecuteInstalled(ctx context.Context, name string, args []string, stdin io.Reader, stdout, stderr io.Writer) (int, bool) {
	if !commandName.MatchString(name) || name == "go" || name == "rs" || name == "js" || name == "zig" || name == "index" {
		return 0, false
	}
	root, config, err := paths()
	var inventory []installed
	if err == nil {
		var disabled map[string]bool
		disabled, err = disabledPlugins(config)
		if err == nil {
			inventory, err = scanInstalled(root, disabled, stderr)
		}
	}
	if err != nil {
		fmt.Fprintf(stderr, "maw: %s\n", err)
		return 1, true
	}
	for _, p := range inventory {
		if p.Command != name {
			continue
		}
		fail := func(code int, reason string) (int, bool) {
			fmt.Fprintf(stderr, "maw: plugin %s %s\n", p.Name, reason)
			return code, true
		}
		if !p.Enabled {
			return fail(1, "is disabled")
		}
		if p.Runtime != "bun-dev" || p.Target != "js" || !p.Interactive {
			return fail(126, "is not a standalone Bun CLI (requires runtime=bun-dev, target=js, cli.interactive=true)")
		}
		stat, err := os.Stat(p.Entry)
		if p.Entry == "" || err != nil || !stat.Mode().IsRegular() {
			return fail(126, "entry is missing or not a regular file")
		}
		bun := ""
		bunName := "bun"
		if runtime.GOOS == "windows" {
			bunName = "bun.exe"
		}
		for _, dir := range filepath.SplitList(os.Getenv("PATH")) {
			if !filepath.IsAbs(dir) {
				continue
			}
			candidate := filepath.Join(dir, bunName)
			if stat, err := os.Stat(candidate); err == nil && stat.Mode().IsRegular() && (runtime.GOOS == "windows" || stat.Mode().Perm()&0111 != 0) {
				bun = candidate
				break
			}
		}
		if bun == "" {
			return fail(126, "requires bun on PATH")
		}
		cmd := exec.CommandContext(ctx, bun, append([]string{p.Entry}, args...)...)
		cmd.Stdin, cmd.Stdout, cmd.Stderr = stdin, stdout, stderr
		if err := cmd.Run(); err != nil {
			var exit *exec.ExitError
			if errors.As(err, &exit) && exit.ExitCode() >= 0 {
				return exit.ExitCode(), true
			}
			if ctx.Err() != nil {
				return 1, true
			}
			return fail(126, fmt.Sprintf("cannot execute bun %s: %v", safePath(bun), err))
		}
		return 0, true
	}
	return 0, false
}
