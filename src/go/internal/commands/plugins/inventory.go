package plugins

import (
	"encoding/json"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"regexp"
	"sort"
	"strings"
	"unicode/utf8"
)

type installed struct {
	Name, Version, Tier, Dir   string
	Enabled, CLI, API, Missing bool
}

func safePath(path string) string {
	var out strings.Builder
	for _, c := range path {
		if c < 32 || (c >= 127 && c <= 159) {
			fmt.Fprintf(&out, "\\u%04x", c)
		} else {
			out.WriteRune(c)
		}
	}
	return out.String()
}

func readJSON(path string) (map[string]any, error) {
	stat, err := os.Stat(path)
	if os.IsNotExist(err) {
		return nil, nil
	}
	invalid := fmt.Errorf("cannot read JSON metadata: %s", safePath(path))
	if err != nil || !stat.Mode().IsRegular() || stat.Size() > 1048576 {
		return nil, invalid
	}
	file, err := os.Open(path)
	if err != nil {
		return nil, invalid
	}
	defer file.Close()
	opened, err := file.Stat()
	if err != nil || !opened.Mode().IsRegular() || opened.Size() > 1048576 {
		return nil, invalid
	}
	data, err := io.ReadAll(io.LimitReader(file, 1048577))
	if err != nil || len(data) > 1048576 || !utf8.Valid(data) {
		return nil, invalid
	}
	var value map[string]any
	if json.Unmarshal(data, &value) != nil || value == nil {
		return nil, invalid
	}
	return value, nil
}

func stringField(m map[string]any, key string) string { value, _ := m[key].(string); return value }
func objectField(m map[string]any, key string) map[string]any {
	value, _ := m[key].(map[string]any)
	return value
}
func validWeight(value any) (float64, bool) {
	n, ok := value.(float64)
	return n, ok && n >= 0 && n <= 99
}
func tierRank(tier string) int {
	if tier == "core" {
		return 0
	}
	if tier == "standard" {
		return 1
	}
	return 2
}

func paths() (string, string, error) {
	env := func(key, fallback string) string {
		if value := os.Getenv(key); value != "" {
			return value
		}
		return fallback
	}
	home := env("HOME", os.Getenv("USERPROFILE"))
	xdg := false
	switch strings.ToLower(os.Getenv("MAW_XDG")) {
	case "1", "true", "yes", "on":
		xdg = true
	}
	if home == "" && ((os.Getenv("MAW_PLUGINS_DIR") == "" && os.Getenv("MAW_HOME") == "" && os.Getenv("MAW_DATA_DIR") == "" && !(xdg && os.Getenv("XDG_DATA_HOME") != "")) || (os.Getenv("MAW_HOME") == "" && os.Getenv("MAW_CONFIG_DIR") == "" && os.Getenv("XDG_CONFIG_HOME") == "")) {
		return "", "", fmt.Errorf("HOME is not set; provide explicit plugin and config roots")
	}
	data := filepath.Join(home, ".maw")
	switch strings.ToLower(os.Getenv("MAW_XDG")) {
	case "1", "true", "yes", "on":
		data = filepath.Join(env("XDG_DATA_HOME", filepath.Join(home, ".local", "share")), "maw")
	}
	data = env("MAW_HOME", env("MAW_DATA_DIR", data))
	plugins, err := filepath.Abs(env("MAW_PLUGINS_DIR", filepath.Join(data, "plugins")))
	if err != nil {
		return "", "", err
	}
	config := env("MAW_CONFIG_DIR", filepath.Join(env("XDG_CONFIG_HOME", filepath.Join(home, ".config")), "maw"))
	if value := os.Getenv("MAW_HOME"); value != "" {
		config = filepath.Join(value, "config")
	}
	config, err = filepath.Abs(config)
	return plugins, config, err
}

func scanInstalled(root string, disabled map[string]bool, stderr io.Writer) ([]installed, error) {
	overrides, err := readJSON(filepath.Join(root, ".overrides.json"))
	if err != nil {
		return nil, err
	}
	entries, err := os.ReadDir(root)
	if os.IsNotExist(err) {
		return nil, nil
	}
	if err != nil {
		return nil, fmt.Errorf("cannot read plugin directory: %s", safePath(root))
	}
	found := map[string]bool{}
	plugins := []installed{}
	for _, entry := range entries {
		dir := filepath.Join(root, entry.Name())
		stat, err := os.Stat(dir)
		if err != nil || !stat.IsDir() {
			continue
		}
		m, err := readJSON(filepath.Join(dir, "plugin.json"))
		if err == nil && m == nil {
			if _, e := os.Stat(filepath.Join(dir, "plugin.ts")); e == nil {
				fmt.Fprintf(stderr, "maw: skipped TypeScript-only manifest: %s\n", safePath(dir))
			}
			continue
		}
		name, version := stringField(m, "name"), stringField(m, "version")
		valid := err == nil && pluginName.MatchString(name) && version != "" && safePath(version) == version
		tier := stringField(m, "tier")
		if _, exists := m["tier"]; exists && tier != "core" && tier != "standard" && tier != "extra" {
			valid = false
		}
		weight := float64(50)
		if value, exists := m["weight"]; exists {
			var ok bool
			weight, ok = validWeight(value)
			valid = valid && ok
		}
		if !valid {
			fmt.Fprintf(stderr, "maw: skipped invalid plugin.json: %s\n", safePath(dir))
			continue
		}
		if found[name] {
			continue
		}
		found[name] = true
		if value, ok := validWeight(overrides[name]); ok {
			weight = value
		}
		if tier == "" {
			if weight < 10 {
				tier = "core"
			} else if weight < 50 {
				tier = "standard"
			} else {
				tier = "extra"
			}
		}
		executable := stringField(m, "entry")
		if executable == "" && stringField(m, "target") != "wasm" {
			executable = stringField(objectField(m, "artifact"), "path")
		}
		if executable == "" {
			executable = stringField(m, "wasm")
		}
		p := installed{Name: name, Version: version, Tier: tier, Dir: dir, Enabled: !disabled[name], CLI: objectField(m, "cli") != nil || executable != "", API: objectField(m, "api") != nil}
		p.Missing = p.CLI && executable == ""
		if executable != "" {
			if !filepath.IsAbs(executable) {
				executable = filepath.Join(dir, executable)
			}
			stat, err := os.Stat(executable)
			p.Missing = err != nil || !stat.Mode().IsRegular()
		}
		plugins = append(plugins, p)
	}
	sort.Slice(plugins, func(i, j int) bool {
		if plugins[i].Tier != plugins[j].Tier {
			return tierRank(plugins[i].Tier) < tierRank(plugins[j].Tier)
		}
		return plugins[i].Name < plugins[j].Name
	})
	return plugins, nil
}

var pluginName = regexp.MustCompile(`^[A-Za-z0-9._-]+$`)
