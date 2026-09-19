# maw-herdr

A small Go `maw` CLI. Help first, operational commands as executable plugins.
Standard library only. No server, tmux engine, plugin installer or release engine.

## Run from GitHub — like `bunx` / `npx`

With Go 1.22+ and Git access to this **private** repository:

```sh
GOPRIVATE=github.com/Soul-Brews-Studio/maw-herdr \
  go run github.com/Soul-Brews-Studio/maw-herdr/cmd/maw@alpha --help
```

`go run ...@alpha` downloads and runs the branch; use `@<commit>` to pin a revision.
Unlike `npx`, Go must be installed first. `GOPRIVATE` bypasses the public module
proxy/checksum service; it does not supply Git credentials. Configure Git access
separately (SSH or a credential helper). Preserve any other existing GOPRIVATE
patterns. [Go command docs](https://go.dev/doc/go1.17#go-command),
[private module docs](https://go.dev/ref/mod#private-modules).

To install a persistent executable:

```sh
GOPRIVATE=github.com/Soul-Brews-Studio/maw-herdr \
  go install github.com/Soul-Brews-Studio/maw-herdr/cmd/maw@alpha
```

The binary is `maw`, under `GOBIN` or `$(go env GOPATH)/bin`.
**Check for an existing `maw` first**—other maw tools may use the same name.
Set `GOBIN` to a separate absolute directory to keep installations apart.

## Commands

```sh
maw --help
maw help plugins
maw version
maw plugins
maw <plugin> [args...]
```

No arguments show help. Unknown commands fail with exit 2. Local builds display
`dev`; remote builds display Go's module version. Future command families are
in [docs/plugins.md](docs/plugins.md), not advertised as working stubs.

## Add a plugin

Place an executable `maw-hello` in an absolute directory on PATH:

```sh
#!/bin/sh
case "${1:-}" in
  --help) printf 'Usage: maw hello [name]\n' ;;
  *) printf 'hello %s\n' "${1:-world}" ;;
esac
```

Then `maw hello Ada` runs it. Discovery is file-only: root help and listing do not
execute plugins. `maw help hello` explicitly runs `maw-hello --help`. Built-ins
cannot be shadowed. Plugins run without a shell wrapper; argv, streams and
ordinary exit codes pass through. Plugins are trusted local programs, not
sandboxed. The example is for Linux/macOS; Windows plugins are `.exe` files.
See the [contract](docs/plugins.md).

## Develop — compile, then smoke

```sh
just                       # list tasks
just dev check             # timed build once + actual CLI smoke calls
just dev build             # bin/maw
just dev smoke             # reuse bin/maw, no rebuild
```

Without `just`: `sh scripts/check.sh`. Unit tests are intentionally deferred until
requested. CI compiles and smoke-calls on Linux and macOS; it uploads no artifacts.
Keep Go's build cache warm and use the compiled binary, not repeated `go run`.
Timing samples measure this machine/command/cache state, not a universal speedup.

Work follows issue → feature branch → PR into `alpha` → merge → sync `alpha`.
No tags or release automation in this bootstrap. `$calver` is the release handoff,
but the installed skill currently targets **arra-oracle-skills-cli**, not this
module. Do not run its apply step here or build a replacement version engine.

## Learning

[Architecture and source traces](docs/architecture.md) record what we borrowed
from maw-js and maw-rs and what we deliberately left out. Serena retains
`learning/index`; CodeGraph provides complementary call-graph evidence. Relic
indexes local conversation history (`relic index`); transcripts and index databases
are not shipped. Shared contributor guidance lives in [AGENTS.md](AGENTS.md),
with `CLAUDE.md` as its relative symlink.
