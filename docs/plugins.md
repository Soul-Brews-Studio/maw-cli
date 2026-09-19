# Command/plugin contract

## Available now

| Command | Purpose |
|---|---|
| `maw`, `maw -h`, `maw --help`, `maw help` | List registered commands |
| `maw help <command>` | Show built-in usage or invoke an external plugin with `--help` |
| `maw version`, `maw -v`, `maw --version` | Print the host version |
| `maw plugins` | List registered command names, built-in/external kind, and executable path |
| `maw <external> [args...]` | Run a discovered `maw-<external>` executable |

## Discovery and trust

- Names match `[a-z][a-z0-9-]*`. Matching is exact and case-sensitive.
- Only absolute PATH directories are searched. Empty/relative entries are ignored,
  including `.`; an explicit absolute path to the working directory is allowed.
- Linux/macOS files must be regular executable files. Symlinks are resolved.
  Windows accepts `.exe` files, not `.bat`/`.cmd` shell scripts.
- The first eligible executable wins duplicate names in PATH order. Built-ins
  always win collisions with `maw-help`, `maw-version`, or `maw-plugins`.
- Broken symlinks, missing/unreadable directories, invalid names and nonexecutables
  are skipped. Root help and listing do not execute discovered code.
- PATH is a trust boundary. A file can change between discovery and execution;
  plugins are normal programs running as you, not signed or sandboxed packages.
- `maw plugins` displays the selected resolved paths. It does not download,
  install, update, activate, or uninstall software.

## Invocation

`maw fleet ls --json` invokes the selected `maw-fleet` with exactly
`["ls", "--json"]`. The plugin owns nested subcommands and their flags.
Spaces, case, Unicode and shell metacharacters remain argument data.
Standard input/output/error and environment are inherited; the host does not
capture or interpret a plugin's output. No environment credentials are logged.

`maw fleet --help` passes `--help` through. `maw help fleet` explicitly invokes
the same plugin with `--help`; use root help/list if no external execution is wanted.

Host usage errors return **2**. An external process's ordinary exit status is
preserved. A launch failure returns **126**. Cancellation or abnormal termination
returns nonzero. Go and Bun explicitly cancel/signal the direct child on host
interrupt. The standard-library Rust and Zig ports currently rely on terminal
process-group signals; signaling only the host PID does not guarantee child
shutdown. All plugins own their descendant-process shutdown strategy.

Linux/macOS are the shared smoke targets. Windows discovery code is present in
the Go/Rust/Bun ports but cross-runtime Windows behavior is not yet validated.

## Future command catalog — not implemented

These command families follow concepts in the source references, but are not a
promise of exact maw-js/maw-rs compatibility. Each family can be its own executable
plugin with help, validation, tests, and an explicit effect boundary.

| Family / examples | Plugin responsibility | Effects |
|---|---|---|
| `ls`, `peek`, `a` / attach | Session discovery, screen inspection, terminal attachment | Read/interactive |
| `wake`, `sleep`, `run` | Agent lifecycle and pane execution | Creates/stops processes; explicit invocation only |
| `hey`, `send`, `notify` | Address resolution and delivery reporting | Sends messages; never imply consumption from submission |
| `fleet`, `agents` | Host/agent inventory and cross-host queries | Network access when invoked |
| `team`, `swarm` | Coordinated lifecycle of an explicit group | Durable state and process changes |
| `work`, `worktree` | Repository/issue workspaces | Git/worktree writes |
| `serve` | API/WebSocket backend | Long-running listener; outside the help host |
| `config`, `doctor` | Configuration editing and diagnostics | Reads by default; writes explicit |
| `plugin` | Future managed installation/verification | Requires a separate trust and distribution design |

Catalog evidence: [maw-js core route names](https://github.com/Soul-Brews-Studio/maw-js/blob/5ee396a7f61def2ee2a8774d3f6da216e069c6c2/src/cli/dispatch.ts#L9-L15),
[maw-rs usage examples](https://github.com/Soul-Brews-Studio/maw-rs/blob/76f130846207ec7b631a70e3b18ac25b99966b92/README.md#usage),
and their reviewed learning hubs. The family grouping and process protocol above
are maw-herdr design decisions, not upstream behavior claims.

## Adding a built-in

Only host-essential commands should be built in. Register a `CommandPlugin` factory in its package `init`, then blank-import
the package from `src/go/internal/commands/register.go`.
Smoke-call it now; unit tests wait for the user's explicit mark.
It automatically participates in help/listing; no separate help catalog to edit.
Prefer an external plugin for operational commands so the host stays lean.

## Go built-in modules

`src/go/internal/command.CommandPlugin` defines `Metadata`, `BindFlags(*flag.FlagSet)`
and `Run(context.Context, *Invocation) int`. Each built-in package calls
`command.Register(factory)` in `init`; `internal/commands/register.go` links packages
with blank imports. The router copies factories, creates fresh command instances,
and derives help/dispatch from the same metadata. Invocation carries streams,
version, positional args, catalog and nested dispatch. Only flag-declaring built-ins
use Go flag parsing; external plugin argv is untouched. Flags precede positionals.
`context --help` and `help context` only read metadata.

`index` is shared across ports. `context` is currently Go-only. These names are
reserved wherever built in; adding a command requires importing its package, not
editing a switch ladder. This is static package registration, **not** Go shared-library
plugins or runtime-loaded code. No dependency framework.

The host names `maw-go`, `maw-rs`, `maw-js`, and `maw-zig` are reserved and
excluded from discovery. Install them side by side without recursive host plugins.
