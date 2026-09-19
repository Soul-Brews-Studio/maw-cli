# Source-only release, explicit approval gate — issue #7

`go release` is **not a Go builtin**. Use `just go release` (an alias for
`just release preview`). It does not bump a package, commit, tag, push, or publish.
Bun, Python 3, Git and authenticated `gh` are development prerequisites.

The installed `$calver` skill targets arra-oracle-skills-cli. We reuse its
[upstream pure `computeVersion` export](https://github.com/Soul-Brews-Studio/arra-oracle-skills-cli/blob/68110ad0641f5b7bc8a14a988971ff4ead9ad77a/scripts/calver.ts)
from a commit- and SHA256-pinned temporary download, rather than creating a Go
version calculator or modifying that external repository. No new runtime CLI
dependency is introduced. The upstream CLI `--check` can repair invalid dates in
package.json before its check guard; **do not execute its main entrypoint here**.

Scheme: `vYY.M.D-alpha.HMM`, Asia/Bangkok, integer hour*100+minute with no leading
zeros (the skill's actual format, not zero-padded SemVer components). Same-minute
collisions fail instead of overwriting tags. Preview also generates notes using
GitHub's releases/generate-notes endpoint, following merged PRs and their linked
issues. It prints the exact commit and proposed tag for review. No release asset
or raw transcript is uploaded.

After the user explicitly approves a particular previewed tag and alpha commit:

```sh
just release publish <approved-tag> <approved-full-alpha-SHA>
```

Publication requires tracked-clean `alpha`, the exact matching remote SHA, all
eight successful Linux/macOS language checks, and an absent remote tag. It creates
an annotated source tag and prerelease with generated notes, **no binaries**.
An interrupted publish can leave a pushed tag without a release; inspect the exact
tag and use `gh release create --verify-tag` to recover after renewed approval.
Never force-delete or move published tags. No automatic push-triggered release.
The mutating publication branch remains deliberately unexecuted until approval.

## Go install selectors

Yes: `@alpha` can coexist with immutable alpha CalVer releases. It names the
moving **branch**, not a release. Today there are no published release tags;
use `@alpha` for current code or `@<commit>` for a fixed snapshot.

For the nested `src/go` module, a Go-compatible CalVer release could use:

- Git tag: `src/go/v0.20260919.1020-alpha`
- Install selector: `@v0.20260919.1020-alpha`
- Command path: `github.com/Soul-Brews-Studio/maw-herdr/src/go/cmd/maw`

This is a **proposed, unpublished companion tag**, not something the current
release script creates. It keeps the import path stable: a `v26.9.19-alpha.1020`
Go semantic version would require a `/v26` module suffix. The existing script's
repository-wide CalVer tag can remain the human release name, with a future
Go-module companion tag pointing to the same commit. Alternatively, a non-semantic
repository tag such as `alpha-26.9.19.1020` can be queried as a revision; Go normally
records that as a pseudo-version. None of these example tags has been published.

Go's `@latest` prefers stable releases over prereleases; it is not an alias for
our alpha branch. See [Go version/tag mapping](https://go.dev/ref/mod#vcs-version)
and [version queries](https://go.dev/ref/mod#version-queries).
