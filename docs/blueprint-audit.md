# Master blueprint implementation audit

Historical PR9 audit. Later changes: [automatic prebuilt releases](release.md)
and [direct GitHub bunx](running.md) supersede the source-only publication limits below.
The `index` CLI, parser dependency and throughput tasks were subsequently removed
in PR19; their evidence below describes the older PR9 snapshot only.

The full user blueprint, plus later approval of Rust `serde_json`, public visibility
and `src/` / `docs/` / `utils/` layout, is the scope—not only the initial help milestone.

| Requirement | Evidence / explicit boundary |
|---|---|
| Go plugin-style modules | `src/go/internal/command.CommandPlugin`; init-registered command packages and aggregator; same metadata for help/dispatch |
| GitHub remote Go command | Nested module `.../src/go`; `go run/install .../src/go/cmd/maw@alpha`; source-only, no bootstrap installer |
| Native MCP clients / automatic traces | stdlib bounded stdio MCP client, context resolver, per-result Serena JSON memory writes; real installed servers plus mock CLI verified |
| Parallel ports | `src/{go,rs,js,zig}`; matching actual-process help/plugin/index smokes |
| Development speed / overhead | [Observed delivery windows and source footprint](development-benchmark.md); exact earliest compile instant/coding effort unrecoverable, never invented |
| Cold/warm build + startup | [Measured source snapshots](benchmarks/cli/README.md); isolated compiler caches, warm OS caches, actual fresh processes |
| Heavy trace/context indexing | 19.86MB normalized MCP corpus, real retained postings, independent output oracle, wall/user/system/peakRSS; not live-server throughput |
| GitHub flow | Issues5–8 before implementation, incremental pushes, PR9 into alpha; self-merge after successful CI |
| Modular timed tasks | `utils/just/{go,rs,js,zig,bench,mcp,memory,release}.just`; root justfile imports modules |
| Long-run Relic / Serena | Incremental Relic index/session tasks; local transcripts; refreshed semantic indexes and Serena learning/index memories |
| Compile/smoke first | Real CLI and tiny owned mock processes; no unit frameworks or comprehensive integration suites |
| CalVer + release notes | `just go release` previews pinned upstream calculator and GitHub PR/issue-derived notes; explicit approved TAG+SHA required for source-tag prerelease; no Go CalVer engine |
| Public repository / clean layout | Visibility changed only after explicit user authorization and tracked-history credential/artifact scan; alpha stays default |

## Verification and limits

Shared index smoke:16 valid file/stdin cases (including depth32 and exact64MiB),
18 invalid cases, usage/missing-file behavior across all ports. Go vet and baseline
Go1.22 compile/smoke; Rust1.69 lock/fmt; Zig0.16 fmt; Python syntax; Linux/macOS
compile/smoke matrix is attached to PR9. No binaries, source indexes or transcripts
are uploaded. CLAUDE.md remains a relative AGENTS.md symlink.

CodeGraph1.6.0 does not index Zig; Serena symbol lookup covers it, but empty
JS/Zig reference results are not proof of no callers. Historical development times
are delivery-window upper bounds, not exact time-to-first-compile measurements.
The release **publication branch is deliberately unexecuted**: the user requested
an approval handoff after code shipping. Automation is prepared; publishing a tag
or release is a separate, gated action, not unfinished source implementation.

Cleanup plan followed: preserve behavior with existing process smokes before
extracting command packages and moving paths; move tracked source, retain local
caches, repair references, compile/smoke all four, review failure boundaries, then
ship through GitHub Flow. No learned external repository source was modified.
