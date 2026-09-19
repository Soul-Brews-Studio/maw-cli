set working-directory := '../../src/zig'

build:
    /usr/bin/time -p zig build -Doptimize=ReleaseFast

smoke:
    /usr/bin/time -p sh ../../utils/scripts/smoke.sh "$(pwd)/zig-out/bin/maw-zig"

check: build smoke
