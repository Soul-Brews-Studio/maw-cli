# Run maw

Choose one implementation. Go adds the `context` MCP command; the four ports
otherwise share the help/plugin/index contract.

## Prebuilt: no compiler or runtime

Open [Releases](https://github.com/Soul-Brews-Studio/maw-cli/releases), choose a
published alpha tag, and download one archive plus `SHA256SUMS`:

- Default Go: `maw-go-<os>-<arch>.tar.gz` (includes `context`).
- Alternatives: `maw-rs-...`, `maw-js-...`, `maw-zig-...`.
- `<os>`: `linux` or `darwin` (macOS); `<arch>`: `amd64` (x64) or `arm64`.

In a new directory, verify your selected archive before extracting:

```sh
# Example: after downloading the Linux x64 Go archive and SHA256SUMS
grep '  maw-go-linux-amd64.tar.gz$' SHA256SUMS | sha256sum -c -
tar -xzf maw-go-linux-amd64.tar.gz
./maw-go --help
```

On macOS, use `shasum -a 256 -c -` instead of `sha256sum -c -`. Every archive
contains its language-named executable and `RELEASE.json`; extract into separate directories
to keep their metadata alongside them.
Bun's prebuilt embeds its runtime. Linux builds run on Ubuntu 24.04; older
Linux/libc compatibility is not guaranteed. macOS binaries are not notarized.
Use the source commands below if platform security or compatibility blocks a binary.
A queued build is not a published download; alpha prereleases have no `/latest` alias.

## Bun / bunx: run directly from GitHub

Requires **Bun 1.3.11+**, no clone required:

```sh
bunx --bun --package 'https://github.com/Soul-Brews-Studio/maw-cli#alpha' maw-js --help
```

Use `#alpha`, not the browser URL `/tree/alpha`. Replace the fragment with an exact
commit or published release tag to pin the source. This downloads the Git package,
not a prebuilt binary or npm package. See [bunx](https://bun.com/docs/pm/bunx) and
[Bun Git dependencies](https://bun.com/docs/pm/cli/add#git-dependencies).

With npm/npx instead of an existing Bun install:

```sh
npx --yes --package=bun@1.3.11 -- bun x --bun --package 'https://github.com/Soul-Brews-Studio/maw-cli#alpha' maw-js --help
```

npx fetches Bun, then Bun runs the GitHub package; this is **not a native Node
port**. `--yes` accepts npm's install prompt. No registry package named maw-cli
is published. Both runners execute code with your user privileges.

## Go: run or install directly

Requires Go **1.22+**. No clone or GitHub authentication is needed:

```sh
go run github.com/Soul-Brews-Studio/maw-cli/src/go/cmd/maw-go@alpha --help
```

To install an executable named `maw-go`:

```sh
go install github.com/Soul-Brews-Studio/maw-cli/src/go/cmd/maw-go@alpha
```

**Check for an existing `maw-go` before installing.** Set `GOBIN` to a separate
absolute directory to avoid replacing it. Otherwise Go installs into its default
binary directory, normally `$(go env GOPATH)/bin`; add that directory to PATH.

## Local source: Bun, Rust and Zig

```sh
git clone --branch alpha https://github.com/Soul-Brews-Studio/maw-cli.git
cd maw-cli
```

Run these commands from the repository root. You need only the selected runtime.

### Bun 1.3.11

```sh
bun src/js/src/cli.ts --help
```

### Rust 1.69+

```sh
cargo run --release --locked --manifest-path src/rs/Cargo.toml -- --help
```

### Zig 0.16.0

```sh
(cd src/zig && zig build -Doptimize=ReleaseFast)
src/zig/zig-out/bin/maw-zig --help
```

## Pin a version

- `@alpha` in Go and `#alpha` in Bun follow the moving Git branch.
- An exact commit pins both runners without waiting for a release.
- Published root tags use `vYY.M.D-alpha.HMM.CI_RUN_ID`; use them after `#` in Bun.
- Go uses the release's companion version `v0.YYYYMMDD.HMM-alpha.CI_RUN_ID`,
  shown in its downloadable `release.json`; put that version after `@`.

The Go Git tag is prefixed `src/go/`, but the install selector omits that prefix.
The companion tag keeps the current Go module path valid, unlike a `v26...`
major-version tag. `@latest` prefers stable versions; it does not mean the alpha
branch. See [Go version/tag mapping](https://go.dev/ref/mod#vcs-version) and
[release automation](release.md). Running a command does not publish a release.
