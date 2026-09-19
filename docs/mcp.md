# Native Go MCP context client

The Go CLI's `context` command starts trusted local Serena and CodeGraph stdio
servers, resolves code context, and automatically writes a metadata trace through
Serena's `write_memory` tool after each successful resolution. Rust/Bun/Zig do not
implement this command yet. This is not the offline `index` workload.

```sh
just go build
bin/maw-go context --help
bin/maw-go context --config ~/.config/maw/mcp.json --project . \
  --file go/internal/cli/cli.go --symbol Run 'command dispatch'
```

Flags precede positional query text. Query-only calls use CodeGraph exploration;
`--file` adds Serena symbol overview, and `--symbol` selects precise symbol lookup
instead. `--file` must resolve inside the selected project. The project directory
is resolved absolutely and becomes both servers' working directory. Help does not
read configuration or start servers.

## Trusted local configuration

Default path: `~/.config/maw/mcp.json`; override with `MAW_MCP_CONFIG` or `--config`.
The JSON object has exactly two named servers:

```json
{
  "serena": {
    "command": "/absolute/path/to/your/serena-launcher",
    "args": ["start-mcp-server", "--project-from-cwd"],
    "env": {}
  },
  "codegraph": {
    "command": "/absolute/path/to/your/codegraph-launcher",
    "args": ["mcp"],
    "env": {"DO_NOT_TRACK": "1", "CODEGRAPH_TELEMETRY": "0"}
  }
}
```

These are illustrative launcher paths, not an installation script. Copy the
actual command/argument/environment fields from your existing trusted server
configuration, including any launcher-specific arguments. Do not copy transport
fields or secrets into the repository. `cwd` is accepted but the command overrides
it with validated `--project`. The current environment is inherited with explicit
overrides; CodeGraph telemetry disabling is enforced by the command. Processes
are spawned directly without a shell. Only configure commands you trust.

Serena must expose `initial_instructions`, `activate_project`, `write_memory`, and
the requested symbol tool. CodeGraph must expose `codegraph_explore`. The client
discovers tools and their input schemas; it does not install servers, silently
invent substitute tool names, or implement a general JSON Schema validator.
Serena activation occurs in its newly owned server session, not another client's
shared MCP connection. Maintain/sync the project indexes separately.

## Result and mandatory trace persistence

Success prints one JSON object with `project` and `resolutions`. Each resolution
contains `provider`, `tool`, the complete MCP tool `result`, and `trace_memory`.
Trace names are unique `learning/traces/YYYY-MM-DD/<random-id>` memories. Metadata
includes project, Git HEAD when available, file/symbol, tool/provider, timestamp,
query/result SHA256, result byte count, elapsed time and client version. Git HEAD
is provenance, not proof that a dirty working tree matches that commit.

Trace records intentionally omit raw query and result content; source content is
still present in the explicitly requested CLI output. File/symbol/project names
are recorded. There is no implicit network telemetry or transcript upload.

Persistence failure fails the command rather than claiming a logged resolution.
An earlier successful trace can remain if a later lookup/persistence fails; this
is an append-only audit, not an atomic transaction or rollback mechanism.

## Transport and failure boundaries

- Standard-library Go, compact newline-delimited JSON-RPC over stdin/stdout.
- Legacy MCP initialization requests `2025-11-25`; accepted negotiated versions
  are `2025-11-25`, `2025-06-18`, `2025-03-26`, and `2024-11-05`. No claim of
  compatibility with the different `2026-07-28` lifecycle.
- Serial request/response matching, paginated tool discovery with cursor guards,
  interleaved notifications, server ping replies and unsupported-request errors.
- Incoming messages are bounded to 32 MiB. Invalid framing/JSON or mismatched IDs
  fail closed. Tool errors include up to 512 bytes of escaped text diagnostics;
  raw successful results are not truncated.
- `--timeout` defaults to 60 seconds (maximum 10 minutes). Request cancellation
  sends the advisory notification except during initialization, then closes the
  session so late responses cannot be mixed into later requests.
- Cleanup closes stdin and allows two seconds for normal EOF/LSP cleanup, then
  kills only the owned server and waits up to 500 ms. This bounded cleanup can
  extend wall time past the request deadline for each server. Forced/nonzero exit
  remains an error. No invented MCP shutdown method, process-group kill, or
  descendant-process management is performed.
- Diagnostics are suppressed by default; `--server-logs` forwards server stderr.
  Server logs may contain local paths or content: enable deliberately.

## Compile-first smoke verification

```sh
just mcp check
```

This builds once and invokes the real binary against isolated temporary Python
stdio servers. It verifies handshake/pagination/ping, cwd/privacy environment,
automatic trace writes, persistence failures, invalid schemas/protocol, timeout
cancellation, inert help and delayed normal shutdown. It does not contact installed
servers, run unit tests, or retain fixture data. Live installed-server verification
is a separate environment-specific check, not a language throughput benchmark.
