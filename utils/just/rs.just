set working-directory := '../..'

build:
    /usr/bin/time -p env CARGO_REGISTRIES_CRATES_IO_PROTOCOL=sparse cargo build --locked --release --manifest-path src/rs/Cargo.toml

smoke:
    /usr/bin/time -p sh utils/scripts/smoke.sh "$(pwd)/src/rs/target/release/maw-rs"

check: build smoke
