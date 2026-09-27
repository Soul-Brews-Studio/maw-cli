# Command/plugin contract

## Available now

| Command | Purpose |
|---|---|
| `maw`, `maw -h`, `maw --help`, `maw help` | List built-ins, installed plugins and PATH commands, in that order |
| `maw help <command>` | Show built-in usage or invoke an external plugin with `--help` |
| `maw version`, `maw -v`, `maw --version` | Print the host version |
| `maw plugin ls` | Summarize installed global plugin JSON metadata |
| `maw plugin ls -v` | Show name/version/tier/enabled-state/directory rows |
| `maw plugin ls --all` | Include disabled plugins |
| `maw plugins`, `maw plugins ls` | Compatibility aliases for `maw plugin ls` |
| `maw <external> [args...]` | Run a discovered `maw-<external>` executable |
| `maw <installed> [args...]` | Fall back to an installed standalone Bun CLI |
| `maw <installed> version`, `maw <installed> --version` | Host prints the manifest name, version and short commit; no plugin code runs ([reserved verb](plugin-lifecycle.md#reserved-plugin-verb-version)) |

## Installed metadata versus executable commands

Listing reads the global plugin inventory, normally `~/.maw/plugins`, using
`plugin.json` and global disabled-plugin configuration. It does not list the
host's built-ins or PATH command catalog. See [inventory rules and limits](installed-plugin-listing.md)
for path overrides, config precedence, TypeScript-only manifests and health.
All aliases have the same behavior. No plugin/config state is changed.

## Installed standalone Bun CLIs

When a name is not a registered built-in or PATH command, all four hosts use the
same global JSON inventory and disabled-plugin configuration as `plugin ls`.
An installed CLI is selected by nonempty string `cli.command`, otherwise its
manifest `name`; `cli` must be an object. Command names must match
`[a-z][a-z0-9-]*`; `go`, `rs`, `js`, `zig` and removed `index` are excluded.
For multiple manifests declaring one command, first in inventory tier/name order
wins, including disabled or unsupported entries: never fall through to a shadow.

The supported script ABI requires all three manifest declarations:

```json
{ "runtime": "bun-dev", "target": "js", "cli": { "command": "herdr", "interactive": true } }
```

Use the inventory's effective entry (`entry`, then non-WASM `artifact.path`,
then `wasm`), normalized to an absolute path. The selected file must be regular.
Find executable `bun` in absolute PATH directories (relative/empty entries are
ignored), then spawn it with `[entry, ...args]` and inherited streams, environment
and working directory. No import, shell interpolation, fetch or install step.
The Bun host also uses external `bun`, not its own compiled executable as a runtime.
Root help lists built-ins under `Commands:`, installed plugins under
`Installed plugins:` and `maw-<command>` PATH executables under `External (PATH):`
(#53). An installed row is what dispatch reaches: the command above (never a
folder name, and only the first plugin declaring it), in parentheses the
`cli.aliases` that dispatch would route to it (not a built-in, PATH executable,
plugin command, or an alias another enabled plugin also declares; see
[plugin aliases](plugin-lifecycle.md#plugin-aliases-clialiases)), and the
manifest `description` (else `cli.help`) cut to one line at
the terminal width, 80 when stdout is not a terminal. Only enabled plugins get a
row; `N disabled — maw plugin ls --all` counts the rest, and a row whose command
a built-in or PATH executable takes is marked `(shadowed by …)`. An unreadable
inventory drops the section with a note on stderr; help still exits **0**.
Root help/list never execute entries. Explicit `help herdr` invokes the selected
plugin with `--help`, just like `herdr --help`.

Disabled plugins and unreadable/invalid configuration fail with **1** without
execution. Unsupported ABI, missing entry or missing Bun fail with **126** and a
diagnostic; no matching command retains unknown-command **2**. Other manifest
validation/skipping follows the inventory contract. Explicit invocation runs
trusted local code with your privileges; capability declarations, SDK versions
and artifact hashes are **not enforced**. Installation is not a trust signature.
These checks are not a race-proof sandbox against concurrent filesystem changes.

This supports the standalone script in
[maw-herdr-plugin at 93d4739](https://github.com/Soul-Brews-Studio/maw-herdr-plugin/tree/93d473919f31f97a4cf9bc7e3d8331b4b2a73c04),
including its bundled `artifact.path` form. It is not a general compatibility
layer for in-process handler exports or WASM. Herdr's operational verbs still
require its own external tools/services; help succeeding does not prove all verbs.

## PATH command discovery and trust

- Names match `[a-z][a-z0-9-]*`. Matching is exact and case-sensitive.
- Only absolute PATH directories are searched. Empty/relative entries are ignored,
  including `.`; an explicit absolute path to the working directory is allowed.
- Linux/macOS files must be regular executable files. Symlinks are resolved.
  Windows accepts `.exe` files, not `.bat`/`.cmd` shell scripts.
- The first eligible executable wins duplicate names in PATH order. Built-ins
  always win collisions with `maw-help`, `maw-version`, `maw-plugin`, or `maw-plugins`.
- Broken symlinks, missing/unreadable directories, invalid names and nonexecutables
  are skipped. Root help and listing do not execute discovered code.
- PATH is a trust boundary. A file can change between discovery and execution;
  plugins are normal programs running as you, not signed or sandboxed packages.
- `maw plugin ls` is a separate metadata inventory. It does not download,
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
| `plugin install/update/info/check` | Basic host-owned Git lifecycle | Explicit clone/update; commit and Git-blob inspection; see [contract](plugin-lifecycle.md) |

Catalog evidence: [maw-js core route names](https://github.com/Soul-Brews-Studio/maw-js/blob/5ee396a7f61def2ee2a8774d3f6da216e069c6c2/src/cli/dispatch.ts#L9-L15),
[maw-rs usage examples](https://github.com/Soul-Brews-Studio/maw-rs/blob/76f130846207ec7b631a70e3b18ac25b99966b92/README.md#usage),
and their reviewed learning hubs. The family grouping and process protocol above
are maw-cli design decisions, not upstream behavior claims.

## Adding a built-in

Only host-essential commands should be built in. Register a `CommandPlugin` factory in its package `init`, then blank-import
the package from `src/go/internal/commands/register.go`.
Smoke-call it now; unit tests wait for the user's explicit mark.
It automatically participates in help/dispatch; no separate help catalog to edit.
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

`context` is currently Go-only. The old `index` command and its parser
implementations were removed; it is not a hidden built-in. Built-in names are
reserved wherever registered; adding a command requires importing its package, not
editing a switch ladder. This is static package registration, **not** Go shared-library
plugins or runtime-loaded code. No dependency framework.

The host names `maw-go`, `maw-rs`, `maw-js`, and `maw-zig` are reserved and
excluded from discovery. Install them side by side without recursive host plugins.
