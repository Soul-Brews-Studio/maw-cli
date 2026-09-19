package contextcmd

import (
	"bytes"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"strings"

	"github.com/Soul-Brews-Studio/maw-herdr/src/go/internal/mcp"
)

type configuration struct {
	Serena    mcp.ServerConfig `json:"serena"`
	CodeGraph mcp.ServerConfig `json:"codegraph"`
}

func loadConfig(path string) (configuration, error) {
	var config configuration
	file, err := os.Open(path)
	if err != nil {
		return config, fmt.Errorf("read --config (or MAW_MCP_CONFIG): %w", err)
	}
	defer file.Close()
	data, err := io.ReadAll(io.LimitReader(file, 1024*1024+1))
	if err != nil {
		return config, err
	}
	if len(data) > 1024*1024 {
		return config, errors.New("MCP config exceeds 1 MiB")
	}
	decoder := json.NewDecoder(bytes.NewReader(data))
	decoder.DisallowUnknownFields()
	if err := decoder.Decode(&config); err != nil {
		return config, fmt.Errorf("MCP config: %w", err)
	}
	if err := decoder.Decode(new(any)); err != io.EOF {
		return config, errors.New("MCP config must contain exactly one JSON object")
	}
	if config.Serena.Command == "" || config.CodeGraph.Command == "" {
		return config, errors.New("MCP config requires serena.command and codegraph.command")
	}
	return config, nil
}

func sourcePath(project, file string) (string, error) {
	root, err := filepath.Abs(project)
	if err != nil {
		return "", err
	}
	root, err = filepath.EvalSymlinks(root)
	if err != nil {
		return "", fmt.Errorf("project: %w", err)
	}
	info, err := os.Stat(root)
	if err != nil || !info.IsDir() {
		return "", errors.New("project must be an existing directory")
	}
	if file != "" {
		if filepath.IsAbs(file) {
			return "", errors.New("--file must be project-relative")
		}
		resolved, err := filepath.EvalSymlinks(filepath.Join(root, file))
		if err != nil {
			return "", fmt.Errorf("file: %w", err)
		}
		relative, err := filepath.Rel(root, resolved)
		if err != nil || relative == ".." || strings.HasPrefix(relative, ".."+string(filepath.Separator)) {
			return "", errors.New("--file must stay inside the project")
		}
	}
	return root, nil
}
