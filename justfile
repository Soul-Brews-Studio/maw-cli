mod dev 'just/dev.just'
mod go 'just/go.just'
mod rs 'just/rs.just'
mod js 'just/js.just'
mod zig 'just/zig.just'
mod bench 'just/bench.just'

# List the development commands.
default:
    @just --list --list-submodules
