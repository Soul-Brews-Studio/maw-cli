set working-directory := '..'

# Compile once, using Go's normal build cache.
build:
    go build -o bin/maw ./cmd/maw

# Smoke an already compiled binary; no unit tests.
smoke:
    sh scripts/smoke.sh

# Time one compile-and-smoke iteration.
check:
    sh scripts/check.sh
