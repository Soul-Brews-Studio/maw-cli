# Development

Start with the [run guide](running.md) if you only want to use the CLI.
The ports are independent implementations, not vendored maw-js/maw-rs projects.

## Build and smoke

Use Go 1.22+, Rust 1.69+, Bun 1.3.11 and Zig **0.16.0**. `just` runs modular tasks;
benchmarking and MCP mocks also need Python 3. CI builds/smokes on Linux and macOS.

```sh
just                 # list modules
just go check        # compile + actual CLI smoke; also rs, js, zig
just dev all         # all four ports
just mcp check       # Go context against temporary local stdio mocks
```

Without `just`, check Go with `sh utils/scripts/check.sh`.
No unit tests yet. Smoke fixtures use harmless isolated executable plugins and
verify help/list side effects, argv, streams and normal exit status. See the
[plugin contract](plugins.md) for trust and signal-forwarding limits.
Rust alone uses the approved `serde_json`; the other ports use built-in JSON parsers.

## Measure

```sh
just bench run       # new-process startup samples
just bench builds    # isolated-cache and repeated builds too
just bench index     # normalized JSONL indexing: wall/CPU/peak RSS
```

Build once, then smoke the compiled/bundled output. Raw benchmark JSON stays local.
[Benchmark methodology and results](benchmarks/cli/README.md) distinguish native
optimized builds from Bun bundles and warmed OS caches from cold-machine tests.
The [index workload](trace-index-contract.md) measures local parsing and postings,
not live MCP throughput. [Development evidence](development-benchmark.md) records
observed delivery windows, not exact first-build times or language productivity rankings.

## MCP and learning

[MCP configuration](mcp.md) covers trusted local Serena/CodeGraph servers and
mandatory metadata-only trace persistence. Help does not start servers.
[Architecture](architecture.md) links the source relationships learned from
maw-js and maw-rs. Serena keeps `learning/index`; CodeGraph cross-checks symbols.

```sh
just memory index    # incremental Relic history checkpoint, kept local
```

Raw transcripts, indexes, build outputs and benchmark JSON are not uploaded.
Active sessions can remain changed immediately after indexing.

## Ship source

Issue → focused feature commits → PR into `alpha` → compile/smoke → merge →
sync `alpha`. `CLAUDE.md` remains a relative symlink to [AGENTS.md](../AGENTS.md).

```sh
just go release      # read-only CalVer and release-notes preview
```

[Release tasks](release.md) reuse the pinned upstream CalVer calculator without
mutating arra. Publication requires explicit approval of the exact tag and commit;
preview creates no tag, release or binary upload.
