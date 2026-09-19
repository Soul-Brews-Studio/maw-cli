mod dev 'utils/just/dev.just'
mod go 'utils/just/go.just'
mod rs 'utils/just/rs.just'
mod js 'utils/just/js.just'
mod zig 'utils/just/zig.just'
mod bench 'utils/just/bench.just'
mod mcp 'utils/just/mcp.just'
mod release 'utils/just/release.just'
mod memory 'utils/just/memory.just'

# List the development commands.
default:
    @just --list --list-submodules
