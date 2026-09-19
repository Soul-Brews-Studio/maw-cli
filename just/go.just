set working-directory := '..'

# Build core maw (maw-go is the comparison filename).
build:
    /usr/bin/time -p go -C go build -o ../bin/maw-go ./cmd/maw

smoke:
    /usr/bin/time -p sh scripts/smoke.sh "$(pwd)/bin/maw-go"

check: build smoke
