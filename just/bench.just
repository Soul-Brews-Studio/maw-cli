set working-directory := '..'

# Build optimized/native or bundled/Bun entries, smoke, then sample help startup.
run:
    /usr/bin/time -p python3 scripts/benchmark.py

# Also measure isolated-cache and warm builds (slower, no global cache clearing).
builds:
    /usr/bin/time -p python3 scripts/benchmark.py --builds

# Build, verify equivalent context postings, then measure CPU/wall/RSS.
index:
    /usr/bin/time -p python3 scripts/benchmark-index.py

# Actual-process JSONL contract checks after building every port.
index-smoke:
    just go build
    just rs build
    just js build
    just zig build
    python3 scripts/index-smoke.py -- "$(pwd)/bin/maw-go"
    python3 scripts/index-smoke.py -- "$(pwd)/rs/target/release/maw-rs"
    python3 scripts/index-smoke.py -- "$(command -v bun)" "$(pwd)/js/dist/cli.js"
    python3 scripts/index-smoke.py -- "$(pwd)/zig/zig-out/bin/maw-zig"
