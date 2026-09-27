# Go self-update

```sh
maw-go update --check
maw-go update
maw-go update --version v26.9.19-alpha.1547
```

Go-only, standard library, no runtime tool dependencies. `maw-go` is separate
from an older installed `maw`; `maw go` is not an alias. Bootstrap an old Go
installation lacking this command with the README's `go install ...@alpha`.

## Small contract

- Default selects the numerically newest `vYY.M.D-alpha.HMM` among the newest
  30 published GitHub releases in Soul-Brews-Studio/maw-cli. Drafts and legacy
  run-ID tags are excluded. This is a published prebuilt, not the moving branch.
  `--version TAG` selects an exact published tag and explicitly permits
  reinstall/downgrade. There is no stable channel, daemon or plugin update here.
- `--check` reports current version, selected tag, source commit and status;
  downloads metadata only, never an executable or local installation state.
  Errors/rate limits are reported, not treated as "up to date".
- Native prebuilt CalVer and Go companion versions compare numerically.
  Go pseudo-version installs use GitHub's bounded commit comparison to ensure
  the candidate is the same source or a descendant, not a release of older
  code published later. A newer/diverged source waits for a release unless
  `--version` was explicit. Local `dev`/`go run` builds refuse mutation.
- Downloads use fixed repository HTTPS URLs, bounded response sizes/timeouts
  and an explicit GitHub release redirect-host allowlist. No arbitrary URL,
  authentication-token forwarding, shell installer or automatic tool install.
- Validate SHA256SUMS entries for the archive and release.json; cross-check
  tag/commit/schema and archive membership. Require exactly two regular USTAR
  members: maw-go and RELEASE.json, matching platform, executable header/mode,
  binary SHA-256 and source commit. Check gzip CRC and bound decompressed data.
  Executable size is at most512MiB; metadata/download limits reject oversized input.
- Resolve the running executable, including symlink aliases. Lock that target,
  create a private sibling staging directory, close/sync the candidate, run
  its exact `version` with empty PATH and a short deadline. Only after all
  checks pass, recheck the old file's identity and replace it with one
  same-filesystem rename. Failed download/validation/proof leaves the old file
  in place; there is no gap from moving it to a backup first.
- No sudo: the installation directory must be writable. A concurrent updater
  or leftover `<executable>.update-lock` causes a clear failure, not lock theft.
  After a killed process, verify no updater is running before removing its
  stale lock. Ordinary failures clean their lock and temporary directory.
- Does not modify plugins, config, Bun, the Go module cache or other hardlink
  names. Linux/macOS amd64/arm64 only. Existing prebuilt platform/libc limits
  still apply; candidate proof catches startup failures, not every regression.

Checksums and metadata come from the same GitHub release over TLS. They detect
mismatches/corruption; they are **not independent publisher signatures**.
Candidate version proof is not a full compatibility test or sandbox.

## Verification

`python3 utils/scripts/update-smoke.py` builds isolated binaries and serves
fixture releases over local TLS. Source overlays replace origins/CA roots only
in those fixture builds; production has no test URL/target overrides. Fixtures
need Go and openssl, not updater users. Actual processes cover success, aliases,
read-only checks, malformed/corrupt payloads, candidate proof failure and
source/downgrade decisions with an empty runtime PATH. No unit framework.

Source ancestry API: [GitHub compare-two-commits](https://docs.github.com/en/rest/commits/commits#compare-two-commits).

## js port (`maw-js update`)

```sh
maw-js update --check
maw-js update
maw-js update --version v26.9.28-alpha.348
```

A port of the contract above, command for command, using only Bun/Node
built-ins (`fetch`, `node:zlib`, `node:crypto`) and a hand-written tar reader.
Same selection, `current`/`target`/`commit`/`status`/`updated` lines, size
limits, redirect-host allowlist, 90 s download and 3 min overall deadlines,
exact-member archive rules (`maw-js` and `RELEASE.json` only, metadata
`language` `js`), candidate `version` proof and single same-directory rename.
Differences, all deliberate:

- `release.json` must also carry `skip: false`, as every published plan does.
- maw-js embeds only a release tag or `dev`, so there is no pseudo-version or
  Go companion-tag branch; any other embedded string is reported as unrecognized.
- Only a standalone executable replaces itself. A script run (`bun cli.ts`,
  `bun link`, `bun add --global`) has the bun runtime as its `process.execPath`
  and is refused before any download, whatever version it reports.
- A `dev` build refuses to replace anything. From a git checkout of this
  repository it prints the fix with the real path instead, adding
  `switch alpha` when on another branch and saying when the tree is dirty
  (read-only: `git symbolic-ref` and `git status --porcelain`):

  ```
  maw: update: this maw runs from a source checkout; update it with git
    git -C /path/to/maw-cli switch alpha
    git -C /path/to/maw-cli pull --ff-only
  ```

  Outside a checkout it prints the `bun add --global` reinstall command.
  `--check` still reports release status from any `dev` build.
- Every failure ends with a copy-pasteable command that fixes or narrows it
  (for example the `curl -sSIL` of the URL that failed, or the stale lock's `rmdir`).

`python3 utils/scripts/update-smoke.py -- BUN ENTRY` (run by `smoke.sh` for the
source-run js port) copies `src/js/src` into a throwaway git checkout, rewrites
only the origins there, compiles fixture executables with `bun build --compile`
and serves releases over local TLS, the same overlay approach as Go. It replaces
only copies in a temporary directory and never runs `--check` through the real
ENTRY, which would reach GitHub.
