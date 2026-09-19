set working-directory := '..'

# Bundle for Bun, not a standalone executable.
build:
    /usr/bin/time -p bun build js/src/cli.ts --target=bun --outdir js/dist

smoke:
    /usr/bin/time -p sh scripts/smoke.sh "$(command -v bun)" "$(pwd)/js/dist/cli.js"

check: build smoke
