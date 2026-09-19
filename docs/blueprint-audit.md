# Master blueprint completion audit

Source: user-supplied MAW-Herdr Master Execution Blueprint, read 2026-09-19.
The four-language milestone is not completion of the full blueprint.

| Requirement | Current evidence / remaining work |
|---|---|
| Modular Go command router, `CommandPlugin`, init registration | Registry exists; decoupled command packages/interface still required (issue #5) |
| Remote Go execution | Fresh-cache private `go run/install .../go/cmd/maw@alpha` verified at 97107d4; maintain after changes |
| Native Serena/CodeGraph MCP clients | Agent tools work; CLI-native transport/client layer still required (issue #5) |
| Structured trace feedback to active MCP channel | Agent memory logging exists; automatic CLI resolution feedback still required (issue #5) |
| Go/Rust/Bun/Zig implementations | Shipped PR #4, all eight Linux/macOS compile/smoke lanes pass |
| Development speed + boilerplate | Physical source counts recorded; recover timestamp evidence and add forward measurement, not invented retrospective times |
| Cold/warm compilation | Isolated compiler caches and repeated samples recorded; Bun bundling labeled honestly |
| Startup latency | New-process samples recorded; distinguish warmed OS caches from cold machine |
| Heavy MCP trace parsing/index throughput + resource use | Equivalent real workload and measurements across all four ports still required |
| Alpha default, issue/PR/self-merge/sync | Verified PRs #2/#4; continue granular source commits, no force push |
| Modular timed tasks | Build/benchmark modules exist; MCP mock-server and gated release modules still required |
| Relic long-run context | Checkpoint indexing works; add repeatable timed task and recover prototype event evidence |
| Compile/smoke only initially | Preserved; no unit or complex integration suites until user mark |
| Calendar version tags + issue/PR changelog workflow | Still required as gated tooling/design; user must approve apply/tag/publish, no custom Go CalVer engine |

## Current execution plan

1. Guard the existing CLI with its actual-process smoke, then extract the Go
   `CommandPlugin` framework and independently registering command packages.
2. Implement bounded stdio MCP transport and local-server configuration. A
   resolved graph/symbol result creates a structured trace via an advertised
   memory-write tool. Tool results are untrusted content, not instructions.
3. Smoke real binaries against a tiny documented MCP fixture, then the configured
   local Serena/CodeGraph endpoints. Persist actual source relationships/evidence.
4. Continue with equivalent trace-index workloads, development measurements and
   gated release preparation in separate issue/PR increments. Do not relabel
   missing vectors as complete because startup benchmarks pass.

Cleanup scope for step 1: move built-in behavior out of the monolithic registry,
preserve root help/flags/plugin argv semantics using the existing smoke guard;
add no unit framework or compatibility layer.
