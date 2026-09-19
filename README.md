# maw-herdr

One lean CLI contract, four independent implementations for comparison.
Help first; operational commands remain external executable plugins.

```text
go/     core maw in Go      → bin/maw-go (remote install name: maw)
rs/     Rust                → rs/target/release/maw-rs
js/     TypeScript via Bun  → bun js/dist/cli.js
zig/    Zig                 → zig/zig-out/bin/maw-zig
just/   per-language task modules
scripts/ shared actual-CLI smoke and benchmark harness
```

These are new small ports—not vendored copies of the external maw-js/maw-rs
projects. They implement `help`, `version`, `plugins`, and `maw <plugin> [args...]`.
No tmux service, agent engine, runtime package dependencies or release machinery.

## Build and smoke

Use Go 1.22+, Rust 1.69+, Bun 1.3.11 and Zig **0.16.0**. `just` runs modular tasks;
benchmarking also needs Python 3. CI uses Linux and macOS with pinned toolchains.

```sh
just                 # list all modules
just go check        # compile + real CLI smoke; same for rs, js, zig
just dev all         # all four ports
just bench run       # startup samples, raw JSON saved locally
just bench builds    # also isolated-cache + repeated build measurements
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
Heavy MCP throughput and development productivity are **not yet measured**.

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
→ sync `alpha`. No releases/tags in this increment. `$calver` remains a separate
handoff; its installed script targets arra, so it must not mutate that repo here.
`CLAUDE.md` is a relative symlink to [AGENTS.md](AGENTS.md).
