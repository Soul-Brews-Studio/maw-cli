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

Repository CalVer tags are not Go module semantic-version tags: the nested module
has no `/v26` suffix. Continue using `go run/install .../go/cmd/maw@alpha` or an
exact commit (shown in preview), rather than promising `@latest` resolves CalVer.
This preserves the lean module path while retaining calendar-tagged source.
