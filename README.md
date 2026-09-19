# maw-cli

A help-first CLI: `maw-go`, `maw-rs`, `maw-js` and `maw-zig`.
Modular built-ins and external executable plugins; no tmux service or agent engine.

## Run maw

Choose one implementation. Go adds the `context` MCP command; the four ports
otherwise share the help/version/plugin contract.

### Prebuilt: no compiler or runtime

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

### Bun / bunx: run directly from GitHub

Requires **Bun 1.3.11+**, no clone required:

```sh
bunx --bun --package 'https://github.com/Soul-Brews-Studio/maw-cli#alpha' maw-js --help
```

Use `#alpha`, not the browser URL `/tree/alpha`. Replace the fragment with an exact
commit or published release tag to pin the source. This downloads the Git package,
not a prebuilt binary or npm package. See [bunx](https://bun.com/docs/pm/bunx) and
[Bun Git dependencies](https://bun.com/docs/pm/cli/add#git-dependencies).

Bun may reuse a cached `#alpha` checkout. To fetch current alpha without clearing
other packages, use a fresh temporary cache (verified with Bun 1.3.11):

```sh
(
  fresh=$(mktemp -d) || exit
  trap 'rm -rf "$fresh"' EXIT
  TMPDIR="$fresh" bunx --bun --package 'https://github.com/Soul-Brews-Studio/maw-cli#alpha' maw-js plugin ls
)
```

This bypasses bunx's [temporary executable cache](https://github.com/oven-sh/bun/blob/a04817ce2b7f1a1e8b7cbf8af8f2c027ab072f1d/src/cli/bunx_command.zig#L474-L534).

With npm/npx instead of an existing Bun install:

```sh
npx --yes --package=bun@1.3.11 -- bun x --bun --package 'https://github.com/Soul-Brews-Studio/maw-cli#alpha' maw-js --help
```

npx fetches Bun, then Bun runs the GitHub package; this is **not a native Node
port**. `--yes` accepts npm's install prompt. No registry package named maw-cli
is published. Both runners execute code with your user privileges.

### Go: run or install directly

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

### Local source: Bun, Rust and Zig

```sh
git clone --branch alpha https://github.com/Soul-Brews-Studio/maw-cli.git
cd maw-cli
```

Run these commands from the repository root. You need only the selected runtime.

#### Bun 1.3.11

```sh
bun src/js/src/cli.ts --help
```

#### Rust 1.69+

```sh
cargo run --release --locked --manifest-path src/rs/Cargo.toml -- --help
```

#### Zig 0.16.0

```sh
(cd src/zig && zig build -Doptimize=ReleaseFast)
src/zig/zig-out/bin/maw-zig --help
```

### Pin a version

- `@alpha` in Go and `#alpha` in Bun follow the moving Git branch.
- An exact commit pins both runners without waiting for a release.
- New alpha releases use `vYY.M.D-alpha.HMM`; use published tags after `#` in Bun.
- Go uses the release's companion version `v0.YYYYMMDD.HMM-alpha`,
  shown in its downloadable `release.json`; put that version after `@`.

Tags use the source CI run's creation time in Bangkok. `HMM` is hour × 100 +
minute without leading zeros: 09:37 becomes `937`. CI run IDs are metadata only.

The Go Git tag is prefixed `src/go/`, but the install selector omits that prefix.
The companion tag keeps the current Go module path valid, unlike a `v26...`
major-version tag. `@latest` prefers stable versions; it does not mean the alpha
branch. See [Go version/tag mapping](https://go.dev/ref/mod#vcs-version) and
[release automation](docs/release.md). Running a command does not publish a release.

[Prebuilt builds](https://github.com/Soul-Brews-Studio/maw-cli/actions/workflows/release.yml)
run in the background after successful alpha CI.

## Commands

List installed plugins from `~/.maw/plugins` without loading or running them:

```sh
bunx --bun --package 'https://github.com/Soul-Brews-Studio/maw-cli#alpha' maw-js plugin ls
```

`plugins ls` and the original `plugins` are equivalent aliases. Default output
shows active/disabled totals, tiers, CLI/API metadata, entry-file health and names.
Add `-v` for `name`, `version`, `tier`, `enabled|disabled`, and directory rows;
add `--all` to include disabled plugins.

```sh
bunx --bun --package 'https://github.com/Soul-Brews-Studio/maw-cli#alpha' maw-js plugins ls -v
```

This is a **read-only JSON inventory**, not the old maw runtime loader. It reads
`plugin.json` only; TypeScript-only manifests are reported and skipped. Global
path/config overrides are supported; project overlays, active profiles and
runtime compatibility/hash validation are not. `health: ok` checks file existence,
not whether plugins are safe or runnable. See the [inventory contract](docs/installed-plugin-listing.md).
Built-ins and PATH commands remain visible in `help`. No installation or state
changes are included.

All ports provide `help`, `version`, `plugin ls`, and external `maw <plugin> [args...]`.
The former benchmark-only `index` command has been removed. Go also provides
[`context`](docs/mcp.md) through local Serena and CodeGraph MCP servers. Plugins
run with your privileges, not in a sandbox.

## Repository

- `src/` — `go/`, `rs/`, `js/`, `zig/`
- `docs/` — guides and benchmark reports
- `utils/` — scripts and modular `just` tasks

[Development](docs/development.md) · [Plugins](docs/plugins.md) ·
[Architecture](docs/architecture.md) · [Benchmarks](docs/benchmarks/cli/README.md) ·
[Release workflow](docs/release.md)
