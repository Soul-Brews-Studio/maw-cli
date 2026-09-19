package plugins

import (
	"bufio"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"strings"

	"github.com/Soul-Brews-Studio/maw-cli/src/go/internal/command"
)

func lockPluginInstall(root, name string) (func(), error) {
	lock := filepath.Join(root, ".install-"+name+".lock")
	if err := os.Mkdir(lock, 0700); err != nil {
		return nil, fmt.Errorf("cannot lock plugin install at %s: %w", safePath(lock), err)
	}
	return func() { os.Remove(lock) }, nil
}

func archiveReplacement(i *command.Invocation, target string) (string, error) {
	file, ok := i.Stdin.(*os.File)
	if !ok {
		return "", fmt.Errorf("plugin already exists; use --backup or --replace explicitly")
	}
	info, err := file.Stat()
	if err != nil || info.Mode()&os.ModeCharDevice == 0 {
		return "", fmt.Errorf("plugin already exists; use --backup or --replace explicitly")
	}
	fmt.Fprintf(i.Stderr, "Plugin exists: %s\n[B] Back up and replace (default), [r] Replace without backup, [c] Cancel: ", safePath(target))
	answer, err := bufio.NewReader(io.LimitReader(i.Stdin, 64)).ReadString('\n')
	if err != nil {
		return "cancel", nil
	}
	switch strings.ToLower(strings.TrimSpace(answer)) {
	case "", "b", "backup":
		return "backup", nil
	case "r", "replace":
		return "replace", nil
	case "c", "cancel":
		return "cancel", nil
	default:
		return "", fmt.Errorf("invalid choice; installation cancelled")
	}
}

// keepStage is true only when an old install could not be restored from staging.
func promoteArchive(root, stage, dir, name, mode string, i *command.Invocation) (keepStage bool, err error) {
	unlock, err := lockPluginInstall(root, name)
	if err != nil {
		return false, err
	}
	defer unlock()
	target := filepath.Join(root, name)
	old, err := os.Lstat(target)
	if err != nil && !os.IsNotExist(err) {
		return false, err
	}
	if old != nil {
		if !old.IsDir() || old.Mode()&os.ModeSymlink != 0 {
			return false, fmt.Errorf("existing plugin must be a real directory, not a symlink")
		}
		if mode == "" {
			mode, err = archiveReplacement(i, target)
			if err != nil {
				return false, err
			}
		}
		if mode == "cancel" {
			fmt.Fprintln(i.Stdout, "installation cancelled")
			return false, nil
		}
	}
	// Recheck after confirmation; never replace a different directory than displayed.
	current, statErr := os.Lstat(target)
	if (old == nil && !os.IsNotExist(statErr)) || (old != nil && (statErr != nil || !os.SameFile(old, current))) {
		return false, fmt.Errorf("plugin destination changed during installation; retry")
	}
	previous := ""
	if old != nil {
		previous = filepath.Join(stage, "previous")
		if mode == "backup" {
			base := root + "-backups"
			if err = os.MkdirAll(base, 0700); err != nil {
				return false, err
			}
			info, err := os.Lstat(base)
			if err != nil || !info.IsDir() || info.Mode()&os.ModeSymlink != 0 {
				return false, fmt.Errorf("backup location must be a real directory")
			}
			slot, err := os.MkdirTemp(base, name+"-")
			if err != nil {
				return false, err
			}
			previous = filepath.Join(slot, name)
		}
		if err = os.Rename(target, previous); err != nil {
			return false, fmt.Errorf("cannot preserve existing plugin: %w", err)
		}
		fmt.Fprintf(i.Stderr, "Previous plugin: %s\n", safePath(previous))
	}
	if err = os.Rename(dir, target); err != nil {
		if previous != "" {
			if _, e := os.Lstat(target); !os.IsNotExist(e) {
				return mode == "replace", fmt.Errorf("installation failed; destination changed; old plugin kept at %s", safePath(previous))
			}
			if restoreErr := os.Rename(previous, target); restoreErr != nil {
				return mode == "replace", fmt.Errorf("installation failed (%v); restore failed (%v); old plugin kept at %s", err, restoreErr, safePath(previous))
			}
		}
		return false, err
	}
	fmt.Fprintf(i.Stdout, "installed %s from archive at %s\n", name, safePath(target))
	if old != nil && mode == "backup" {
		fmt.Fprintf(i.Stdout, "backup\t%s\n", safePath(previous))
	}
	return false, nil
}
