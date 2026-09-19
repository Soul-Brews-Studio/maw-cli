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
