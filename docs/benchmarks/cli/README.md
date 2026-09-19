# CLI measurements

Run from the checkout with Python 3 and the selected toolchains on PATH:

```sh
python3 utils/scripts/benchmark.py
python3 utils/scripts/benchmark.py --languages go rs js --samples 20 --warmups 3
python3 utils/scripts/benchmark.py --builds --build-samples 3
```

Results default to ignored `results/<UTC timestamp>.json`; `--output PATH` writes
a new file without overwriting existing evidence. No results or binaries upload.

## Method

- Build each selected implementation using its normal optimized production
  command, then run the same actual-CLI smoke script. Abort on failure; do not
  report timing for a broken implementation.
- Measure a new `--help` process per sample with `perf_counter_ns`, including
  subprocess launch/wait overhead. Bun's runtime process is included, not just
  its bundled JavaScript. Absolute executable paths use the same empty absolute
  PATH directory to prevent discovery of installed operational plugins.
- Discard stdout consistently; capture stderr for failures. Rotate language order
  round-robin across warmups and measured rounds. Record raw warmups/samples and
  median milliseconds, exact commands, working directories, tool versions, OS,
  architecture, Git SHA, source-scoped dirty flag, per-file SHA256 and end SHA.
  Discard results if measured sources change during the run. Keep normal Go cache for the
  prerequisite build. Startup samples are **not OS-cold-cache** measurements.
- `--builds` additionally creates fresh temporary Go GOCACHE, Rust target, and
  Zig local/global compiler-cache directories and output prefix. Run one first
  build, smoke its output, then at least two repeated builds in those directories.
  Never clear global caches. OS page caches and installed toolchains remain warm.
  Bun is labeled **fresh-output/repeated bundle**, not cold compiler-cache build.
- Build timings include compiler process overhead and use language-native build
  strategies; they are not identical compiler workloads. Initial normal-cache
  build times are prerequisite observations, not the isolated-cache comparison.

Physical source line counts are descriptive footprint only. Historical development
[delivery windows](../../development-benchmark.md) are bounded observations, not
exact coding time. The separate index workload below measures real parsing/postings.
Neither establishes overall productivity or general language superiority.

## Historical help-only snapshot — 2026-09-19

Source `0d494d9e460f1bda64ccb0685c236a166dc8621a`, measured sources clean and
unchanged throughout. Linux x86_64, Go 1.27.1, Rust/Cargo 1.69.0, Bun 1.3.11,
Zig 0.16.0; Python 3.12.3. Original command (before source reorganization):

```sh
python3 scripts/benchmark.py --samples 20 --warmups 3 --builds --build-samples 3
```

| Implementation | Help startup median | First isolated build | Repeated build median | Source lines |
|---|---:|---:|---:|---:|
| Go | 1.818 ms | 2547.715 ms | 44.043 ms | 221 |
| Rust | 0.790 ms | 551.728 ms | 38.618 ms | 195 |
| Bun JS | 15.880 ms | 5.138 ms* | 4.740 ms | 134 |
| Zig | 1.068 ms | 18793.235 ms | 107.780 ms | 191 |

20 startup samples after 3 warmups; 1 first build and 3 repeats. *Bun's first
build is fresh-output bundling, not an isolated compiler cache. Source lines
include blanks/comments/build source, not manifests, and do not measure effort.
Raw commands, versions, fingerprints and samples remain local in ignored
`results/20260919T023414.390797Z.json`. Re-run for your machine; these results
describe only these prototypes, configurations and this workload.

## Expanded CLI / source-layout snapshot — 2026-09-19

Clean, unchanged source `9cd5e6b000af4542d0e412af647b1849115abbd9`.
Linux x86_64, Python3.12.3, Go1.27.1, Rust/Cargo1.69.0, Bun1.3.11, Zig0.16.0.
Rust registry sparse; dependencies already downloaded before isolated target builds.
Commands (run sequentially):

```sh
python3 utils/scripts/benchmark-index.py --samples 5 --warmups 1
python3 utils/scripts/benchmark.py --samples 20 --warmups 3 --builds --build-samples 3
```

| Port | Help median ms | Isolated first build ms | Repeated build median ms |
|---|---:|---:|---:|
| go | 2.014 | 3221.206 | 51.500 |
| rs | 0.897 | 3166.793 | 38.584 |
| js | 17.571 | 5.288 | 5.052 |
| zig | 1.109 | 21734.079 | 107.433 |

20 help samples after3 warmups; one cache-isolated first build,3 repeats. Bun
remains fresh-output bundling, not compiler-cache isolation. Go now includes MCP
and command modules, unlike the other ports; startup/compile footprints differ.
No OS caches were cleared. The worktree/shared machine is not an isolated lab.

### Normalized MCP JSONL index

12,000 generated records,19,862,350 input bytes,18,242,720 decoded text bytes;
2,000 unique `(file,symbol)` pairs,2,265 terms,120,000 retained postings.
Every output matches independent checksum `2620ae0bb6b14a51`.
Corpus SHA256: `a8d3843d92c6ec1ddb0a046fa7662e077db5cc21d2b7cf670e132a7853de3496`.
See the [input and indexing contract](../../trace-index-contract.md).

| Port | Wall median ms | User CPU ms | System CPU ms | MiB/s | Peak RSS median MiB | Workload source lines |
|---|---:|---:|---:|---:|---:|---:|
| go | 310.175 | 310.795 | 51.092 | 61.07 | 53.73 | 169 |
| rs | 152.106 | 131.418 | 17.949 | 124.53 | 22.75 | 103 |
| js | 534.704 | 438.282 | 178.787 | 35.43 | 316.41 | 108 |
| zig | 112.933 | 81.362 | 32.011 | 167.73 | 42.75 | 102 |

Five measured new processes per port after one warmup, rotating order; full input
buffering allowed and real postings retained. CPU time can exceed wall time for
multi-threaded runtimes. This measures local normalized JSONL parsing/indexing,
**not live MCP transport, server query throughput, or source-code semantic indexing**.

Per-child `wait4` runs inside a fresh small Python measurement process, excluding
that launcher's startup from CLI timing. Each sample records its inherited RSS
floor (~12–12.5MiB here). Near-floor figures are not pure executable memory.
The implementation was cross-checked using a300MiB parent and an allocating child:
child64MiB workload maxRSS77,594,624bytes matched `/usr/bin/time`. A preliminary
run that inherited the large corpus/oracle parent's RSS was rejected, not reported
as executable memory. Raw per-sample CPU/RSS, baselines, commands, hashes and versions
remain local in ignored `results/index-20260919T031207.580870Z.json`; startup/build
raw evidence is `results/20260919T031221.575210Z.json`. No raw artifacts are uploaded.
