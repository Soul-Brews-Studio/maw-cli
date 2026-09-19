package plugins

import (
	"context"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"os"
	"path/filepath"
	"strings"
	"time"

	"github.com/Soul-Brews-Studio/maw-cli/src/go/internal/command"
)

const archiveDownloadLimit = 128 << 20

func archiveSource(source string) bool {
	// Existing directories retain the Git-directory contract, even with this suffix.
	if info, err := os.Stat(source); err == nil && info.IsDir() {
		return false
	}
	if u, err := url.Parse(source); err == nil && u.Scheme != "" {
		source = u.Path
	}
	return strings.HasSuffix(strings.ToLower(source), ".tar.gz") || strings.HasSuffix(strings.ToLower(source), ".tgz")
}

func archiveInstall(ctx context.Context, i *command.Invocation) int {
	mode := ""
	if len(i.Args) == 3 && (i.Args[2] == "--backup" || i.Args[2] == "--replace") {
		mode = strings.TrimPrefix(i.Args[2], "--")
	} else if len(i.Args) != 2 {
		return i.Fail("usage: maw plugin install FILE.tar.gz|HTTPS.tar.gz [--backup|--replace]")
	}
	root, _, err := paths()
	if err == nil {
		err = installArchive(ctx, root, i.Args[1], mode, i)
	}
	if err != nil {
		fmt.Fprintln(i.Stderr, "maw:", err)
		return 1
	}
	return 0
}

func openArchive(ctx context.Context, source string) (io.ReadCloser, error) {
	if safePath(source) != source {
		return nil, fmt.Errorf("invalid archive source")
	}
	u, err := url.Parse(source)
	if err != nil {
		return nil, fmt.Errorf("invalid archive URL")
	}
	if u.Scheme == "" {
		info, err := os.Stat(source)
		if err != nil || !info.Mode().IsRegular() || info.Size() > archiveDownloadLimit {
			return nil, fmt.Errorf("archive must be a regular file of at most 128 MiB")
		}
		f, err := os.Open(source)
		if err != nil {
			return nil, err
		}
		info, err = f.Stat()
		if err != nil || !info.Mode().IsRegular() || info.Size() > archiveDownloadLimit {
			f.Close()
			return nil, fmt.Errorf("archive must be a regular file of at most 128 MiB")
		}
		return f, nil
	}
	if u.Scheme != "https" || u.Host == "" || u.User != nil || u.Fragment != "" {
		return nil, fmt.Errorf("archive URL must use HTTPS without credentials or a fragment")
	}
	client := &http.Client{Timeout: 2 * time.Minute, CheckRedirect: func(req *http.Request, via []*http.Request) error {
		if len(via) >= 5 || req.URL.Scheme != "https" || req.URL.User != nil {
			return fmt.Errorf("unsafe archive redirect")
		}
		return nil
	}}
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, source, nil)
	if err != nil {
		return nil, err
	}
	req.Header.Set("User-Agent", "maw-go-plugin-installer")
	response, err := client.Do(req)
	if err != nil {
		return nil, err
	}
	if response.StatusCode != http.StatusOK || response.ContentLength > archiveDownloadLimit {
		response.Body.Close()
		return nil, fmt.Errorf("archive download failed: HTTP %d or size exceeds 128 MiB", response.StatusCode)
	}
	return response.Body, nil
}

func installArchive(ctx context.Context, root, source, mode string, i *command.Invocation) error {
	input, err := openArchive(ctx, source)
	if err != nil {
		return err
	}
	defer input.Close()
	if err = os.MkdirAll(root, 0700); err != nil {
		return err
	}
	// Resolve configured symlink roots before choosing the sibling backup directory.
	root, err = filepath.EvalSymlinks(root)
	if err != nil {
		return err
	}
	stage, err := os.MkdirTemp(root, ".install-")
	if err != nil {
		return err
	}
	keepStage := false
	defer func() {
		if !keepStage {
			os.RemoveAll(stage)
		}
	}()
	dir := filepath.Join(stage, "package")
	if err = os.Mkdir(dir, 0700); err != nil {
		return err
	}
	if err = extractArchive(input, dir); err != nil {
		return err
	}
	dir, name, err := archiveManifest(dir)
	if err != nil {
		return err
	}
	keepStage, err = promoteArchive(root, stage, dir, name, mode, i)
	return err
}
