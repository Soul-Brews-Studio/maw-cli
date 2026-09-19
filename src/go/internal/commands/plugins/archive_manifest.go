package plugins

import (
	"bytes"
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"strings"
)

func archiveManifest(dir string) (string, string, error) {
	if _, err := os.Lstat(filepath.Join(dir, "plugin.json")); os.IsNotExist(err) {
		entries, e := os.ReadDir(dir)
		if e != nil || len(entries) != 1 || !entries[0].IsDir() {
			return "", "", fmt.Errorf("archive needs plugin.json at its root or inside one wrapper directory")
		}
		dir = filepath.Join(dir, entries[0].Name())
	}
	m, err := readJSON(filepath.Join(dir, "plugin.json"))
	if err != nil || m == nil {
		return "", "", fmt.Errorf("archive has invalid or missing plugin.json")
	}
	name, entry, err := manifestEntry(m)
	if err != nil {
		return "", "", err
	}
	if err = regularEntry(dir, entry); err != nil {
		return "", "", err
	}
	artifacts := []any{}
	if artifact, ok := m["artifact"]; ok {
		artifacts = append(artifacts, artifact)
	}
	if value, ok := m["bundledArtifacts"]; ok {
		bundled, valid := value.([]any)
		if !valid {
			return "", "", fmt.Errorf("invalid bundledArtifacts")
		}
		artifacts = append(artifacts, bundled...)
	}
	seen := map[string]bool{}
	remaining := int64(512 << 20)
	for _, value := range artifacts {
		artifact, ok := value.(map[string]any)
		file := stringField(artifact, "path")
		expected, err := hex.DecodeString(strings.TrimPrefix(stringField(artifact, "sha256"), "sha256:"))
		if !ok || !lifecycleEntry(file) || err != nil || len(expected) != sha256.Size {
			return "", "", fmt.Errorf("invalid artifact path or SHA-256")
		}
		if seen[file] {
			return "", "", fmt.Errorf("duplicate artifact path")
		}
		seen[file] = true
		if err = regularEntry(dir, file); err != nil {
			return "", "", err
		}
		f, err := os.Open(filepath.Join(dir, file))
		if err != nil {
			return "", "", err
		}
		hash := sha256.New()
		n, err := io.Copy(hash, io.LimitReader(f, remaining+1))
		f.Close()
		remaining -= n
		if err != nil || remaining < 0 || !bytes.Equal(hash.Sum(nil), expected) {
			return "", "", fmt.Errorf("artifact SHA-256 mismatch: %s", file)
		}
	}
	return dir, name, nil
}
