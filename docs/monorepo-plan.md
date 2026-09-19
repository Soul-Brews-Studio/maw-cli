# Polyglot increment — issue #3

Move the already-smoked Go host into `/go`; add independent `/rs`, `/js` (Bun),
and `/zig` implementations of the same small process-plugin contract. This is
not a vendored copy or a full port of the external maw-js/maw-rs source projects.

## Guardrails

- Preserve help/version/plugins, usage errors, deterministic discovery and exact
  argument/stream forwarding. Run existing CLI smoke before/after the Go move,
  then apply the same harmless fixture to every port. No unit tests yet.
- Keep each implementation's manifest/source/cache under its own directory.
  Shared `just mod` tasks, smoke inputs and benchmark methodology stay at root.
- No new runtime dependencies, live MCP clients, auto-update wrappers, release
  engine, telemetry uploads or binary uploads in this layout increment.
- Record actual runtime/compiler versions, commands, warmups and raw samples.
  Separate build timing from CLI startup; include Bun runtime startup rather
  than implying JavaScript is a native binary.
- Benchmark native optimized builds and Bun's bundled source. Cold-build samples
  use isolated caches, never destructive global cache cleaning. They are
  cache-isolated compiler runs, not claims of a cold OS or network/toolchain setup.
- Development effort/line counts are descriptive observations, not language
  productivity rankings. Heavy MCP trace/index throughput remains unmeasured
  until equivalent real processing workloads exist in each implementation.

## Shipping

Issue #3 -> focused commits on `feat/3-polyglot-cli` -> PR into `alpha` -> compile
and smoke -> self-merge -> checkout/pull `alpha`. Verify the new Go remote command
`go run github.com/Soul-Brews-Studio/maw-herdr/go/cmd/maw@alpha --help` after merge.
The old root-module command path is replaced in this unreleased alpha layout.
Keep `$calver` a separate user handoff; no tag or release in this increment.
