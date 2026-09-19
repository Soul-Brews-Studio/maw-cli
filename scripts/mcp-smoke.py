#!/usr/bin/env python3
"""Smoke the compiled Go CLI against owned, temporary stdio subprocesses."""
import json
import signal
from pathlib import Path
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
BINARY = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else ROOT / "bin/maw-go"
MOCK = ROOT / "scripts/mcp-mock.py"


def check(condition, message):
    if not condition:
        raise SystemExit("MCP smoke: " + message)


with tempfile.TemporaryDirectory(prefix="maw-mcp-smoke-") as temporary:
    project = Path(temporary)
    (project / "fixture.go").write_text("package fixture\nfunc Fixture() {}\n")
    config = project / "mcp.json"

    def run(mode="", extra=(), timeout="5s"):
        logdir = project / (mode or "success")
        logdir.mkdir(exist_ok=True)
        config.write_text(json.dumps({role: {"command": sys.executable, "args": [str(MOCK), role],
            "env": {"MAW_MOCK_DIR": str(logdir), "MAW_MOCK_MODE": mode}}
            for role in ("serena", "codegraph")}))
        process = subprocess.run([str(BINARY), "context", "--config", str(config), "--project", str(project),
            "--timeout", timeout, *extra, "fixture"], capture_output=True, text=True, timeout=12)
        return process, logdir

    # Missing configuration must not be opened and no server should start for help.
    help_result = subprocess.run([str(BINARY), "context", "--help"], env={"MAW_MCP_CONFIG": str(config)}, capture_output=True, text=True)
    check(help_result.returncode == 0 and not config.exists(), "help is not inert")
    success, logs = run(extra=("--file", "fixture.go", "--symbol", "Fixture"))
    check(success.returncode == 0, success.stderr)
    output = json.loads(success.stdout)
    check(len(output["resolutions"]) == 2, "expected graph and symbol resolutions")
    for resolution in output["resolutions"]:
        trace = json.loads((logs / (resolution["trace_memory"].split("/")[-1] + ".json")).read_text())
        check(trace["schema"] == "maw.context-trace.v1" and trace["tool"] == resolution["tool"], "trace schema/tool mismatch")
        check(trace["project"] == str(project) and len(trace["result_sha256"]) == 64, "trace provenance/hash missing")
        check("query" not in trace and "result" not in trace, "raw context leaked into trace")
    for role in ("serena", "codegraph"):
        events = [json.loads(line) for line in (logs / f"{role}.jsonl").read_text().splitlines()]
        check(events[0]["cwd"] == str(project), "server cwd mismatch")
        check(events[-1].get("event") == "eof", "server did not close normally")
        if role == "codegraph":
            check(events[0]["privacy"] == ["1", "0"], "telemetry not disabled")
    for mode, diagnostic in (("missing-content", "requires content array"), ("persistence-error", "persistence failed"), ("bad-protocol", "unsupported MCP protocol"), ("bad-schema", "invalid tool descriptor")):
        result, _ = run(mode)
        check(result.returncode != 0 and not result.stdout and diagnostic in result.stderr, f"{mode}: {result.stderr}")
        if mode == "persistence-error":
            check("fixture persistence denied" in result.stderr and "\x1b" not in result.stderr, "missing or unsafe tool error detail")
    started = time.monotonic()
    result, logs = run("timeout", timeout="300ms")
    check(result.returncode != 0 and not result.stdout and "deadline" in result.stderr, "timeout not propagated")
    check(time.monotonic() - started < 7, "timeout cleanup exceeded bounded allowance")
    events = [json.loads(line) for line in (logs / "codegraph.jsonl").read_text().splitlines()]
    check(any(event.get("method") == "notifications/cancelled" for event in events), "request cancellation not sent")
    result, _ = run("slow-close")
    check(result.returncode == 0, "ordinary delayed EOF cleanup failed: " + result.stderr)

# Go installs a signal context: stdin indexing must observe it even while blocked.
blocked = subprocess.Popen([str(BINARY), "index", "-"], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
time.sleep(0.1)
blocked.send_signal(signal.SIGINT)
try:
    blocked.wait(timeout=3)
finally:
    if blocked.poll() is None:
        blocked.kill()
        blocked.wait()
check(blocked.returncode != 0, "blocked stdin interrupt must fail")
blocked.stdin.close()
check(not blocked.stdout.read(), "interrupted index emitted summary")

print("MCP smoke: actual CLI handshake, paging, trace persistence, errors, timeout, inert help, and cleanup OK")
