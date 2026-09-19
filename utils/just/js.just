set working-directory := '../..'

# Bundle for Bun, not a standalone executable.
build:
    /usr/bin/time -p bun build src/js/src/cli.ts --target=bun --outdir src/js/dist

smoke:
    /usr/bin/time -p sh utils/scripts/smoke.sh "$(command -v bun)" "$(pwd)/src/js/dist/cli.js"

check: build smoke
