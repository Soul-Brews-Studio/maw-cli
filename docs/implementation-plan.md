# Lean maw CLI: scope and acceptance

## Goal

Build a dependency-free Go CLI named `maw`, runnable from this GitHub module.
Ship a help-first plugin host, not a partial reimplementation of all of maw-js/maw-rs.
Keep learning evidence in Serena memories and use both Serena and CodeGraph to
inspect reference relationships. Preserve the private GitHub repository's visibility.

## First increment

1. A single descriptor registry supplies built-in `help`, `version`, and `plugins`.
2. No arguments and `--help` show deterministic available-command help. Unknown
   commands/flags fail; never silently dispatch a guessed alias or no-op stub.
3. External executable `maw-<command>` plugins are opt-in through absolute PATH
   directories. Discovery never executes code. Built-ins cannot be shadowed.
   Dispatch preserves argument boundaries/case, standard streams, and exit status.
4. Describe future command families as separate plugin responsibilities, explicitly
   not implemented. No tmux, server, agent launch, configuration database, native
   Go shared-library plugins, or third-party dependencies in this increment.
5. Compile first, then smoke-call the real binary and a harmless temporary plugin.
   Unit tests wait for the user's mark. Keep modular just tasks and record timings.
6. Provide Go run/install from GitHub instructions including private-module access;
   verify an actual remote revision from outside this checkout after shipping source.
7. Use the installed `$calver` skill only at the release handoff. It targets arra,
   not this Go module: do not create a replacement Go version engine. No release
   automation, binary archives, uploads or tags in this increment.

## Lean-down plan (latest user update)

Remove the unshipped unit tests, custom CalVer packages, and archive/release
automation from the earlier draft. Retain the small command host; use actual
CLI smoke checks as the behavior guard. Simplify version display to Go build info.
Rewrite documentation and CI to match this compile-first, source-only scope.

## Shipping boundary

Issue #1 precedes implementation shipping. Seed the empty private repo with the
shared instructions on `alpha`, then use small feature-branch commits and a PR
targeting `alpha`. Merge after compile/smoke verification and sync local `alpha`.
Do not change visibility or send private module requests to a public Go proxy.
Do not commit raw session data, local indexes, binaries or unrelated artifacts.
