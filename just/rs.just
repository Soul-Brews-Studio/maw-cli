set working-directory := '..'

build:
    /usr/bin/time -p cargo build --release --manifest-path rs/Cargo.toml

smoke:
    /usr/bin/time -p sh scripts/smoke.sh "$(pwd)/rs/target/release/maw-rs"

check: build smoke
