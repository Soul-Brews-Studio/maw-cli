package plugins

import (
	"io"
	"sort"
	"strings"
)

// HelpPlugin is one installed plugin as root help lists it (#53).
type HelpPlugin struct {
	Command, Summary string
	Aliases          []string
}

// HelpPlugins resolves installed plugins the way dispatch does, reading
// manifests only. The inventory already holds one plugin per manifest name, and
// dispatch takes the first plugin in tier/name order declaring a command, so a
// later plugin declaring the same command is never returned. Enabled plugins
// come back sorted by command; disabled ones are only counted. Aliases keep only
// words that reach the plugin (#55): typeable, not a plugin command, and
// declared by no other enabled plugin, since such an alias runs neither.
func HelpPlugins(stderr io.Writer) ([]HelpPlugin, int, error) {
	root, config, err := paths()
	if err != nil {
		return nil, 0, err
	}
	disabled, err := disabledPlugins(config)
	if err != nil {
		return nil, 0, err
	}
	inventory, err := scanInstalled(root, disabled, stderr)
	if err != nil {
		return nil, 0, err
	}
	claimed, holders := map[string]bool{}, map[string]int{}
	var enabled []installed
	off := 0
	for _, p := range inventory {
		if p.Enabled {
			seen := map[string]bool{}
			for _, alias := range p.Aliases {
				if !seen[alias] {
					seen[alias] = true
					holders[alias]++
				}
			}
		}
		if !typeable(p.Command) || claimed[p.Command] {
			continue
		}
		claimed[p.Command] = true
		if p.Enabled {
			enabled = append(enabled, p)
		} else {
			off++
		}
	}
	result := []HelpPlugin{}
	for _, p := range enabled {
		entry := HelpPlugin{Command: p.Command, Summary: oneLine(p.Description)}
		if entry.Summary == "" {
			entry.Summary = oneLine(p.Help)
		}
		seen := map[string]bool{}
		for _, alias := range p.Aliases {
			if typeable(alias) && !claimed[alias] && holders[alias] == 1 && !seen[alias] {
				seen[alias] = true
				entry.Aliases = append(entry.Aliases, alias)
			}
		}
		result = append(result, entry)
	}
	sort.Slice(result, func(i, j int) bool { return result[i].Command < result[j].Command })
	return result, off, nil
}

// typeable reports whether dispatch would ever look an installed plugin up by word.
func typeable(word string) bool {
	return commandName.MatchString(word) && word != "go" && word != "rs" && word != "js" && word != "zig" && word != "index"
}

// oneLine is the first non-empty line of text with control characters
// (terminal escapes included) blanked.
func oneLine(text string) string {
	text = strings.TrimSpace(text)
	if end := strings.IndexAny(text, "\r\n"); end >= 0 {
		text = text[:end]
	}
	return strings.TrimSpace(strings.Map(func(c rune) rune {
		if c < 32 || (c >= 127 && c <= 159) {
			return ' '
		}
		return c
	}, text))
}
