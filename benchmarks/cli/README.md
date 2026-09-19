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
  architecture, reviewed Git SHA, and dirty flag. Keep normal Go cache for the
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
