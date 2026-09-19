# maw-herdr

A help-first CLI with independent Go, Rust, Bun and Zig implementations.
Modular built-ins and external executable plugins; no tmux service or agent engine.

## Run from GitHub

With **Go 1.22+**, no clone required:

```sh
go run github.com/Soul-Brews-Studio/maw-herdr/src/go/cmd/maw@alpha --help
```

`@alpha` follows development. Use an exact commit to pin a revision;
CalVer alpha releases are planned, not published yet.

## Choose a runtime

| Runtime | How to run |
| --- | --- |
| Go | Run directly from GitHub above, or install `maw` |
| Bun | Clone, then `bun src/js/src/cli.ts --help` |
| npx | Clone, then use npx to run Bun; not a native Node port |
| bunx | Clone, then use bunx to select Bun; no published maw package |
| Rust / Zig | Clone and compile their independent ports |

**[Run and install guide →](docs/running.md)** — exact commands and version pinning.
No `maw-herdr` package is published for npx/bunx.

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
