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
	"strings"
	"time"
)

var (
	commandName = regexp.MustCompile(`^[a-z][a-z0-9-]*$`)
	shortCommit = regexp.MustCompile(`^true\n([0-9a-f]{4,64})\n?$`)
	shellWord   = regexp.MustCompile(`^[A-Za-z0-9_@%+=:,./-]+$`)
)

// resolveInstalled picks the plugin a verb names (#55): a plugin whose command
// (cli.command, else its manifest name) it is, first in inventory order, and only
// then one declaring it in cli.aliases, so an alias never shadows a command.
// Built-ins and PATH executables were already tried by the caller. An alias that
// more than one enabled plugin declares resolves to none of them and returns
// every holder; a disabled holder answers only when no enabled one does.
func resolveInstalled(inventory []installed, name string) (*installed, []installed) {
	for i := range inventory {
		if inventory[i].Command == name {
			return &inventory[i], nil
		}
	}
	var enabled, disabled []installed
	for _, p := range inventory {
		for _, alias := range p.Aliases {
			if alias != name {
				continue
			}
			if p.Enabled {
				enabled = append(enabled, p)
			} else {
				disabled = append(disabled, p)
			}
			break
		}
	}
	switch {
	case len(enabled) == 1:
		return &enabled[0], nil
	case len(enabled) > 1:
		return nil, enabled
	case len(disabled) > 0:
		return &disabled[0], nil
	}
	return nil, nil
}

// shellQuote quotes one word for a copy-pasteable sh command line.
func shellQuote(word string) string {
	if shellWord.MatchString(word) {
		return word
	}
	return "'" + strings.ReplaceAll(word, "'", `'\''`) + "'"
}

// pluginCommit returns the short commit of the Git work tree a plugin directory
// lies in, for `maw <plugin> version` (#52), or "" when it lies in none. git runs
// inside the directory, so a symlinked plugin reports the repository its target
// lives in, even from a subfolder of a larger one. `rev-parse --short HEAD`, never
// `describe`: plugin checkouts never fetch new tags, so describe goes stale.
// Inherited GIT_* routing (a hook's GIT_DIR) is dropped, GIT_OPTIONAL_LOCKS=0
// keeps it from writing, and any failure or the two-second timeout reads as
// "not a Git checkout".
func pluginCommit(ctx context.Context, dir string) string {
	ctx, cancel := context.WithTimeout(ctx, 2*time.Second)
	defer cancel()
	cmd := exec.CommandContext(ctx, "git", "-C", dir, "rev-parse", "--is-inside-work-tree", "--short", "HEAD")
	cmd.Env = []string{"GIT_OPTIONAL_LOCKS=0"}
	for _, value := range os.Environ() {
		if !strings.HasPrefix(value, "GIT_") {
			cmd.Env = append(cmd.Env, value)
		}
	}
	cmd.WaitDelay = time.Second
	output, err := cmd.Output()
	if err != nil {
		return ""
	}
	if match := shortCommit.FindSubmatch(output); match != nil {
		return string(match[1])
	}
	return ""
}

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
	p, ambiguous := resolveInstalled(inventory, name)
	if len(ambiguous) > 0 {
		names, commands := make([]string, len(ambiguous)), ""
		for i, holder := range ambiguous {
			names[i] = holder.Name
			line := []string{"maw", holder.Command}
			for _, arg := range args {
				line = append(line, shellQuote(arg))
			}
			commands += "  " + strings.Join(line, " ") + "\n"
		}
		fmt.Fprintf(stderr, "maw: %q is an alias of %d plugins (%s); neither runs. Run one by name:\n%s",
			name, len(ambiguous), strings.Join(names, ", "), commands)
		return 2, true
	}
	if p == nil {
		return 0, false
	}
	fail := func(code int, reason string) (int, bool) {
		fmt.Fprintf(stderr, "maw: plugin %s %s\n", p.Name, reason)
		return code, true
	}
	if !p.Enabled {
		return fail(1, "is disabled")
	}
	// Reserved verb (#52): the host answers from plugin.json; no plugin code runs.
	if len(args) == 1 && (args[0] == "version" || args[0] == "--version") {
		commit := pluginCommit(ctx, p.Dir)
		if commit == "" {
			commit = "not a Git checkout"
		}
		fmt.Fprintf(stdout, "%s %s (%s)\n", p.Name, p.Version, commit)
		return 0, true
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
