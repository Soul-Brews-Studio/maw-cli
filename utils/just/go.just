set working-directory := '../..'

# Build core maw (maw-go is the comparison filename).
build:
    /usr/bin/time -p go -C src/go build -o ../../bin/maw-go ./cmd/maw-go

smoke:
    /usr/bin/time -p sh utils/scripts/smoke.sh "$(pwd)/bin/maw-go"
    /usr/bin/time -p python3 utils/scripts/marketplace-smoke.py "$(pwd)/bin/maw-go"
    /usr/bin/time -p python3 utils/scripts/selector-smoke.py "$(pwd)/bin/maw-go"
    /usr/bin/time -p python3 utils/scripts/archive-smoke.py "$(pwd)/bin/maw-go"
    /usr/bin/time -p python3 utils/scripts/update-smoke.py

check: build smoke

# Go has no built-in `go release`; this task previews our gated source release.
release:
    /usr/bin/time -p python3 utils/scripts/release.py
