# Run maw

Choose one implementation. Go adds the `context` MCP command; the four ports
otherwise share the help/plugin/index contract.

## Go: run or install directly

Requires Go **1.22+**. No clone or GitHub authentication is needed:

```sh
go run github.com/Soul-Brews-Studio/maw-herdr/src/go/cmd/maw@alpha --help
```

To install an executable named `maw`:

```sh
go install github.com/Soul-Brews-Studio/maw-herdr/src/go/cmd/maw@alpha
```

**Check for an existing `maw` before installing.** Set `GOBIN` to a separate
absolute directory to avoid replacing it. Otherwise Go installs into its default
binary directory, normally `$(go env GOPATH)/bin`; add that directory to PATH.

## Bun, npx, Rust and Zig: clone first

```sh
git clone --branch alpha https://github.com/Soul-Brews-Studio/maw-herdr.git
cd maw-herdr
```

Run these commands from the repository root. You need only the selected runtime.

### Bun 1.3.11

```sh
bun src/js/src/cli.ts --help
```

### bunx / npx: select Bun

With bunx or npm/npx installed, choose one:

```sh
bunx --bun --package bun@1.3.11 bun src/js/src/cli.ts --help
```

```sh
npx --yes --package=bun@1.3.11 -- bun src/js/src/cli.ts --help
```

Both commands fetch Bun and run the cloned TypeScript source, not a published
maw package. The npx command is **not** a native Node implementation; `--yes`
accepts npm's install prompt. Plain `bun` is simpler if you already have it.

### Rust 1.69+

```sh
cargo run --release --locked --manifest-path src/rs/Cargo.toml -- --help
```

### Zig 0.16.0

```sh
(cd src/zig && zig build -Doptimize=ReleaseFast)
src/zig/zig-out/bin/maw-zig --help
```

### Direct package runners

| Runner | Direct maw package available? |
| --- | --- |
| `bunx` | No; the example above selects Bun, not maw |
| `npx` | No; the example above installs Bun, not maw |

See [bunx](https://bun.sh/docs/pm/bunx) and
[npm exec](https://docs.npmjs.com/cli/v11/commands/npm-exec/) for runner behavior.

The repository has no root `package.json`. `src/js/package.json` is private and
has no `bin` entry. Direct runners need package metadata and an executable
entrypoint; this repository is not packaged for that yet. Do not substitute an
unrelated registry package with a similar name.

## Pin a version

- `@alpha` is a moving Git branch, not an immutable release.
- Go accepts an exact Git commit after `@`; source users can check out that commit.
- Calendar-versioned alpha tags are possible, but **none are published yet**.

For example, a future nested-module Git tag `src/go/v0.20260919.1020-alpha` would
allow `@v0.20260919.1020-alpha` on the Go command path. This is a **proposed example,
not a runnable released version**. A plain major-version `v26...` module tag would
require a matching `/v26` module path; a repository CalVer label alone does not
make the existing Go module installable at that semantic version.

See [Go module versions](https://go.dev/ref/mod#versions),
[nested-module tags](https://go.dev/ref/mod#vcs-version), and our
[gated release workflow](release.md). No npm publication, tag or release is
performed by these run commands.
