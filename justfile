mod dev 'just/dev.just'
mod go 'just/go.just'
mod rs 'just/rs.just'
mod js 'just/js.just'
mod zig 'just/zig.just'
mod bench 'just/bench.just'
mod mcp 'just/mcp.just'
mod release 'just/release.just'
mod memory 'just/memory.just'

# List the development commands.
default:
    @just --list --list-submodules
