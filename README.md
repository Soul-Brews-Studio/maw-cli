# maw-cli

A help-first CLI: `maw-go`, `maw-rs`, `maw-js` and `maw-zig`.
Modular built-ins and external executable plugins; no tmux service or agent engine.

## Run from GitHub

With **Bun**, no clone required:

```sh
bunx --bun --package 'https://github.com/Soul-Brews-Studio/maw-cli#alpha' maw-js --help
```

With **Go 1.22+**, no clone required:

```sh
go run github.com/Soul-Brews-Studio/maw-cli/src/go/cmd/maw-go@alpha --help
```

`@alpha` follows development. Use an exact commit to pin a revision;
CI automatically publishes immutable CalVer alpha prereleases.

## Choose a runtime

| Runtime | How to run |
| --- | --- |
| None | [Prebuilt downloads](https://github.com/Soul-Brews-Studio/maw-cli/releases): Linux/macOS, x64/ARM64 |
| Go | Run directly from GitHub above, or install `maw-go` |
| Bun / bunx | Run directly from GitHub above |
| npx | Use npx to run Bun + the GitHub package; see guide |
| Rust / Zig | Clone and compile their independent ports |

**[Run and install guide →](docs/running.md)** — exact commands and version pinning.
No npm publication is needed: bunx downloads the GitHub source.
[Prebuilt builds](https://github.com/Soul-Brews-Studio/maw-cli/actions/workflows/release.yml)
run in the background after successful alpha CI.

## Commands

All ports provide `help`, `version`, `plugins`, `index FILE|-`, and external
`maw <plugin> [args...]`. Go also provides [`context`](docs/mcp.md) through local
Serena and CodeGraph MCP servers. Plugins run with your privileges, not in a sandbox.

## Repository

- `src/` — `go/`, `rs/`, `js/`, `zig/`
- `docs/` — guides and benchmark reports
- `utils/` — scripts and modular `just` tasks

[Development](docs/development.md) · [Plugins](docs/plugins.md) ·
[Architecture](docs/architecture.md) · [Benchmarks](docs/benchmarks/cli/README.md) ·
[Release workflow](docs/release.md)
