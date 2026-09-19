package plugins

import (
	"context"
	"fmt"
	"os"
	"path/filepath"
	"regexp"
	"strings"

	"github.com/Soul-Brews-Studio/maw-cli/src/go/internal/command"
)

var fullCommit = regexp.MustCompile(`^[a-fA-F0-9]{40}$`)
var safeRef = regexp.MustCompile(`^[A-Za-z0-9][A-Za-z0-9._/-]*$`)

func lifecycle(ctx context.Context, i *command.Invocation) int {
	args := i.Args
	usage := "usage: maw plugin install SOURCE [--ref REF] | update NAME [--ref REF] | info|check NAME"
	if len(args) != 2 && len(args) != 4 {
		return i.Fail(usage)
	}
	ref := ""
	if len(args) == 4 {
		if (args[0] != "install" && args[0] != "update") || args[2] != "--ref" || !safeRef.MatchString(args[3]) {
			return i.Fail(usage)
		}
		ref = args[3]
	}
	root, _, err := paths()
	if err == nil {
		if args[0] == "install" {
			err = installGitPlugin(ctx, root, args[1], ref, i)
		} else {
			var dir string
			dir, err = managedPlugin(ctx, root, args[1])
			if err == nil {
				if args[0] == "update" {
					err = updateGitPlugin(ctx, dir, args[1], ref, i)
				} else {
					err = inspectGitPlugin(ctx, dir, args[1], args[0] == "check", i)
				}
			}
		}
	}
	if err != nil {
		fmt.Fprintln(i.Stderr, "maw:", err)
		return 1
	}
	return 0
}

func installGitPlugin(ctx context.Context, root, source, ref string, i *command.Invocation) error {
	if source == "herdr" {
		source = herdrRepository
	}
	if !strings.HasPrefix(source, "https://") {
		if at := strings.LastIndex(source, "@"); at > 0 && !filepath.IsAbs(source) {
			if ref != "" {
				return fmt.Errorf("ref supplied twice")
			}
			ref, source = source[at+1:], source[:at]
		}
		if info, err := os.Stat(source); err == nil && info.IsDir() {
			source, err = filepath.Abs(source)
			if err != nil {
				return err
			}
		} else {
			parts := strings.Split(source, "/")
			if len(parts) != 2 || !lifecycleName(parts[0]) || !lifecycleName(parts[1]) {
				return fmt.Errorf("source must be herdr, owner/repo, HTTPS URL or local Git directory")
			}
			source = "https://github.com/" + source
		}
	}
	if strings.ContainsAny(source, "\r\n\x00") || (ref != "" && !safeRef.MatchString(ref)) {
		return fmt.Errorf("invalid source or ref")
	}
	if err := os.MkdirAll(root, 0700); err != nil {
		return err
	}
	stage, err := os.MkdirTemp(root, ".install-")
	if err != nil {
		return err
	}
	defer os.RemoveAll(stage)
	dir := filepath.Join(stage, "repo")
	if _, err = pluginGit(ctx, root, "clone", "--depth", "1", "--no-local", "--", source, dir); err != nil {
		return err
	}
	if ref != "" {
		commit, err := fetchPluginRef(ctx, dir, ref)
		if err != nil {
			return err
		}
		if _, err = pluginGit(ctx, dir, "checkout", "--detach", commit); err != nil {
			return err
		}
	}
	name, entry, err := candidateManifest(ctx, dir, "HEAD")
	if err != nil {
		return err
	}
	if err = regularEntry(dir, entry); err != nil {
		return err
	}
	commit, err := pluginGit(ctx, dir, "rev-parse", "HEAD")
	if err != nil {
		return err
	}
	target := filepath.Join(root, name)
	if _, err = os.Lstat(target); !os.IsNotExist(err) {
		return fmt.Errorf("plugin destination already exists: %s", name)
	}
	if err = os.Rename(dir, target); err != nil {
		return err
	}
	fmt.Fprintln(i.Stdout, "installed", name, commit)
	return nil
}

func managedPlugin(ctx context.Context, root, name string) (string, error) {
	if !lifecycleName(name) {
		return "", fmt.Errorf("invalid plugin name")
	}
	dir := filepath.Join(root, name)
	for _, path := range []string{dir, filepath.Join(dir, ".git")} {
		info, err := os.Lstat(path)
		if err != nil || !info.IsDir() || info.Mode()&os.ModeSymlink != 0 {
			return "", fmt.Errorf("plugin must be its own real Git checkout")
		}
	}
	real, err := filepath.EvalSymlinks(dir)
	if err != nil {
		return "", err
	}
	top, err := pluginGit(ctx, dir, "rev-parse", "--show-toplevel")
	if err != nil || top != real {
		return "", fmt.Errorf("plugin is not its own Git checkout")
	}
	return dir, nil
}

func fetchPluginRef(ctx context.Context, dir, ref string) (string, error) {
	if _, err := pluginGit(ctx, dir, "fetch", "--depth", "1", "origin", ref); err != nil {
		return "", err
	}
	commit, err := pluginGit(ctx, dir, "rev-parse", "FETCH_HEAD^{commit}")
	if err == nil && fullCommit.MatchString(ref) && !strings.EqualFold(commit, ref) {
		return "", fmt.Errorf("resolved commit does not match requested pin")
	}
	return commit, err
}

func updateGitPlugin(ctx context.Context, dir, name, ref string, i *command.Invocation) error {
	status, err := pluginGit(ctx, dir, "status", "--porcelain", "--untracked-files=all")
	if err != nil {
		return err
	}
	if status != "" {
		return fmt.Errorf("plugin has local changes; update refused")
	}
	if ref == "" {
		branch, err := pluginGit(ctx, dir, "rev-parse", "--abbrev-ref", "HEAD")
		if err != nil {
			return err
		}
		if branch == "HEAD" {
			commit, err := pluginGit(ctx, dir, "rev-parse", "HEAD")
			if err != nil {
				return err
			}
			fmt.Fprintln(i.Stdout, "pinned", name, commit, "(use update --ref to change)")
			return nil
		}
		if _, err = pluginGit(ctx, dir, "fetch", "origin"); err != nil {
			return err
		}
		ref, err = pluginGit(ctx, dir, "rev-parse", "@{upstream}^{commit}")
	} else {
		ref, err = fetchPluginRef(ctx, dir, ref)
	}
	if err != nil {
		return err
	}
	candidate, _, err := candidateManifest(ctx, dir, ref)
	if err != nil {
		return err
	}
	if candidate != name {
		return fmt.Errorf("update would change plugin name")
	}
	if len(i.Args) == 4 {
		_, err = pluginGit(ctx, dir, "checkout", "--detach", ref)
	} else {
		_, err = pluginGit(ctx, dir, "merge", "--ff-only", ref)
	}
	if err != nil {
		return err
	}
	fmt.Fprintln(i.Stdout, "updated", name, ref)
	return nil
}

func inspectGitPlugin(ctx context.Context, dir, name string, check bool, i *command.Invocation) error {
	actualName, entry, err := candidateManifest(ctx, dir, "HEAD")
	if err != nil {
		return err
	}
	if actualName != name {
		return fmt.Errorf("plugin directory and manifest name differ")
	}
	if err = regularEntry(dir, entry); err != nil {
		return err
	}
	commit, err := pluginGit(ctx, dir, "rev-parse", "HEAD")
	if err != nil {
		return err
	}
	source, err := pluginGit(ctx, dir, "remote", "get-url", "origin")
	if err != nil {
		return err
	}
	hash, err := pluginGit(ctx, dir, "hash-object", "--no-filters", "--", entry)
	if err != nil {
		return err
	}
	expected, err := treeBlob(ctx, dir, "HEAD", entry)
	if err != nil {
		return err
	}
	dirty, err := pluginGit(ctx, dir, "status", "--porcelain", "--untracked-files=all")
	if err != nil {
		return err
	}
	status := "clean"
	if dirty != "" || hash != expected {
		status = "modified"
	}
	fmt.Fprintf(i.Stdout, "source\t%s\ncommit\t%s\nentry\t%s\nhash\t%s (git-blob)\nstatus\t%s\n", safePath(source), commit, safePath(entry), hash, status)
	if check && status != "clean" {
		return fmt.Errorf("plugin check failed: local modifications")
	}
	return nil
}
