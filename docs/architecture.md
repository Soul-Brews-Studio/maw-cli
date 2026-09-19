# Architecture: a small command host

## Boundaries

`src/go/cmd/maw-go` wires standard streams, interrupt cancellation, and version information
into `src/go/internal/cli.Run`. It returns the command's exit status to the shell.

`src/go/internal/command.CommandPlugin` defines metadata, flag binding and contextual
execution. Decoupled packages in `internal/commands/` register factories in `init`;
the aggregator blank-imports them. `internal/cli.Run` builds the metadata catalog
from those factories plus discovered executable plugins. Help and execution resolve
the same registry, so an unavailable future command is not presented as working.

The only central aliases are `-h`/`--help` and `-v`/`--version`. There is no
catch-all agent shorthand, network service, automatic installation or fuzzy
prefix execution. A typo must not turn into an operational command.

`src/go/internal/cli/plugins.go` discovers executable files, and invokes explicitly
selected plugins with `os/exec` and an argument slice, not a shell command string.
Core dependencies are the standard library only. Existing Go code need not link
against an SDK to provide a plugin; any language can implement the process contract.

Local builds print `dev`; Go remote builds can report the module version.
Release builds inject the same immutable CalVer tag into all four executables.
No Go version-bump engine: the development release script reuses a pinned
upstream CalVer calculator, separate from CLI runtime.

## Independent runtime implementations

| Directory | Entry / router | Plugin process boundary |
|---|---|---|
| `src/go/` | `cmd/maw-go/main.go`, `internal/cli/cli.go` | `internal/cli/plugins.go` |
| `src/rs/` | `src/main.rs`, `src/cli.rs` | `src/plugins.rs` |
| `src/js/` | `src/cli.ts` → `src/mod.run.ts` via Bun | `src/mod.discover.ts`, `src/mod.execute.ts` |
| `src/zig/` | `src/main.zig` | `src/registry.zig` discovers; `Host.execute` spawns |

These are fresh ports of this small contract, not copies of the external learned
maw-rs/maw-js repositories. Each owns its manifest and generated cache/output.
Root `go.work` assists local Go navigation; the standalone module is `src/go/go.mod`.
The public executables are `maw-go`, `maw-rs`, `maw-js`, and `maw-zig`.
The common help/diagnostic prefix stays `maw`, and plugins keep the `maw-` prefix;
the four host names are reserved, not recursively discovered as plugins.
JavaScript uses one named function per `mod.<function>.ts`; `mod.run` assembles
the registry; `mod.listPlugins` serves `plugin ls` and its plural aliases.
Root `package.json` exposes the Bun entrypoint as `maw-js` for direct GitHub bunx.
Shared `utils/scripts/smoke.sh` exercises real processes with an isolated plugin PATH.
Root `just` modules keep implementation-specific commands separate. Benchmark
methodology is [here](benchmarks/cli/README.md); comparisons cover the actual
prototype implementations, not general language speed.

## Reference evidence and deliberate differences

These are design inputs, not copied implementations or claims of compatibility.

| Reference | Verified relationship | Decision here |
|---|---|---|
| [maw-js registry](https://github.com/Soul-Brews-Studio/maw-js/blob/5ee396a7f61def2ee2a8774d3f6da216e069c6c2/src/cli/command-registry-match.ts#L11-L51) | `registerCommand`, `matchCommand`, `listCommands` share descriptors | One registry drives help and invocation; exact top-level names, plugin owns nested commands |
| [maw-js dispatcher](https://github.com/Soul-Brews-Studio/maw-js/blob/5ee396a7f61def2ee2a8774d3f6da216e069c6c2/src/cli/dispatch.ts#L25-L52) | Communication/tool routing precedes alias and plugin dispatch | Do not carry the multi-layer fallback ladder into a help-first bootstrap |
| [maw-js argument boundary](https://github.com/Soul-Brews-Studio/maw-js/blob/5ee396a7f61def2ee2a8774d3f6da216e069c6c2/src/cli/dispatch.ts#L55-L64) | Dispatch explicitly protects word boundaries and original-case arguments | Never guess prefixes or join plugin argv through a shell |
| [maw-rs generated help](https://github.com/Soul-Brews-Studio/maw-rs/blob/76f130846207ec7b631a70e3b18ac25b99966b92/crates/maw-cli/src/core_impl/resolve_plan.rs#L427-L492) | `usage_all_text` derives rows from dispatch entries and calls `render_help_rows` | Sort help from actual registered commands |
| [maw-rs cheap help discovery](https://github.com/Soul-Brews-Studio/maw-rs/blob/76f130846207ec7b631a70e3b18ac25b99966b92/crates/maw-cli/src/core_impl/resolve_plan.rs#L392-L425) | Help listing avoids loading/executing plugin artifacts | File discovery only for root help/list; no plugin code execution |

Serena verified the TypeScript `registerCommand` and Rust `render_help_rows`
bodies; CodeGraph MCP supplied surrounding registration and caller relationships.
Serena references for the TypeScript registry returned empty despite visible
callers. That discrepancy is recorded, not interpreted as absence of callers.
The Rust help call was independently retrieved through CodeGraph callers.

Durable trace: Serena `learning/maw-go-cli-design`, linked from `learning/index`.
Source snapshots and learning hubs remain in `ψ/learn/Soul-Brews-Studio/` locally.

## Context and learning feedback

`commands/context.plugin.resolve` starts configured owned MCP stdio processes,
negotiates explicit legacy protocol versions, resolves CodeGraph context and optional
Serena symbol/overview data, then immediately calls Serena `write_memory` for each
successful resolution. Missing/malformed/error acknowledgments fail the command.
Traces contain source identifiers, revision, hashes, timing and size, not raw query
or code content. Tool output is untrusted data. This is local application persistence,
not server-only `notifications/message` or public telemetry. See [MCP](mcp.md).

The experimental `index` CLI and all four parser implementations were removed
to keep the host lean. Its [old workload contract](trace-index-contract.md) remains
historical evidence only. Serena/CodeGraph context resolution and Relic history
indexing are separate features and remain intact. Production agent/fleet
operations remain outside this prototype.

## Non-goals for this increment

No tmux/PTY implementation, agent lifecycle, fleet discovery, messaging transport,
HTTP server, plugin marketplace, WASM engine, Go `plugin` shared objects, automatic
updates, or user-configuration database. Operational features will be separate
commands/plugins, not placeholder branches in the host.
