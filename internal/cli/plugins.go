package cli

import (
	"context"
	"errors"
	"fmt"
	"io"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"strings"
)

func validName(name string) bool {
	if name == "" || name[0] < 'a' || name[0] > 'z' {
		return false
	}
	for _, c := range name {
		if !(c >= 'a' && c <= 'z' || c >= '0' && c <= '9' || c == '-') {
			return false
		}
	}
	return true
}

func discover() map[string]string {
	plugins := map[string]string{}
	for _, dir := range filepath.SplitList(os.Getenv("PATH")) {
		if !filepath.IsAbs(dir) {
			continue
		}
		entries, err := os.ReadDir(dir)
		if err != nil {
			continue
		}
		for _, entry := range entries {
			name := entry.Name()
			if runtime.GOOS == "windows" {
				if !strings.HasSuffix(name, ".exe") {
					continue
				}
				name = strings.TrimSuffix(name, ".exe")
			}
			if !strings.HasPrefix(name, "maw-") {
				continue
			}
			name = strings.TrimPrefix(name, "maw-")
			if !validName(name) {
				continue
			}
			if _, exists := plugins[name]; exists {
				continue
			}
			path, err := filepath.EvalSymlinks(filepath.Join(dir, entry.Name()))
			if err != nil {
				continue
			}
			info, err := os.Stat(path)
			if err != nil || !info.Mode().IsRegular() {
				continue
			}
			if runtime.GOOS != "windows" && info.Mode().Perm()&0111 == 0 {
				continue
			}
			plugins[name] = path
		}
	}
	return plugins
}

func execute(ctx context.Context, path string, args []string, stdin io.Reader, stdout, stderr io.Writer) int {
	cmd := exec.CommandContext(ctx, path, args...)
	cmd.Stdin, cmd.Stdout, cmd.Stderr = stdin, stdout, stderr
	if err := cmd.Run(); err != nil {
		var exit *exec.ExitError
		if errors.As(err, &exit) && exit.ExitCode() >= 0 {
			return exit.ExitCode()
		}
		fmt.Fprintf(stderr, "maw: cannot execute %s: %v\n", path, err)
		if ctx.Err() != nil {
			return 1
		}
		return 126
	}
	return 0
}
