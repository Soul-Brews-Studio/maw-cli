# Installed plugin inventory

Implementation plan for issue #22: replace the command-catalog listing with a
small, read-only inventory of installed plugin metadata. Lock the new behavior
with an actual-process fixture before changing the implementations; preserve
the existing help/dispatch/inertness smoke. No unit framework or plugin execution.

## Shared contract

- `plugin ls`, `plugins ls`, and legacy `plugins` list the same inventory.
  Accept `-v`/`--verbose` and `--all` after `ls` (or after bare `plugins`).
  Unknown flags/arguments fail with usage, exit 2. No management operations.
- Read one global plugin directory: nonempty `MAW_PLUGINS_DIR`, otherwise
  `<data>/plugins`. Data is `MAW_HOME`, then `MAW_DATA_DIR`, then
  `${XDG_DATA_HOME:-$HOME/.local/share}/maw` when `MAW_XDG` is `1`, `true`,
  `yes`, or `on` (case-insensitive); otherwise `$HOME/.maw`.
- Read immediate child directories and directory symlinks only. Inspect
  `plugin.json`, never import/parse/execute `plugin.ts` or any plugin entrypoint.
  A directory with only `plugin.ts` is skipped with a diagnostic. A directory
  containing both uses JSON. Ordinary non-plugin directories are ignored.
- JSON inputs must be regular files, at most 1 MiB, valid UTF-8 JSON objects.
  Invalid/unreadable manifests are skipped with diagnostics. Require nonempty
  string `name` (ASCII letters/digits/dot/underscore/hyphen) and `version`
  (no control characters). Metadata inspection is not full SDK/schema validation.
- Sort directory names before discovery; first valid manifest name wins duplicates.
  Sort output by tier (`core`, `standard`, `extra`), then name, bytewise.
- Tier is explicit `tier` (`core`, `standard`, `extra`); otherwise weight `<10`
  means core, `<50` standard, else extra. Default weight is 50. Weight must be
  a finite number in 0..99 when present. `<plugins>/.overrides.json` optionally
  maps names to weights; valid numeric overrides replace weights, not explicit tiers.
- Configuration root is `$MAW_HOME/config`, then `MAW_CONFIG_DIR`, then
  `${XDG_CONFIG_HOME:-$HOME/.config}/maw`. Read `maw.config.<digits>.json`
  and `maw.config.<digits>.local.json`, ordered by numeric weight, non-local
  before local, then filename. If none exist, read `maw.config.json` instead.
  Each array-valued `disabledPlugins` replaces the preceding array; retain only
  string members. Missing configuration is fine; unreadable/invalid config or
  overrides fail with exit 1 rather than silently misreport enabled state.
- Active means not named in `disabledPlugins`, not runtime-loaded/verified.
  Default display hides disabled entries; `--all` includes them. Total and
  active/disabled counts always describe every accepted manifest.
- CLI surface means a non-null `cli` object, or a nonempty `entry`, `wasm`, or
  non-WASM `artifact.path`. API surface means a non-null `api` object.
  Effective entry: `entry`, else `artifact.path` when target is not `wasm`,
  else `wasm`. Health only checks that the effective entry is a regular file.
  Missing entry declarations count as missing when a CLI surface is declared.
  Paths may be absolute or relative to the plugin directory; normalize them
  lexically (without resolving directory symlinks), then check. Never execute them.
- Empty inventory prints `no plugins installed`. Default output is:

  ```text
  N plugins (A active, D disabled)
    core: C · standard: S · extra: E
    cli: L · api: P · health: ok
    name-a · name-b
  ```

  Use singular `1 plugin`. Tier/surface/health/names describe displayed entries.
  Missing-entry health is `N missing executable` / `N missing executables`.
  Omit the names line when no entries are displayed. If disabled entries are
  hidden, append `  disabled hidden by default — use --all to include`.
- Verbose output contains one tab-separated row per displayed entry, no header:
  `name`, `version`, `tier`, `enabled|disabled`, absolute plugin directory.
  Escape control characters in displayed filesystem paths so they cannot inject
  terminal control sequences or extra rows.
- `HOME` (or `USERPROFILE`) supplies defaults. When unset, explicit data/plugin
  and config roots are sufficient; otherwise fail instead of guessing a home.

## Boundaries and evidence

Source reviewed: maw-js `5ee396a7f61def2ee2a8774d3f6da216e069c6c2`, especially
`src/commands/shared/plugins-ls-info.ts`, `src/plugin/registry.ts`,
`src/plugin/manifest-load.ts`, `src/core/xdg.ts`, and `src/core/paths.ts`.
Serena declarations and CodeGraph/source references were cross-checked.

This lean global inventory deliberately does not emulate project/ancestor plugin
roots, active profiles, config migrations, SDK compatibility gates, artifact
hash verification, or executable TypeScript manifests. `health: ok` means only
that declared entry files exist, not that plugins are safe or runnable.
Built-ins/PATH commands remain visible through `help`; their execution protocol
is unchanged. No install/update/enable/disable operations and no `index` command.
Rust may reuse `serde_json` for this metadata only, explicitly approved by the user.

Regular-file checks and bounded reads are not a filesystem sandbox: concurrent
replacement between stat/open is not race-proof. Do not use listing to validate
an adversarially changing plugin tree.
