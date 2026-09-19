# Automatic alpha prebuilt releases

A successful **push CI run on the canonical `alpha` branch** starts
[Alpha prebuilt release](https://github.com/Soul-Brews-Studio/maw-cli/actions/workflows/release.yml).
GitHub builds and publishes in the background; no local waiting or per-tag approval
is required. This implements the user's September 19 authorization for public
prebuilt uploads. PR/fork CI never grants publication authority.

## What ships

Native builds smoke all four ports on these [hosted runners](https://docs.github.com/en/actions/reference/runners/github-hosted-runners):

| Platform | x64 (`amd64`) | ARM64 (`arm64`) |
| --- | --- | --- |
| Linux | `ubuntu-24.04` | `ubuntu-24.04-arm` |
| macOS (`darwin`) | `macos-15-intel` | `macos-15` |

The public prerelease contains **16 archives**, `SHA256SUMS`, and `release.json`.
Each `maw-{go,rs,js,zig}-{linux,darwin}-{amd64,arm64}.tar.gz` contains only:

- `maw-go`, `maw-rs`, `maw-js` or `maw-zig`: the selected native executable;
- `RELEASE.json`: source commit, tag, language, platform and binary SHA256.

Go adds `context`; the other shared commands are available in all ports. Bun's
[standalone executable](https://bun.com/docs/bundler/executables) embeds Bun.
Linux compatibility is measured on Ubuntu 24.04, not every libc/distribution;
macOS downloads are not developer-signed or notarized. No Windows build is provided.

Only selected release outputs are uploaded. Transcripts, local indexes,
configuration and raw benchmark inputs remain private. Temporary Actions artifacts
expire after seven days; public downloads belong on [Releases](https://github.com/Soul-Brews-Studio/maw-cli/releases).
Alpha prereleases are not GitHub's `latest` release.

## Immutable CalVer selectors

The pinned upstream [pure `computeVersion` export](https://github.com/Soul-Brews-Studio/arra-oracle-skills-cli/blob/68110ad0641f5b7bc8a14a988971ff4ead9ad77a/scripts/calver.ts)
provides the Bangkok calendar date and integer hour*100+minute. The source is
SHA256-verified before import; its mutating main entrypoint is never executed.
No Go version calculator or runtime dependency is added.

The successful source CI run's creation time gives deterministic selectors in
`Asia/Bangkok`:

- Root release tag: `vYY.M.D-alpha.HMM`.
- Nested Go tag: `src/go/v0.YYYYMMDD.HMM-alpha`.
- `HMM = hour * 100 + minute`, without leading zeros: September 19, 2026 at
  09:37 becomes `v26.9.19-alpha.937` (format example, not a promised release).
- Both point to the same full source SHA. The CI run ID stays in provenance
  metadata, never in the version suffix.

Use a published root tag after `#` in bunx. Use `go_version` from `release.json`
after `@` in `go run/install .../src/go/cmd/maw-go`. The `v0` companion respects
[Go nested-module rules](https://go.dev/ref/mod#vcs-version) without changing the
module path. `alpha` remains the moving development branch. Previously published
run-qualified tags remain unchanged; this format applies to new releases.

## Trust, retries and failure

`prepare` validates the upstream workflow path, repository, event, branch,
conclusion and exact SHA. Every job checks out that SHA, not workflow_run's
default-branch SHA. Build jobs are read-only; only `publish` gets `contents: write`.
Publication revalidates CI evidence and the complete archive set, binary format,
architecture, metadata and checksums before creating immutable tags.

Assets upload to a draft, then publish only after all 18 match. A matching draft
can resume; a matching complete release is a no-op. Existing tags and assets are
never moved or clobbered. A rebuilt binary with different bytes is rejected,
not silently substituted; retry the failed publish job with its original artifacts.
Rerunning the same source CI run retains its creation time and tags. A different
source SHA in the same minute must not reuse an existing tag; publication refuses
the collision. If artifacts expired or a collision needs a new timestamp, use a
genuinely new source CI run created in a later minute, not GitHub's rerun action.

If alpha advances, stale work skips instead of relabeling old binaries. A race may
leave an unpublished draft or tags; inspect the run before recovery. Never force
move tags or use `--clobber`. Keep tag creation and publication in this workflow:
[GITHUB_TOKEN events do not start ordinary downstream workflows](https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/trigger-a-workflow).

## Local tools

```sh
just go release      # read-only CalVer preview; not a Go builtin
just release prepare CI_RUN_ID /tmp/release-plan.json
# Mutating recovery: only with the exact verified plan and original CI archives
just release publish /tmp/release-plan.json /path/to/release-assets
```

These development helpers need Python 3, Bun, Git and authenticated `gh`.
Preview never commits, tags, pushes or publishes. See the [run guide](../README.md#run-maw)
for download and source commands.
