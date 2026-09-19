package plugins

import (
	"archive/tar"
	"bytes"
	"compress/gzip"
	"fmt"
	"io"
	"os"
	"path"
	"path/filepath"
	"strings"
	"unicode/utf8"
)

func extractArchive(input io.Reader, dir string) error {
	compressed := &io.LimitedReader{R: input, N: archiveDownloadLimit + 1}
	gz, err := gzip.NewReader(compressed)
	if err != nil {
		return fmt.Errorf("invalid gzip archive: %w", err)
	}
	defer gz.Close()
	expanded := &io.LimitedReader{R: gz, N: (512 << 20) + 1}
	reader := tar.NewReader(expanded)
	seen := map[string]bool{}
	for count := 0; ; count++ {
		h, err := reader.Next()
		if err == io.EOF {
			break
		}
		if err != nil {
			return fmt.Errorf("invalid tar archive: %w", err)
		}
		if count >= 4096 || h.Size < 0 || h.Size > 512<<20 {
			return fmt.Errorf("archive exceeds entry or size limit")
		}
		// GitHub archives carry a global PAX commit comment, not a filesystem entry.
		if h.Typeflag == tar.TypeXGlobalHeader {
			continue
		}
		name := h.Name
		if !utf8.ValidString(name) || len(name) > 4096 || safePath(name) != name || strings.Contains(name, "\\") || path.IsAbs(name) {
			return fmt.Errorf("unsafe archive path")
		}
		for _, part := range strings.Split(name, "/") {
			if part == ".." || strings.EqualFold(part, ".git") {
				return fmt.Errorf("unsafe archive path: %s", safePath(name))
			}
		}
		name = path.Clean(name)
		if (h.Typeflag != tar.TypeDir && h.Typeflag != tar.TypeReg) || (name == "." && h.Typeflag != tar.TypeDir) {
			return fmt.Errorf("archive contains a link or unsupported file type")
		}
		if seen[name] {
			return fmt.Errorf("duplicate archive path: %s", name)
		}
		seen[name] = true
		target := filepath.Join(dir, filepath.FromSlash(name))
		if h.Typeflag == tar.TypeDir {
			if err = os.MkdirAll(target, 0755); err != nil {
				return err
			}
			continue
		}
		if err = os.MkdirAll(filepath.Dir(target), 0755); err != nil {
			return err
		}
		mode := os.FileMode(0644)
		if h.Mode&0111 != 0 {
			mode = 0755
		}
		file, err := os.OpenFile(target, os.O_WRONLY|os.O_CREATE|os.O_EXCL, mode)
		if err != nil {
			return err
		}
		_, copyErr := io.Copy(file, reader)
		closeErr := file.Close()
		if copyErr != nil {
			return copyErr
		}
		if closeErr != nil {
			return closeErr
		}
	}
	// Finish gzip to check its CRC; tar EOF alone does not validate the trailer.
	buffer := make([]byte, 32768)
	for {
		n, err := expanded.Read(buffer)
		if len(bytes.Trim(buffer[:n], "\x00")) != 0 {
			return fmt.Errorf("unexpected data after tar archive")
		}
		if err == io.EOF {
			break
		}
		if err != nil {
			return fmt.Errorf("invalid gzip trailer: %w", err)
		}
	}
	if compressed.N <= 0 || expanded.N <= 0 {
		return fmt.Errorf("archive exceeds compressed or extracted size limit")
	}
	return nil
}
