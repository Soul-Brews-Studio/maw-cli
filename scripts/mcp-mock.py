#!/usr/bin/env python3
"""Local stdio fixture; never connect to a real MCP server or repository."""
import json
import os
from pathlib import Path
import sys
import time

role = sys.argv[1]
mode = os.environ.get("MAW_MOCK_MODE", "")
directory = Path(os.environ["MAW_MOCK_DIR"])


def log(event):
    with (directory / f"{role}.jsonl").open("a") as stream:
        stream.write(json.dumps(event) + "\n")


def send(value):
    print(json.dumps(value, separators=(",", ":")), flush=True)


log({"event": "start", "cwd": os.getcwd(), "privacy": [os.environ.get("DO_NOT_TRACK"), os.environ.get("CODEGRAPH_TELEMETRY")]})
names = (["initial_instructions", "activate_project", "write_memory", "find_symbol", "get_symbols_overview"]
         if role == "serena" else ["codegraph_explore"])
for line in sys.stdin:
    message = json.loads(line)
    method = message.get("method")
    identifier = message.get("id")
    log(message)
    if method == "initialize":
        result = {"protocolVersion": "2026-07-28" if mode == "bad-protocol" else "2025-11-25", "capabilities": {"tools": {}}}
    elif method == "tools/list":
        # Force pagination on Serena and interleave server notifications/requests.
        send({"jsonrpc": "2.0", "method": "notifications/message", "params": {"data": "fixture notice"}})
        send({"jsonrpc": "2.0", "id": 42, "method": "ping"})
        response = json.loads(sys.stdin.readline())
        assert response["id"] == 42 and response["result"] == {}
        page = names[2:] if message.get("params", {}).get("cursor") else names[:2]
        result = {"tools": [{"name": name, "inputSchema": {"type": "object"}} for name in page]}
        if len(names) > 2 and not message.get("params", {}).get("cursor"):
            result["nextCursor"] = "second"
        if mode == "bad-schema":
            result["tools"][0]["inputSchema"] = "invalid"
    elif method == "tools/call":
        name = message["params"]["name"]
        arguments = message["params"].get("arguments", {})
        if mode == "timeout" and name == "codegraph_explore":
            continue
        result = {"content": [{"type": "text", "text": "fixture result"}]}
        if name == "write_memory":
            if mode == "missing-content":
                result = {}
            elif mode == "persistence-error":
                result = {"isError": True, "content": [{"type": "text", "text": "fixture persistence denied\n\u001b[31m"}]}
            else:
                trace = json.loads(arguments["content"])
                (directory / (arguments["memory_name"].split("/")[-1] + ".json")).write_text(json.dumps(trace))
        if name == "codegraph_explore":
            result["structuredContent"] = {"file": "fixture.go", "symbol": "Fixture", "text": "func Fixture() {}"}
    elif identifier is None:
        continue
    else:
        send({"jsonrpc": "2.0", "id": identifier, "error": {"code": -32601, "message": "unsupported"}})
        continue
    send({"jsonrpc": "2.0", "id": identifier, "result": result})

# Model ordinary Python/LSP cleanup that legitimately takes more than 200ms.
if mode == "slow-close":
    time.sleep(0.35)
log({"event": "eof"})
