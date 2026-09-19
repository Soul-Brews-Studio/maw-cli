package update

import (
	"archive/tar"
	"bytes"
	"compress/gzip"
	"context"
	"crypto/sha256"
	"encoding/binary"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"io"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"time"
)

func installRelease(ctx context.Context, r publishedRelease, plan releasePlan, sum, asset string) (string, error) {
	target, err := os.Executable()
	if err != nil {
		return "", err
	}
	target, err = filepath.EvalSymlinks(target)
	if err != nil {
		return "", err
	}
	original, err := os.Lstat(target)
	if err != nil {
		return "", err
	}
	if !original.Mode().IsRegular() || original.Mode()&(os.ModeSetuid|os.ModeSetgid) != 0 {
		return "", fmt.Errorf("refusing non-regular or privileged executable")
	}
	lock := target + ".update-lock"
	if err = os.Mkdir(lock, 0700); err != nil {
		return "", fmt.Errorf("cannot lock %s (another update, stale lock, or directory not writable): %w", target, err)
	}
	defer os.Remove(lock)
	stage, err := os.MkdirTemp(filepath.Dir(target), ".maw-go-update-")
	if err != nil {
		return "", err
	}
	defer os.RemoveAll(stage)
	archive, err := os.OpenFile(filepath.Join(stage, "archive.tar.gz"), os.O_CREATE|os.O_EXCL|os.O_RDWR, 0600)
	if err != nil {
		return "", err
	}
	defer archive.Close()
	hash := sha256.New()
	if err = download(ctx, assetURL(r, asset), maxArchive, io.MultiWriter(archive, hash)); err != nil {
		return "", err
	}
	if hex.EncodeToString(hash.Sum(nil)) != sum {
		return "", fmt.Errorf("archive checksum mismatch; original executable unchanged")
	}
	if _, err = archive.Seek(0, io.SeekStart); err != nil {
		return "", err
	}
	candidate := filepath.Join(stage, "maw-go")
	if err = unpack(archive, candidate, plan); err != nil {
		return "", err
	}
	if err = proveCandidate(ctx, candidate, plan.Tag); err != nil {
		return "", err
	}
	now, err := os.Lstat(target)
	if err != nil {
		return "", err
	}
	if !os.SameFile(original, now) || original.Size() != now.Size() || !original.ModTime().Equal(now.ModTime()) {
		return "", fmt.Errorf("installed executable changed during update; refusing replacement")
	}
	if err = ctx.Err(); err != nil {
		return "", err
	}
	// Candidate is proven first; one same-filesystem rename replaces the old name without a gap.
	if err = os.Rename(candidate, target); err != nil {
		return "", err
	}
	return target, nil
}

func unpack(archive io.Reader, candidate string, plan releasePlan) error {
	zipped, err := gzip.NewReader(archive)
	if err != nil {
		return err
	}
	defer zipped.Close()
	// Bound the entire decompressed stream, including hidden tar headers/padding.
	bounded := &io.LimitedReader{R: zipped, N: maxBinary + 1024*1024}
	reader := tar.NewReader(bounded)
	seen := map[string]bool{}
	var metadata struct{ Tag, Commit, Language, OS, Arch, SHA256 string }
	var binaryDigest string
	for {
		h, err := reader.Next()
		if err == io.EOF {
			break
		}
		if err != nil {
			return err
		}
		if (h.Name != "maw-go" && h.Name != "RELEASE.json") || seen[h.Name] || h.Format != tar.FormatUSTAR || (h.Typeflag != tar.TypeReg && h.Typeflag != tar.TypeRegA) || h.Size < 0 {
			return fmt.Errorf("unsafe or unexpected archive member")
		}
		seen[h.Name] = true
		if h.Name == "RELEASE.json" {
			if h.Size > 16384 {
				return fmt.Errorf("archive metadata too large")
			}
			data, err := io.ReadAll(reader)
			if err != nil {
				return err
			}
			if err = json.Unmarshal(data, &metadata); err != nil {
				return err
			}
			continue
		}
		if h.Size < 32 || h.Size > maxBinary || h.Mode != 0755 {
			return fmt.Errorf("invalid executable size or permissions")
		}
		var header [32]byte
		if _, err = io.ReadFull(reader, header[:]); err != nil {
			return err
		}
		if !validHeader(header[:]) {
			return fmt.Errorf("binary format/architecture mismatch")
		}
		file, err := os.OpenFile(candidate, os.O_CREATE|os.O_EXCL|os.O_WRONLY, 0600)
		if err != nil {
			return err
		}
		digest := sha256.New()
		_, copyErr := io.Copy(io.MultiWriter(file, digest), io.MultiReader(bytes.NewReader(header[:]), reader))
		if copyErr == nil {
			copyErr = file.Sync()
		}
		closeErr := file.Close()
		if copyErr != nil {
			return copyErr
		}
		if closeErr != nil {
			return closeErr
		}
		binaryDigest = hex.EncodeToString(digest.Sum(nil))
	}
	// tar EOF can precede the gzip footer. Drain to validate CRC and reject trailing payloads.
	var padding [4096]byte
	for {
		n, err := bounded.Read(padding[:])
		for _, b := range padding[:n] {
			if b != 0 {
				return fmt.Errorf("unexpected trailing archive data")
			}
		}
		if err == io.EOF {
			break
		}
		if err != nil {
			return err
		}
	}
	if bounded.N == 0 {
		return fmt.Errorf("decompressed archive exceeds size limit")
	}
	if len(seen) != 2 || metadata.Tag != plan.Tag || metadata.Commit != plan.Commit || metadata.Language != "go" || metadata.OS != runtime.GOOS || metadata.Arch != runtime.GOARCH || metadata.SHA256 != binaryDigest || binaryDigest == "" {
		return fmt.Errorf("archive metadata/binary checksum mismatch")
	}
	return os.Chmod(candidate, 0755)
}

func validHeader(h []byte) bool {
	if runtime.GOOS == "linux" {
		machine := uint16(62)
		if runtime.GOARCH == "arm64" {
			machine = 183
		}
		kind := binary.LittleEndian.Uint16(h[16:18])
		return bytes.Equal(h[:7], []byte{127, 'E', 'L', 'F', 2, 1, 1}) && (kind == 2 || kind == 3) && binary.LittleEndian.Uint16(h[18:20]) == machine
	}
	cpu := uint32(0x01000007)
	if runtime.GOARCH == "arm64" {
		cpu = 0x0100000c
	}
	return bytes.Equal(h[:4], []byte{0xcf, 0xfa, 0xed, 0xfe}) && binary.LittleEndian.Uint32(h[4:8]) == cpu && binary.LittleEndian.Uint32(h[12:16]) == 2
}

type proofOutput struct{ data bytes.Buffer }

func (b *proofOutput) Write(p []byte) (int, error) {
	if b.data.Len()+len(p) > 4096 {
		return 0, fmt.Errorf("candidate version output too large")
	}
	return b.data.Write(p)
}

func proveCandidate(ctx context.Context, path, tag string) error {
	ctx, cancel := context.WithTimeout(ctx, 5*time.Second)
	defer cancel()
	cmd := exec.CommandContext(ctx, path, "version")
	cmd.Dir = filepath.Dir(path)
	cmd.Env = []string{"PATH=", "HOME=" + filepath.Dir(path)}
	cmd.WaitDelay = time.Second
	var stdout, stderr proofOutput
	cmd.Stdout, cmd.Stderr = &stdout, &stderr
	if err := cmd.Run(); err != nil {
		return fmt.Errorf("candidate version check failed; original executable unchanged: %w", err)
	}
	if stdout.data.String() != "maw "+tag+"\n" || stderr.data.Len() != 0 {
		return fmt.Errorf("candidate version mismatch; original executable unchanged")
	}
	return nil
}
