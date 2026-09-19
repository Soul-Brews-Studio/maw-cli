package plugins

import (
	"context"
	"fmt"
	"os"
	"os/exec"
	"strings"
	"time"
)

func pluginGit(ctx context.Context, dir string, args ...string) (string, error) {
	ctx, cancel := context.WithTimeout(ctx, 90*time.Second)
	defer cancel()
	// No commits are created; a fixed reflog identity avoids hostname/DNS lookup.
	prefix := []string{"--literal-pathspecs", "-c", "core.hooksPath=/dev/null", "-c", "core.fsmonitor=false", "-c", "protocol.ext.allow=never", "-c", "user.name=maw", "-c", "user.email=maw@localhost"}
	cmd := exec.CommandContext(ctx, "git", append(prefix, args...)...)
	cmd.Dir = dir
	for _, value := range os.Environ() {
		if !strings.HasPrefix(value, "GIT_") {
			cmd.Env = append(cmd.Env, value)
		}
	}
	cmd.Env = append(cmd.Env, "GIT_CONFIG_GLOBAL=/dev/null", "GIT_CONFIG_SYSTEM=/dev/null", "GIT_CONFIG_NOSYSTEM=1", "GIT_TERMINAL_PROMPT=0", "GIT_LFS_SKIP_SMUDGE=1")
	output, err := cmd.Output()
	if err != nil {
		detail := err.Error()
		if failed, ok := err.(*exec.ExitError); ok {
			data := failed.Stderr
			if len(data) > 4096 {
				data = data[:4096]
			}
			if len(data) > 0 {
				detail = safePath(strings.TrimSpace(string(data)))
			}
		}
		return "", fmt.Errorf("git %s failed: %s", args[0], detail)
	}
	return strings.TrimSpace(string(output)), nil
}
