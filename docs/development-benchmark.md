# Development-window evidence (not a language productivity ranking)

## Recovered historical observations

On 2026-09-19, `relic index`, `relic session <session-id> --json`, and
`relic read <resolved-transcript> --json` recovered the original implementation
dispatch markers and first explicit completion reports below. Raw transcripts,
private filesystem paths, and message bodies remain local and are not committed.
Session identifier: `01a0b746-d27a-7e41-9389-75d59d083fa6`.

**The measured development vector is an observed prototype delivery window:
assignment to first confirmed success report.** Each window is an upper bound
on delivery of the reported compile/smoke milestone, not an exact first-success
instant and not active coding time. Relic presents some tool
results without payloads and assignment bodies as encrypted text. Tool-call
timestamps alone cannot establish success; therefore we use explicit completion
reports, not an inferred successful exit. Earliest actual successful compile/smoke
timestamps remain **unmeasured**. Child inherited history is not new work and was
excluded from endpoint selection.

Stage definitions:

1. **Assignment:** the root dispatch marker for the named implementation task;
   it includes scheduling delay before the child begins work.
2. **Implementation and integration:** source creation, reference lookup,
   compilation attempts, fixes, and any parent integration or scope changes.
   These activities are not separately timed in this historical evidence.
3. **Confirmed delivery report:** the first recovered explicit report confirming
   both compilation and execution of actual CLI smoke checks. The endpoint
   includes reporting latency; it is not inferred from a tool call alone.

Thus the delivery window is measured boundedly, while exact compile latency,
active development effort, and per-stage effort cannot be recovered from these
events. Compiler/startup measurements elsewhere use separate timed processes.

All timestamps below are UTC on 2026-09-19:

| Original implementation | Dispatch marker | First recovered explicit compile + CLI smoke report | Observed window |
|---|---|---|---:|
| Go | 02:01:55.892 | 02:15:45.686 | 829.794 s |
| Rust | 02:24:47.096 | 02:27:07.398 | 140.302 s |
| Bun/TypeScript | 02:25:01.401 | 02:27:12.469 | 131.068 s |
| Zig | 02:27:49.077 | 02:30:59.906 | 190.829 s |

The Go initial child report at 02:05:25.348 establishes tests/vet, **not** an
actual CLI smoke endpoint. Its longer window includes parent integration,
toolchain setup, a user scope change removing initial tests/release machinery,
and the subsequent compile/smoke tooling. Rust/Bun/Zig reuse the existing Go
behavior and reference work; Zig received prior API research. Tasks overlapped,
agents and acceptance scopes differed, and waiting/report latency is included.
These differences preclude fair language or model speed rankings.

### Audit identifiers

Relic sequence numbers refer to their own transcript, not a global sequence.
The root transcript supplies dispatches; child identifiers below resolve through
the session family. UIDs allow local revalidation without publishing raw text.

| Language | Start root seq / UID | Report transcript identifier / seq / UID |
|---|---|---|
| Go | 864 / `e0e9c2718e34cf3746263d6b5f0cc15c7123060d` | root / 1065 / `d42f8eb462a7897024df648127d8c0ffdfe0bcf7` |
| Rust | 1230 / `4688758822a502948b91bff8826617241b7997a6` | `01a0b77b-0306-7482-ada1-af0cd8568c72` / 67 / `46a37b4ca38a4839ef8ac934e4a324530c76c2a8` |
| Bun | 1236 / `67a3357b2a42037b70fbcf080e25f7e321480946` | `01a0b77b-3aed-7e11-bcfc-c6e8eeed0e9e` / 73 / `7222ee4f9d59a014ac87428aded4dcfcfcb1fbf5` |
| Zig | 1291 / `fe47c5bee6bdf8c465247ae75fc6204f732ccabd` | `01a0b77d-c9ea-7832-a9f6-5a506181d722` / 101 / `7a7195d5ef69c53f8fcde9a67f7a8b78e644f1ee` |

Initial compile/smoke occurred on dirty worktrees, so a precise endpoint source
commit is unavailable. Subsequent source checkpoints are Go `d162982` (host),
`a83d0ad` (smoke tasks); Rust/Bun `76daa74`; Zig `0d494d9`. These commits anchor
reviewable artifacts, **not** exact endpoint snapshots.

## Source overhead boundaries

Reproduce the initial shared milestone from committed files, not today's expanded
Go MCP/framework code or generated bundles:

```sh
python3 scripts/development-evidence.py footprint --commit 0d494d9
```

Snapshot: `0d494d9e460f1bda64ccb0685c236a166dc8621a`.

| Implementation | Implementation physical lines | Build/manifest/lock physical lines |
|---|---:|---:|
| Go | 221 | 3 |
| Rust | 195 | 16 |
| Bun/TypeScript | 134 | 9 |
| Zig | 178 | 13 |

Implementation includes entrypoint, help/dispatch, and external-plugin code.
Zig's executable build script is counted separately, as are Cargo lock/manifest,
Go module, and Bun package metadata. Comments and blank lines count; generated
outputs, dependencies, shared smoke/benchmark scripts, docs, and installed
toolchains do not. This is reviewable **source footprint**, not binary size,
runtime footprint, semantic complexity, maintenance cost, or developer effort.
Signal-forwarding/platform behavior differs among these prototypes; sharing the
smoke contract does not imply complete behavioral equivalence.

## Forward measurement for the next increment

```sh
python3 scripts/development-evidence.py start issue-next-go
# Perform the bounded implementation, compile, and actual CLI smoke.
python3 scripts/development-evidence.py finish issue-next-go --verified-compile-smoke
```

Records stay under ignored `benchmarks/cli/results/development/`. Use a new
non-sensitive label for each increment. Start records cannot be overwritten;
finish requires explicit operator attestation of compile/smoke success, not an
automatic inference. The script records monotonic elapsed wall seconds, UTC,
source commits, and dirty flags without shell history or transcript contents.
Start/finish must run on the **same continuously running host**. Failed attempts,
interruptions, waiting, and parallel activity remain included; record scope and
toolchain differences when interpreting the interval. A start/finish near an
actual success provides a tighter observation, still not active coding effort.

This development vector complements startup/build measurements in
`benchmarks/cli/README.md` and trace-index workload measurements; none substitutes
for the others. No universal ranking or productivity speedup is claimed.
