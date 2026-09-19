set working-directory := '../..'

# Build optimized/native or bundled/Bun entries, smoke, then sample help startup.
run:
    /usr/bin/time -p python3 utils/scripts/benchmark.py

# Also measure isolated-cache and warm builds (slower, no global cache clearing).
builds:
    /usr/bin/time -p python3 utils/scripts/benchmark.py --builds

# Build, verify equivalent context postings, then measure CPU/wall/RSS.
index:
    /usr/bin/time -p python3 utils/scripts/benchmark-index.py

# Actual-process JSONL contract checks after building every port.
index-smoke:
    just go build
    just rs build
    just js build
    just zig build
    python3 utils/scripts/index-smoke.py -- "$(pwd)/bin/maw-go"
    python3 utils/scripts/index-smoke.py -- "$(pwd)/src/rs/target/release/maw-rs"
    python3 utils/scripts/index-smoke.py -- "$(command -v bun)" "$(pwd)/src/js/dist/cli.js"
    python3 utils/scripts/index-smoke.py -- "$(pwd)/src/zig/zig-out/bin/maw-zig"
