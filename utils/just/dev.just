set working-directory := '../..'

# Build the core Go implementation.
build:
    just go build

# Smoke an already compiled binary; no unit tests.
smoke:
    just go smoke

# Time one compile-and-smoke iteration.
check:
    just go check

# Compile and smoke all four independent implementations.
all:
    just go check
    just rs check
    just js check
    just zig check
