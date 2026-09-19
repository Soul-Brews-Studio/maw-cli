#!/bin/sh
set -eu
cd "$(dirname "$0")/.."

# One compiler invocation; all assertions below call the resulting executable.
# POSIX time reports wall (real), user, and system seconds on Linux and macOS.
/usr/bin/time -p sh -c 'go build -o bin/maw ./cmd/maw && sh scripts/smoke.sh'
