package plugins

import (
	"context"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"unicode/utf8"
)

func lifecycleName(name string) bool {
	return pluginName.MatchString(name) && ((name[0] >= 'a' && name[0] <= 'z') || (name[0] >= 'A' && name[0] <= 'Z') || (name[0] >= '0' && name[0] <= '9'))
}

func lifecycleEntry(entry string) bool {
	if entry == "" || strings.Contains(entry, "\\") || filepath.IsAbs(entry) || safePath(entry) != entry {
		return false
	}
	for _, part := range strings.Split(entry, "/") {
		if part == "" || part == "." || part == ".." || strings.EqualFold(part, ".git") {
			return false
		}
	}
	return true
}

func treeBlob(ctx context.Context, dir, ref, path string) (string, error) {
	line, err := pluginGit(ctx, dir, "ls-tree", "-z", ref, "--", path)
	row := strings.SplitN(line, "\t", 2)
	fields := strings.Fields(row[0])
	if err != nil || len(row) != 2 || row[1] != path+"\x00" || len(fields) != 3 || (fields[0] != "100644" && fields[0] != "100755") || fields[1] != "blob" {
		return "", fmt.Errorf("plugin file must be a committed regular file: %s", safePath(path))
	}
	return fields[2], nil
}

func candidateManifest(ctx context.Context, dir, ref string) (string, string, error) {
	if _, err := treeBlob(ctx, dir, ref, "plugin.json"); err != nil {
		return "", "", err
	}
	size, err := pluginGit(ctx, dir, "cat-file", "-s", ref+":plugin.json")
	n, e := strconv.Atoi(size)
	if err != nil || e != nil || n > 1048576 {
		return "", "", fmt.Errorf("invalid plugin.json size")
	}
	data, err := pluginGit(ctx, dir, "show", ref+":plugin.json")
	var m map[string]any
	if err != nil || !utf8.ValidString(data) || json.Unmarshal([]byte(data), &m) != nil || m == nil {
		return "", "", fmt.Errorf("invalid plugin.json")
	}
	name, entry, err := manifestEntry(m)
	if err != nil {
		return "", "", err
	}
	_, err = treeBlob(ctx, dir, ref, entry)
	return name, entry, err
}

func manifestEntry(m map[string]any) (string, string, error) {
	name, version, entry := stringField(m, "name"), stringField(m, "version"), stringField(m, "entry")
	if entry == "" {
		entry = stringField(objectField(m, "artifact"), "path")
	}
	if entry == "" {
		entry = stringField(m, "wasm")
	}
	if !lifecycleName(name) || version == "" || safePath(version) != version || !lifecycleEntry(entry) {
		return "", "", fmt.Errorf("invalid plugin name, version or entry")
	}
	return name, entry, nil
}

func regularEntry(dir, entry string) error {
	path := dir
	for _, part := range strings.Split(entry, "/") {
		path = filepath.Join(path, part)
		info, err := os.Lstat(path)
		if err != nil || info.Mode()&os.ModeSymlink != 0 {
			return fmt.Errorf("plugin entry contains a missing file or symlink")
		}
	}
	info, err := os.Stat(path)
	if err != nil || !info.Mode().IsRegular() {
		return fmt.Errorf("plugin entry is not a regular file")
	}
	return nil
}
