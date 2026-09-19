package plugins

import (
	"fmt"
	"os"
	"path/filepath"
	"regexp"
	"sort"
	"strings"
)

var configName = regexp.MustCompile(`^maw\.config\.(\d+)(\.local)?\.json$`)

func disabledPlugins(root string) (map[string]bool, error) {
	entries, err := os.ReadDir(root)
	disabled := map[string]bool{}
	if os.IsNotExist(err) {
		return disabled, nil
	}
	if err != nil {
		return nil, fmt.Errorf("cannot read config directory: %s", safePath(root))
	}
	type config struct {
		name, weight string
		local        bool
	}
	files := []config{}
	for _, entry := range entries {
		if match := configName.FindStringSubmatch(entry.Name()); match != nil {
			files = append(files, config{entry.Name(), strings.TrimLeft(match[1], "0"), match[2] != ""})
		}
	}
	sort.Slice(files, func(i, j int) bool {
		a, b := files[i], files[j]
		if len(a.weight) != len(b.weight) {
			return len(a.weight) < len(b.weight)
		}
		if a.weight != b.weight {
			return a.weight < b.weight
		}
		if a.local != b.local {
			return !a.local
		}
		return a.name < b.name
	})
	if len(files) == 0 {
		files = append(files, config{name: "maw.config.json"})
	}
	for _, file := range files {
		m, err := readJSON(filepath.Join(root, file.name))
		if err != nil {
			return nil, err
		}
		if array, ok := m["disabledPlugins"].([]any); ok {
			disabled = map[string]bool{}
			for _, value := range array {
				if name, ok := value.(string); ok {
					disabled[name] = true
				}
			}
		}
	}
	return disabled, nil
}
