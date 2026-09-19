set working-directory := '..'

# Build optimized/native or bundled/Bun entries, smoke, then sample help startup.
run:
    /usr/bin/time -p python3 scripts/benchmark.py

# Also measure isolated-cache and warm builds (slower, no global cache clearing).
builds:
    /usr/bin/time -p python3 scripts/benchmark.py --builds
