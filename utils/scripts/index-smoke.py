#!/usr/bin/env python3
"""Independent JSONL postings oracle and actual-process contract smoke checks.

Normalized fixtures have unique object member names. Duplicate keys are outside
the contract; parser-specific rejection/last-key handling is not compared.
"""
import argparse
import json
import re
import subprocess
import tempfile
from pathlib import Path

MAX_BYTES = 64 * 1024 * 1024


def validate_strings(value):
    if isinstance(value, str):
        value.encode("utf-8", errors="strict")
    elif isinstance(value, dict):
        for key, item in value.items():
            validate_strings(key)
            validate_strings(item)
    elif isinstance(value, list):
        for item in value:
            validate_strings(item)


def oracle(data):
    if len(data) > MAX_BYTES:
        raise ValueError("input exceeds 64 MiB")
    terms, symbols = {}, set()
    records = text_bytes = 0
    for line in data.decode("utf-8", errors="strict").split("\n"):
        if not line.strip(" \t\r"):
            continue
        record = json.loads(line, parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))
        validate_strings(record)
        if not isinstance(record, dict) or record.get("jsonrpc") != "2.0":
            raise ValueError("invalid JSON-RPC result")
        result = record.get("result")
        context = result.get("structuredContent") if isinstance(result, dict) else None
        if not isinstance(context, dict):
            raise ValueError("invalid context")
        file, symbol, text = (context.get(key) for key in ("file", "symbol", "text"))
        if not all(isinstance(value, str) for value in (file, symbol, text)):
            raise ValueError("context fields must be strings")
        if not file or not symbol or "\0" in file or "\0" in symbol:
            raise ValueError("invalid metadata")
        symbols.add((file, symbol))
        text_bytes += len(text.encode("utf-8"))
        for term in {token.lower() for token in re.findall(r"[A-Za-z0-9_]+", text, flags=re.ASCII)}:
            terms.setdefault(term, []).append(records)
        records += 1
    checksum = 14695981039346656037
    for term in sorted(terms):
        for byte in f"{term}:{len(terms[term])}\n".encode():
            checksum = ((checksum ^ byte) * 1099511628211) & ((1 << 64) - 1)
    return dict(records=records, input_bytes=len(data), text_bytes=text_bytes,
                unique_symbols=len(symbols), unique_terms=len(terms),
                postings=sum(map(len, terms.values())), checksum=f"{checksum:016x}")


def record(text="Alpha alpha beta_2 42", file="src/a.go", symbol="Example"):
    return {"jsonrpc": "2.0", "result": {"structuredContent": {
        "file": file, "symbol": symbol, "text": text}}}


def encode(value):
    return json.dumps(value, ensure_ascii=True, separators=(",", ":")).encode()


def check_output(output, expected):
    actual = json.loads(output)
    if actual != expected or any(type(actual[key]) is not int for key in expected if key != "checksum"):
        raise AssertionError(f"summary mismatch: expected {expected}, got {actual}")


def smoke(command, env=None):
    valid = [b"", b" \t\r\n", encode(record()),
             b"\n" + encode(record("Alpha alpha café ไทย 😀 İ K K")) + b"\r\n"
             + encode(record("beta_2 Z alpha", symbol="Other")),
             encode(record(text="", file="a:b", symbol="c")) + b"\n"
             + encode(record(text="\0 123 _", file="a", symbol="b:c")),
             encode(dict(record(), extra=[True, None, 1.25, {"nested": "valid 😀"}])),
             b" " * MAX_BYTES]
    nested = None
    for _ in range(31):
        nested = [nested]
    valid.append(encode(dict(record(), extra=nested)))
    invalid = [b"{", b"[]", b"null", b"{}", b"\xff", b"\xc0\xaf", b"\xef\xbb\xbf{}",
               b"\v", b"\xc2\xa0", encode(record()) + b"\n{", b" " * (MAX_BYTES + 1),
               encode(record(file="")), encode(record(symbol="\0")), encode(record(text=1)),
               encode(record(text="\ud800")), encode(record(file="\udfff")),
               encode(dict(record(), extra="\ud800")), b'{"jsonrpc":NaN}']
    with tempfile.TemporaryDirectory(prefix="maw-index-smoke-") as temporary:
        path = Path(temporary) / "fixture.jsonl"
        for data in valid:
            expected = oracle(data)
            path.write_bytes(data)
            for argument, stdin in [(str(path), None), ("-", data)]:
                process = subprocess.run([*command, "index", argument], input=stdin, capture_output=True, env=env, timeout=60)
                if process.returncode != 0:
                    raise AssertionError(f"valid input ({len(data)} bytes, {argument}) rejected: {process.stderr.decode(errors='replace')}")
                check_output(process.stdout, expected)
        for number, data in enumerate(invalid):
            try:
                oracle(data)
            except (ValueError, UnicodeError):
                pass
            else:
                raise AssertionError(f"invalid fixture accepted by oracle: {number}")
            process = subprocess.run([*command, "index", "-"], input=data, capture_output=True, env=env, timeout=60)
            if process.returncode == 0 or process.stdout:
                raise AssertionError(f"invalid fixture {number} accepted or produced stdout: {process.stdout!r}")
        for arguments in [["index"], ["index", "one", "two"]]:
            process = subprocess.run([*command, *arguments], capture_output=True, env=env, timeout=10)
            if process.returncode != 2:
                raise AssertionError("usage must return 2")
        process = subprocess.run([*command, "index", str(path.parent / "missing")], capture_output=True, env=env, timeout=10)
        if process.returncode == 0 or process.stdout:
            raise AssertionError("missing file must fail without summary")
    return f"index smoke: {len(valid) * 2} valid file/stdin cases, {len(invalid)} invalid cases, usage/missing-file OK"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    if not command:
        parser.error("provide the CLI command after --")
    print(smoke(command))
