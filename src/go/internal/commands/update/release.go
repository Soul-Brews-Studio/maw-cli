package update

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"regexp"
	"strconv"
	"strings"
	"time"
)

const apiOrigin = "https://api.github.com"
const downloadOrigin = "https://github.com"
const repository = "Soul-Brews-Studio/maw-cli"
const maxMetadata = 2 * 1024 * 1024
const maxBinary = 512 * 1024 * 1024
const maxArchive = maxBinary + 1024*1024

var tagPattern = regexp.MustCompile(`^v([0-9]{1,2})\.([0-9]{1,2})\.([0-9]{1,2})-alpha\.([0-9]{1,4})$`)
var commitPattern = regexp.MustCompile(`^[0-9a-f]{40}$`)
var hashPattern = regexp.MustCompile(`^[0-9a-f]{64}$`)
var goTagPattern = regexp.MustCompile(`^v0\.20([0-9]{2})([0-9]{2})([0-9]{2})\.([0-9]{1,4})-alpha$`)
var pseudoPattern = regexp.MustCompile(`[.-][0-9]{14}-([0-9a-f]{12})$`)

type publishedRelease struct {
	Tag       string `json:"tag_name"`
	Draft     bool   `json:"draft"`
	Published string `json:"published_at"`
	Assets    []struct {
		Name string `json:"name"`
		Size int64  `json:"size"`
	} `json:"assets"`
}
type releasePlan struct {
	Schema   string   `json:"schema"`
	Tag      string   `json:"tag"`
	Commit   string   `json:"commit"`
	Archives []string `json:"archives"`
}

func validURL(raw string) bool {
	u, err := url.Parse(raw)
	if err != nil || u.Scheme != "https" || u.User != nil || u.Fragment != "" {
		return false
	}
	// Origins are constants; fixture builds replace them using a Go source overlay.
	for _, origin := range []string{apiOrigin, downloadOrigin} {
		base, _ := url.Parse(origin)
		if u.Host == base.Host {
			return true
		}
	}
	if u.Port() != "" && u.Port() != "443" {
		return false
	}
	switch u.Hostname() {
	case "release-assets.githubusercontent.com", "objects.githubusercontent.com", "objects-origin.githubusercontent.com", "github-releases.githubusercontent.com":
		return true
	}
	return false
}

func download(ctx context.Context, raw string, limit int64, destination io.Writer) error {
	if !validURL(raw) {
		return fmt.Errorf("refusing non-GitHub HTTPS download")
	}
	client := &http.Client{Timeout: 90 * time.Second, CheckRedirect: func(req *http.Request, via []*http.Request) error {
		if len(via) >= 5 || !validURL(req.URL.String()) {
			return fmt.Errorf("refusing download redirect")
		}
		return nil
	}}
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, raw, nil)
	if err != nil {
		return err
	}
	req.Header.Set("User-Agent", "maw-go-update")
	req.Header.Set("Accept", "application/vnd.github+json, application/octet-stream")
	response, err := client.Do(req)
	if err != nil {
		return err
	}
	defer response.Body.Close()
	if response.StatusCode != http.StatusOK {
		return fmt.Errorf("GitHub returned HTTP %d (release may be unavailable or rate limited)", response.StatusCode)
	}
	if response.ContentLength > limit {
		return fmt.Errorf("download exceeds size limit")
	}
	n, err := io.Copy(destination, io.LimitReader(response.Body, limit+1))
	if err != nil {
		return err
	}
	if n > limit {
		return fmt.Errorf("download exceeds size limit")
	}
	return nil
}

func downloadBytes(ctx context.Context, raw string) ([]byte, error) {
	var b strings.Builder
	if err := download(ctx, raw, maxMetadata, &b); err != nil {
		return nil, err
	}
	return []byte(b.String()), nil
}

func selectRelease(ctx context.Context, tag string) (publishedRelease, error) {
	endpoint := apiOrigin + "/repos/" + repository + "/releases"
	if tag != "" {
		endpoint += "/tags/" + tag
	} else {
		endpoint += "?per_page=30"
	}
	data, err := downloadBytes(ctx, endpoint)
	if err != nil {
		return publishedRelease{}, err
	}
	var releases []publishedRelease
	if tag != "" {
		var r publishedRelease
		if err = json.Unmarshal(data, &r); err != nil {
			return r, err
		}
		if r.Tag != tag {
			return r, fmt.Errorf("release tag mismatch")
		}
		releases = append(releases, r)
	} else if err = json.Unmarshal(data, &releases); err != nil {
		return publishedRelease{}, err
	}
	var best publishedRelease
	for _, r := range releases {
		if r.Draft || r.Published == "" || !tagPattern.MatchString(r.Tag) {
			continue
		}
		if best.Tag == "" || compareTags(r.Tag, best.Tag) > 0 {
			best = r
		}
	}
	if best.Tag == "" {
		return best, fmt.Errorf("no published alpha release found in the newest 30 releases")
	}
	return best, nil
}

func assetURL(r publishedRelease, name string) string {
	return downloadOrigin + "/" + repository + "/releases/download/" + r.Tag + "/" + name
}

func releaseMetadata(ctx context.Context, r publishedRelease, archive string) (releasePlan, map[string]string, error) {
	var plan releasePlan
	for _, name := range []string{archive, "release.json", "SHA256SUMS"} {
		count := 0
		for _, a := range r.Assets {
			if a.Name == name {
				count++
				if a.Size <= 0 || a.Size > maxArchive || (name != archive && a.Size > maxMetadata) {
					return plan, nil, fmt.Errorf("invalid asset size: %s", name)
				}
			}
		}
		if count != 1 {
			return plan, nil, fmt.Errorf("release missing or duplicates asset: %s", name)
		}
	}
	data, err := downloadBytes(ctx, assetURL(r, "SHA256SUMS"))
	if err != nil {
		return plan, nil, err
	}
	sums := map[string]string{}
	for _, line := range strings.Split(strings.TrimSpace(string(data)), "\n") {
		parts := strings.Split(line, "  ")
		if len(parts) != 2 || !hashPattern.MatchString(parts[0]) || parts[1] == "" || sums[parts[1]] != "" {
			return plan, nil, fmt.Errorf("invalid SHA256SUMS")
		}
		sums[parts[1]] = parts[0]
	}
	if sums[archive] == "" || sums["release.json"] == "" {
		return plan, nil, fmt.Errorf("missing release checksum")
	}
	data, err = downloadBytes(ctx, assetURL(r, "release.json"))
	if err != nil {
		return plan, nil, err
	}
	digest := sha256.Sum256(data)
	if hex.EncodeToString(digest[:]) != sums["release.json"] {
		return plan, nil, fmt.Errorf("release.json checksum mismatch")
	}
	if err = json.Unmarshal(data, &plan); err != nil {
		return plan, nil, err
	}
	if plan.Schema != "maw.release.v1" || plan.Tag != r.Tag || !commitPattern.MatchString(plan.Commit) {
		return plan, nil, fmt.Errorf("release metadata mismatch")
	}
	for _, name := range plan.Archives {
		if name == archive {
			return plan, sums, nil
		}
	}
	return plan, nil, fmt.Errorf("archive absent from release metadata")
}

func compareTags(a, b string) int {
	x, y := tagPattern.FindStringSubmatch(a), tagPattern.FindStringSubmatch(b)
	for n := 1; n <= 4; n++ {
		xv, _ := strconv.Atoi(x[n])
		yv, _ := strconv.Atoi(y[n])
		if xv > yv {
			return 1
		}
		if xv < yv {
			return -1
		}
	}
	return 0
}

func updateStatus(ctx context.Context, current string, plan releasePlan, explicit bool) (bool, string, error) {
	if current == "dev" {
		return false, "dev build (check only)", nil
	}
	if explicit {
		return true, "explicit release selected", nil
	}
	if m := goTagPattern.FindStringSubmatch(current); m != nil {
		parts := make([]int, 4)
		for n := range parts {
			parts[n], _ = strconv.Atoi(m[n+1])
		}
		current = fmt.Sprintf("v%d.%d.%d-alpha.%d", parts[0], parts[1], parts[2], parts[3])
	}
	if tagPattern.MatchString(current) {
		switch compareTags(plan.Tag, current) {
		case 1:
			return true, "update available", nil
		case 0:
			return false, "already up to date", nil
		default:
			return false, "installed version is newer than published release", nil
		}
	}
	if m := pseudoPattern.FindStringSubmatch(current); m != nil {
		// Commit ancestry, not publication time, prevents downgrading a newer source install.
		data, err := downloadBytes(ctx, apiOrigin+"/repos/"+repository+"/compare/"+m[1]+"..."+plan.Commit+"?per_page=1")
		if err != nil {
			return false, "", err
		}
		var result struct {
			Status string `json:"status"`
			Base   struct {
				SHA string `json:"sha"`
			} `json:"base_commit"`
		}
		if err = json.Unmarshal(data, &result); err != nil {
			return false, "", err
		}
		if !commitPattern.MatchString(result.Base.SHA) || !strings.HasPrefix(result.Base.SHA, m[1]) {
			return false, "", fmt.Errorf("source commit comparison mismatch")
		}
		switch result.Status {
		case "ahead", "identical":
			return true, "verified release available for source install", nil
		case "behind", "diverged":
			return false, "source install is newer or diverged; wait for a release or select --version explicitly", nil
		default:
			return false, "", fmt.Errorf("invalid source commit comparison status")
		}
	}
	return false, "unrecognized installed version; select --version explicitly", nil
}
