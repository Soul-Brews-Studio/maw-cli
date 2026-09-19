package plugins

import (
	"fmt"
	"os"
	"strings"
)

func pluginSelector(value string, source bool) (string, string, error) {
	// Existing local directories are literal, including names with @ or #.
	if source {
		if info, err := os.Stat(value); err == nil && info.IsDir() {
			return value, "", nil
		}
		// A literal local directory may itself contain selector characters.
		if at := strings.LastIndexAny(value, "@#"); at > 0 {
			if info, err := os.Stat(value[:at]); err == nil && info.IsDir() {
				if !safeRef.MatchString(value[at+1:]) {
					return "", "", fmt.Errorf("invalid source/name selector; use @REF or #REF")
				}
				return value[:at], value[at+1:], nil
			}
		}
	}
	start := 0
	if source && strings.HasPrefix(value, "https://") {
		// An @ in URL userinfo belongs to the authority, not the selector.
		slash := strings.IndexByte(value[len("https://"):], '/')
		if slash < 0 {
			return value, "", nil
		}
		start = len("https://") + slash
	}
	at := strings.IndexAny(value[start:], "@#")
	if at < 0 {
		return value, "", nil
	}
	at += start
	name, ref := value[:at], value[at+1:]
	if name == "" || !safeRef.MatchString(ref) {
		return "", "", fmt.Errorf("invalid source/name selector; use @REF or #REF")
	}
	return name, ref, nil
}
