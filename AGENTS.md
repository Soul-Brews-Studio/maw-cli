# Repository Agent Instructions

## Shared instructions

`AGENTS.md` is the source of truth for repository instructions. `CLAUDE.md`
must remain a relative symlink to `AGENTS.md`, not a separate copy.

## Lean Go CLI and shipping

- Polyglot layout: `src/go/` is the core Go module, `src/rs/` the Rust port, `src/js/` the Bun
  port, `src/zig/` the Zig port. These are independent implementations of the shared
  CLI contract, not vendored maw-js/maw-rs repositories. Keep manifests/cache/output
  isolated, and validate the same actual-process smoke fixture across ports.
- `just dev all` builds/smokes all ports; `just <go|rs|js|zig> check` selects one.
  `just bench run` measures startup; `just bench builds` includes build samples.
  Keep development delivery windows distinct from exact first-build times.
  No synthetic numbers or language rankings. Historic index-throughput reports
  refer to the removed command, not the current CLI.
- After moves or branch switches, explicitly sync CodeGraph and verify a known
  symbol: `status` can say no changes even when transient checkout events removed
  symbols. Serena's live project config can also remain cached; persisted config
  plus a fresh verified MCP connection is different from reloading the old one.

- Start with a small, standard-library-only Go `maw` host. Commands share registry
  metadata for help and dispatch; new built-ins use `CommandPlugin` packages with init-time factory registration.
  External executable plugins keep their separate process boundary.
- Preserve Rust 1.69 compatibility. The user explicitly approved `serde_json`
  for installed-plugin JSON metadata; keep its compatible transitive lockfile.
  No other new runtime dependencies without approval.
- Compile first, then smoke-call the actual CLI. Unit tests are deferred until
  the user explicitly requests them. Do not add test frameworks. The user authorized automatic alpha prereleases and prebuilt uploads on 2026-09-19;
  publish only after verified same-repository alpha CI and complete native build smokes.
- Keep development tasks in a small root `justfile` with `mod` files. Reuse Go's
  build cache, build once per smoke run, and record wall-clock iteration samples
  with the exact command/environment. Do not infer broad speedups from small samples.
- Follow GitHub flow: issue first, small feature commits/pushes, PR into `alpha`,
  verify compile/smoke, merge, then checkout `alpha` and pull fast-forward-only.
- Automatic public prebuilt releases are now authorized: Linux/macOS x64+arm64,
  all four ports, CalVer alpha tags, checksums and release metadata. GitHub Actions
  handles build/upload/publish asynchronously; do not wait locally for the full
  release matrix after queueing, and do not claim queued assets are published.
- Keep write permission confined to the publish job. Validate exact source SHA,
  upstream CI identity, archive contents and full asset set. Never overwrite a
  published tag/asset. Skip superseded alpha heads rather than substituting code.
- Upload only selected binaries/checksums/release manifests, never source indexes,
  raw transcripts, private configuration, credentials or benchmark input artifacts.
  The repository is already public; do not alter other repository visibility.
- The installed `$calver` skill targets arra; reuse its pinned pure calculator,
  never its mutating main entrypoint or a new Go version engine. `just go release`
  stays read-only preview; trusted Actions publication is separately automated.
- Alpha release tags use exactly `vYY.M.D-alpha.HMM`, with no run-ID suffix.
  Calculate the date and `HMM = hour * 100 + minute` in `Asia/Bangkok` from the
  source CI run's creation time; omit leading zeros (09:37 becomes `937`).
  The Go companion tag is `src/go/v0.YYYYMMDD.HMM-alpha`, at the same source SHA.
  Keep the CI run ID in provenance metadata only. Rerunning the same CI run keeps
  its original timestamp and tags. Refuse collisions with a different source SHA;
  never move existing tags. A new timestamp requires a genuinely new source CI
  run created in a later minute, not a rerun of the original run.
- Use `relic` CLI incrementally to retain long-session context. Read only relevant
  history and keep raw transcripts/index databases local. Active sessions may
  remain changed immediately after indexing; do not loop trying to reach zero.

## Naming and package entrypoints

- The public umbrella repository is `Soul-Brews-Studio/maw-cli`; executables are
  `maw-go`, `maw-rs`, `maw-js`, and `maw-zig`, with source under `src/{go,rs,js,zig}`.
- Go installs from `src/go/cmd/maw-go`; root Git package metadata exposes `maw-js`
  to bunx. No npm publication, build hook or extra runtime dependency is required.
- Preserve the shared `maw` help/diagnostic and `maw-` plugin protocol. Exclude all
  four host executable names from plugin discovery to avoid recursive hosts.
- JavaScript named helpers use one function per `mod.<function>.ts`; keep `cli.ts`
  as the small executable entrypoint and shared declarations in `types.ts`.

- The public listing command is `plugin ls`; accept `plugins ls` and legacy
  `plugins` plus `list` as equivalent aliases. They inventory global installed `plugin.json`
  metadata (not built-ins or PATH commands); `-v`/`--verbose` shows rows and
  `--all` includes disabled entries. Follow docs/installed-plugin-listing.md.
  Never execute `plugin.ts`, load entrypoints, migrate config or modify plugin
  state while listing. PATH dispatch remains separate with builtin collision
  protection; do not add plugin management operations implicitly.
- Basic Git lifecycle belongs to maw-cli, not individual plugins: `marketplace`
  is a static source list; explicit `plugin install/update/info/check` use Git's
  origin/HEAD rather than new registry/lock machinery. Follow
  docs/plugin-lifecycle.md. No automatic builds, hooks, background updates or
  native downloads. Preserve pins, refuse dirty/non-fast-forward updates, and
  validate candidate metadata before mutation. Label the entry Git blob hash
  honestly; it is not a SHA-256 package checksum or publisher signature. Keep all
  ports covered by utils/scripts/lifecycle-smoke.py; no new unit framework.
- Go-only additions: marketplace includes local installed/version/ref/commit
  details; plugin install/update accept @REF or #REF aliases for --ref. Keep
  listing read-only, report unavailable/corrupt Git metadata honestly, and do
  not claim these additional forms exist in other ports. Cover them with the
  marketplace-smoke.py and selector-smoke.py actual-process fixtures.
- Go `update` self-replaces from published maw-cli alpha assets using only the
  standard library. Follow docs/self-update.md: bounded HTTPS, archive/metadata
  checksums, exact candidate version proof before single-rename replacement,
  no default source downgrade, and no plugin/config/cache changes. `--check`
  never installs; local dev builds do not self-replace. Go-installed binaries
  can transition to prebuilts. Never point tests at the user's executable;
  update-smoke.py uses source overlays/local TLS/copied binaries. Other ports
  do not yet self-update. No new runtime libraries/system tools were approved.
- Installed command dispatch is a separate, explicit subprocess operation after
  builtin/PATH lookup. Reuse inventory selection and disabled state. Only standalone
  Bun scripts declaring `runtime=bun-dev`, `target=js`, `cli.interactive=true` are
  supported; do not silently import handler modules or add WASM/management support.
  All ports resolve external Bun from absolute PATH directories, preserve argv,
  streams and cwd, and fail clearly for disabled/unsupported/missing entries.
  Root help/list stays inert; explicit `help <installed>` forwards `--help`.
  Preserve the shared actual-process dispatch smoke, including terminal stdin.
- The `index` CLI was removed entirely at the user's request, not hidden. Do not
  restore it or its benchmark/smoke tasks implicitly. The separately approved
  metadata JSON parser must not restore trace-index functionality.
  Serena/CodeGraph indexing and Relic history indexing remain separate and active.

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
