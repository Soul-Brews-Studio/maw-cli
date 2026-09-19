# maw-herdr

One lean CLI contract, four independent implementations for comparison.
Help first; modular built-ins plus external executable plugins.

```text
go/     core maw in Go      → bin/maw-go (remote install name: maw)
rs/     Rust                → rs/target/release/maw-rs
js/     TypeScript via Bun  → bun js/dist/cli.js
zig/    Zig                 → zig/zig-out/bin/maw-zig
just/   per-language task modules
scripts/ shared actual-CLI smoke and benchmark harness
```

These are new small ports—not vendored copies of the external maw-js/maw-rs
projects. They implement `help`, `version`, `plugins`, `index FILE|-`, and external
`maw <plugin> [args...]`. Go additionally provides the native MCP `context` command.
No tmux service or agent engine. Rust uses the approved `serde_json`; other ports
use standard/built-in JSON parsing.

## Build and smoke

Use Go 1.22+, Rust 1.69+, Bun 1.3.11 and Zig **0.16.0**. `just` runs modular tasks;
benchmarking also needs Python 3. CI uses Linux and macOS with pinned toolchains.

```sh
just                 # list all modules
just go check        # compile + real CLI smoke; same for rs, js, zig
just dev all         # all four ports
just bench run       # startup samples, raw JSON saved locally
just bench builds    # also isolated-cache + repeated build measurements
just bench index     # normalized MCP JSONL postings, wall/CPU/peak RSS
just mcp check       # Go context against tiny local stdio mock
just memory index    # incremental Relic checkpoint, kept local
just go release      # read-only CalVer + GitHub release-notes preview
```

No unit tests yet. Each smoke run uses a harmless isolated executable plugin:
help/list must not execute it; explicit dispatch must preserve argv, streams and
normal exit status. See [plugin contract](docs/plugins.md) for trust/signal limits.
Rust/Zig do not explicitly forward interrupts sent only to the host PID.

Go can also be checked without `just`: `sh scripts/check.sh`.
Each build reuses its language's cache; smoke calls compiled/bundled output rather
than recompiling per assertion. Native optimized builds and Bun-bundled source
are different deployment models: see [benchmark methodology](benchmarks/cli/README.md).
Startup samples are new processes with warmed OS caches, not cold-machine tests.
The [index workload](docs/trace-index-contract.md) measures local parsing/indexing,
not live MCP server throughput. [Development evidence](docs/development-benchmark.md)
records observed delivery windows and footprint, not a language productivity ranking.

## Run Go from GitHub — like bunx/npx

With Go installed and Git access to this **private** repository:

```sh
GOPRIVATE=github.com/Soul-Brews-Studio/maw-herdr \
  go run github.com/Soul-Brews-Studio/maw-herdr/go/cmd/maw@alpha --help
```

Use `@<commit>` to pin a revision. To install the `maw` executable:

```sh
GOPRIVATE=github.com/Soul-Brews-Studio/maw-herdr \
  go install github.com/Soul-Brews-Studio/maw-herdr/go/cmd/maw@alpha
```

**Check for an existing `maw` first.** Set `GOBIN` to a separate absolute directory
if needed; otherwise Go uses `$(go env GOPATH)/bin`. `GOPRIVATE` bypasses public
module services, not Git authentication; configure SSH/credential-helper access
separately and preserve your other private-module patterns. The former root
`.../cmd/maw` path is replaced by `.../go/cmd/maw` in this unreleased alpha layout.
[Go remote command docs](https://go.dev/doc/go1.17#go-command),
[private module docs](https://go.dev/ref/mod#private-modules).

## Native MCP context (Go)

```sh
bin/maw-go context --config /path/to/trusted-mcp.json --project . \
  --file go/internal/cli/cli.go --symbol Run 'command dispatch'
```

See [MCP configuration and trace contract](docs/mcp.md). Every successful resolution
persists a metadata-only JSON trace to the active Serena memory tool before CLI
success. Server commands are trusted local executables, not sandboxed. Help never
starts servers. Legacy MCP versions are explicit; no claim of universal/latest support.

## Plugins and learning

A trusted executable named `maw-hello` on an absolute PATH entry becomes
`maw hello`. Built-ins cannot be shadowed. Root help/listing only inspect files;
`maw help hello` explicitly executes `maw-hello --help`. Plugins run with your
privileges, without a shell wrapper—not a sandbox or installer.

[Architecture/source traces](docs/architecture.md) explain what we learned from
maw-js and maw-rs. Serena stores `learning/index`; CodeGraph cross-checks symbol
relationships. `relic index` retains conversation history locally. Raw transcripts,
indexes, build outputs and benchmark result JSON are not uploaded.

Git flow: issue → focused feature commits → PR into `alpha` → verify → self-merge
→ sync `alpha`. No releases/tags without approval. [Gated release tasks](docs/release.md) reuse
the pinned upstream CalVer calculator without mutating arra.
`CLAUDE.md` is a relative symlink to [AGENTS.md](AGENTS.md).
