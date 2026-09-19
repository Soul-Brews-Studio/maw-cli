# Repository Agent Instructions

## Shared instructions

`AGENTS.md` is the source of truth for repository instructions. `CLAUDE.md`
must remain a relative symlink to `AGENTS.md`, not a separate copy.

## Lean Go CLI and shipping

- Polyglot layout: `go/` is the core Go module, `rs/` the Rust port, `js/` the Bun
  port, `zig/` the Zig port. These are independent implementations of the shared
  CLI contract, not vendored maw-js/maw-rs repositories. Keep manifests/cache/output
  isolated, and validate the same actual-process smoke fixture across ports.
- `just dev all` builds/smokes all ports; `just <go|rs|js|zig> check` selects one.
  `just bench run` measures startup; `just bench builds` includes build samples.
  `just bench index` measures normalized trace parsing, real postings and per-child
  CPU/RSS. Keep development delivery windows distinct from exact first-build times. No synthetic numbers or language rankings.
- After moves or branch switches, explicitly sync CodeGraph and verify a known
  symbol: `status` can say no changes even when transient checkout events removed
  symbols. Serena's live project config can also remain cached; persisted config
  plus a fresh verified MCP connection is different from reloading the old one.

- Start with a small, standard-library-only Go `maw` host. Commands share registry
  metadata for help and dispatch; new built-ins use `CommandPlugin` packages with init-time factory registration.
  External executable plugins keep their separate process boundary.
- Rust alone may use the explicitly approved `serde_json`; preserve its pinned
  Rust 1.69-compatible lockfile. No other direct dependencies without approval.
- Compile first, then smoke-call the actual CLI. Unit tests are deferred until
  the user explicitly requests them. Do not add test frameworks. Release tooling
  stays preview-only unless the user explicitly approves the exact tag/commit.
- Keep development tasks in a small root `justfile` with `mod` files. Reuse Go's
  build cache, build once per smoke run, and record wall-clock iteration samples
  with the exact command/environment. Do not infer broad speedups from small samples.
- Follow GitHub flow: issue first, small feature commits/pushes, PR into `alpha`,
  verify compile/smoke, merge, then checkout `alpha` and pull fast-forward-only.
- Source only for now: no binary uploads, automatic tags, releases, or visibility
  changes. Ask the user about `$calver` after shipping code. The installed skill
  targets arra-oracle-skills-cli; our pinned pure-calculator adapter never runs
  its mutating main entrypoint. Do not invent a Go CalVer engine or mutate arra.
  `just go release` previews; `just release publish TAG SHA` requires user approval.
- Use `relic` CLI incrementally to retain long-session context. Read only relevant
  history and keep raw transcripts/index databases local. Active sessions may
  remain changed immediately after indexing; do not loop trying to reach zero.

## Serena MCP: indexing and understanding

- Use Serena MCP to maintain discoverable project knowledge and understand
  code relationships, not just to locate text.
- Read Serena's `initial_instructions` before first use. Activate the correct
  project by its resolved absolute source path before querying or writing memories.
- Register learned repositories as separate Serena projects. Keep their language
  configuration and indexes usable; verify symbol lookup after setup or refresh.
  Do not treat a successful project activation as proof that indexing succeeded.
- Begin unfamiliar code exploration with `get_symbols_overview` and `find_symbol`.
  Use `find_referencing_symbols`, `find_declaration`, or `find_implementations`
  to follow callers, dependencies, implementations, and data/control flow.
- Record important relationships with source paths, symbol names, and the reviewed
  commit. Distinguish verified behavior from inference and untested instructions.
- Keep a learning index in Serena memories linking each repository, source path,
  snapshot, learning hub, and key relationships. Update it after learning or
  meaningful structural changes; revalidate stale entries before relying on them.
- Serena activation is shared state: one coordinator owns project switching;
  parallel agents must not switch projects independently.
- If semantic indexing is unavailable, report the exact limitation and use bounded
  file/text inspection. Never claim a semantic index or relationship is verified
  when only a text search or documentation summary was available.

## Learning artifacts

- Keep notes and hub indexes under `ψ/learn/<owner>/<repo>/`; keep dated learning
  summaries under `ψ/memory/learnings/` and sources outside this repository.
- Resolve `origin` symlinks before passing source paths to agents. Give agents
  separate absolute read and write paths; do not modify learned source code.
- Cite only evidence from the target repository. Do not import host conventions
  or invent missing architecture, tooling, tests, or relationships.
- Keep `ψ/learn/.origins` current and origin symlinks gitignored. Validate artifact
  links and save the durable index through Serena MCP before reporting completion.

## CodeGraph + Serena workflow

- Use both tools for complementary evidence: CodeGraph for broad symbol discovery,
  call/dependency graphs and multi-file context; Serena for precise symbol bodies,
  declarations, references, implementations, and persistent learning memories.
- Keep each source repository's CodeGraph database in its own `.codegraph/`.
  For a new source, run `DO_NOT_TRACK=1 codegraph init --yes <absolute-source>`;
  inspect any setup changes. Query with the explicit source path, not this host's
  documentation directory or its `origin` symlinks.
- Before trusting graph results after offline edits, check `codegraph status
  <absolute-source> --json` and run `codegraph sync <absolute-source>` if needed.
  A running MCP server can watch changes; do not assume a watcher is running or
  that an index is complete merely because initialization once succeeded.
- CodeGraph MCP uses `projectPath` to select the repository. Available configured
  tools include `codegraph_explore`, `codegraph_search`, `codegraph_callers`,
  `codegraph_callees`, `codegraph_node`, and `codegraph_status`. Discover actual
  schemas before calling; installed versions can differ from upstream main.
- Cross-check consequential relationships against source and the other tool.
  An empty result is not proof of no callers, and a graph's metadata is not a
  substitute for reading the declaration. Record unresolved discrepancies.
- Preserve privacy: keep `DO_NOT_TRACK=1` and `CODEGRAPH_TELEMETRY=0` in the
  CodeGraph MCP environment. Do not enable telemetry or upload source for indexing.
- Preserve this instruction source and its symlink. Prefer explicit MCP registration
  over broad `codegraph install`, which can rewrite agent instruction files.
- Maintain benchmark evidence under `benchmarks/code-navigation/`: source commits,
  tool versions, exact queries, warmups, timed samples, raw responses, correctness
  checks, and limitations. Compare known-answer retrieval as well as latency.
  Do not claim general speedups or token savings from a small sample or from timings
  measured through different transports.
- Persist benchmark findings and graph locations in Serena's `learning/index`
  memory. See `benchmarks/code-navigation/2026-09-19/REPORT.md` for the initial run.
