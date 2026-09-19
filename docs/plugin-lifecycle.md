# Basic plugin lifecycle

Lifecycle belongs to maw-cli, not individual plugins. Each language port uses
Git as the existing source/version boundary; there is no registry service,
background updater, package builder, or extra runtime library.

```sh
maw-go marketplace                       # small built-in catalog
maw-go plugin install herdr              # default Git branch
maw-go plugin install Soul-Brews-Studio/maw-herdr-plugin --ref FULL_COMMIT_SHA
maw-go plugin ls                         # plugin list and plugins ls also work
maw-go plugin info herdr                 # source, commit, entry Git-blob hash
maw-go plugin check herdr                # compare entry bytes with committed blob
maw-go plugin update herdr               # clean default branch: fast-forward only
maw-go plugin update herdr --ref FULL_COMMIT_SHA
```

Replace `maw-go` with `maw-rs`, `maw-js`, or `maw-zig`. This is the new polyglot
maw-cli; it does not change an unrelated older `maw` executable on PATH.

## Go archive installations

```sh
maw-go plugin install ./package.tar.gz
maw-go plugin install ./package.tgz --backup
maw-go plugin install https://github.com/OWNER/REPO/archive/COMMIT.tar.gz --replace
```

This explicit tarball route needs no Git, tar command, compiler or added library.
It accepts local regular `.tar.gz`/`.tgz` files and HTTPS URLs with those path
suffixes (query strings allowed, URL credentials/fragments forbidden). Existing
Git directories/URLs and marketplace shorthand retain the Git behavior below.
`--ref` is for Git sources, not archives: encode the source ref in the archive URL.
Only Go supports this route; the other ports remain Git-only installers.

- Extract into private staging under the configured plugin root. Accept a root
  `plugin.json` or exactly one enclosing directory (GitHub archive layout).
  Global PAX metadata is ignored; resolved member paths are still validated.
- Reject traversal/absolute/backslash/control paths, `.git` contents, duplicate
  members, symlinks, hard links and special files. Only directories and regular
  files are materialized. Preserve executable bits, discard special permission
  bits. Compressed input is limited to 128 MiB, the uncompressed stream to
  512 MiB, returned tar headers to 4096, manifests to 1 MiB. Verify gzip CRC.
- Require valid name/version/entry and an in-tree regular entry file. If declared,
  validate `artifact`/`bundledArtifacts` paths and SHA-256 digests; these are
  package self-consistency checks, not independently trusted signatures. The
  archive must come from a trusted source. Never execute package code on install.
- Download only over HTTPS with a two-minute timeout and bounded HTTPS redirects.
  No authentication token is loaded or forwarded. Private Actions downloads are
  not automatic; download/unzip the CI artifact separately and install its tarball.
- For an existing real directory, prompt for `[B]` backup-and-replace (Enter is
  the default), `[r]` replace without a lasting backup, or `[c]` cancel. EOF also
  cancels. Piped input cannot authorize replacement; scripts supply exactly one
  of `--backup`/`--replace`. Existing symlinks and non-directories are refused.
- Use a per-plugin install/update lock and recheck destination identity after the
  prompt. Keep backups at `<resolved-plugin-root>-backups/<unique>/<name>`, outside
  inventory discovery. Local edits and all old files are preserved with `--backup`.
  Replacement moves the old directory aside, promotes the staged candidate, and
  restores the old directory on ordinary promotion failure. If restoration fails,
  preserve its recovery path. This two-rename operation is not a crash-atomic swap;
  interruption can leave a lock and an old copy requiring manual recovery.
- No archive auto-update/provenance registry is added. `info`, `check` and `update`
  retain their real-Git-checkout requirement and direct archive users to reinstall.
  `plugin ls -v`/marketplace still show ordinary non-Git installed metadata.

For Herdr serving, choose a native **package**, not GitHub's source tarball.
The ready-to-run package contains `index.js`, `plugin.json`, and
`bin/maw-herdr-serve`; Bun and Herdr remain runtime requirements. Source archives
do not become native packages merely by extracting them.

## Small contract

- `marketplace [ls|list]` prints a header and the known `herdr` repository. It is
  a static convenience list, not a package registry or a trust endorsement.
  Go additionally reports local installed/disabled/invalid status, manifest
  version, available branch/exact-tag/detached ref and 12-character Git commit.
  No network lookup. Missing metadata is `-`; corrupt/unreadable Git metadata
  produces a warning, not invented version information. Non-Git installs still
  show their manifest version.
- `plugin install SOURCE [--ref REF]` accepts `herdr`, `owner/repo`, an HTTPS Git
  URL, or an existing local Git directory. `owner/repo@REF` is shorthand.
  Go also accepts SOURCE#REF, HTTPS URL selectors, and update NAME@REF/NAME#REF.
  These normalize to --ref; duplicate or empty selectors fail. Existing local
  directories with literal @/# names take precedence over selector parsing.
  Quote # arguments for shell safety. Other ports retain existing --ref syntax.
  This basic installer targets public HTTPS/local repositories; ambient Git
  configuration and interactive credential prompts are disabled.
  Install into the existing configured plugin root. Never overwrite an existing
  destination. Clone into a temporary sibling, validate, then rename into place.
- Keep the Git checkout and all source files. No hooks, build scripts, plugin
  entrypoints, submodules, or Git LFS commands are run by the installer. Git
  commands disable repository hooks; plugin code runs only on explicit dispatch.
- With `--ref`, fetch the requested branch/tag/full 40-hex SHA and check out its
  resolved commit detached. A full SHA must match exactly. Explicit refs remain
  pinned; `update NAME` reports the pin without changing it. `update NAME --ref
  REF` deliberately changes the pin. Unpinned installs track their default branch
  and update with fast-forward only.
- Refuse updates with tracked changes or untracked files. Validate candidate
  `plugin.json` name/version/entry before changing the checkout; keep the plugin
  name stable. No force/reset/clean operation is offered. Plugin directories must
  be real directories, not symlinks, and their own Git checkout, not a parent repo.
- `info`/`check` show `source`, full resolved `commit`, `entry`, `hash`, and
  `status` (`clean` or `modified`). The hash is explicitly Git's blob hash, **not
  an archive checksum, SHA-256 pin, signature, or publisher identity**. Hash the
  actual entry bytes with `git hash-object --no-filters` and compare to HEAD's
  blob; never print a stored hash as if it were reverified. `check` exits nonzero
  on modifications. Checkout transformations such as CRLF conversion also differ
  from raw committed bytes; installation can succeed while this check flags that
  difference. These commands initially require a Git-managed installation.
- Validate a root `plugin.json` (bounded JSON object), safe plugin name, nonempty
  version, and regular in-tree entry (`entry`, falling back to `artifact.path`
  then `wasm`). Reject symlink traversal and absolute/parent-relative entries.
  Do not let malformed metadata write outside the plugin root.
- `plugin` and `plugins` accept the same explicit verbs; legacy bare `plugins`
  still lists. Missing/unknown arguments exit 2; operational failures exit 1.
  Listing/help stay read-only. No shell interpolation of plugin input.

Git installation does **not** download native prebuilts. For Herdr serving, use
the native package from its CI separately, or explicitly run the complete source
checkout with `serve --build` and Go installed. There is no automatic compiler
fallback. Git-blob verification does not replace Herdr's bundled-helper SHA-256
verification.
