set working-directory := '..'

# Smoke the existing Go binary using isolated local stdio fixtures.
smoke:
    /usr/bin/time -p python3 scripts/mcp-smoke.py "$(pwd)/bin/maw-go"

# Compile first, then smoke; no unit test suite or external servers.
check:
    just go build
    just mcp smoke
