# CLI measurements

Run from the checkout with Python 3 and the selected toolchains on PATH:

```sh
python3 scripts/benchmark.py
python3 scripts/benchmark.py --languages go rs js --samples 20 --warmups 3
python3 scripts/benchmark.py --builds --build-samples 3
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

Physical source line counts are descriptive footprint only. Time-to-prototype is
**unmeasured**. Heavy MCP trace parsing and index throughput are **not implemented
or benchmarked**. Help startup does not establish which language is best for those
workloads, overall productivity, or a general speedup. Report the environment and
sample counts with any comparisons; these small local runs are not broad claims.

## Local snapshot — 2026-09-19

Source `0d494d9e460f1bda64ccb0685c236a166dc8621a`, measured sources clean and
unchanged throughout. Linux x86_64, Go 1.27.1, Rust/Cargo 1.69.0, Bun 1.3.11,
Zig 0.16.0; Python 3.12.3. Command:

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
