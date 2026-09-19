#!/usr/bin/env python3
"""Measure actual MCP-shaped JSONL index processes, not live MCP servers."""
import argparse
import datetime
import hashlib
import importlib.util
import json
import os
import platform
import statistics
import subprocess
import tempfile
import time
from pathlib import Path

import benchmark as common

ROOT = common.ROOT
spec = importlib.util.spec_from_file_location("index_smoke", ROOT / "scripts/index-smoke.py")
contract = importlib.util.module_from_spec(spec)
spec.loader.exec_module(contract)


def measure(command, env, expected):
    # wait4 gives this exact child's CPU/RSS, unlike cumulative RUSAGE_CHILDREN.
    with tempfile.TemporaryFile() as stdout, tempfile.TemporaryFile() as stderr:
        started = time.perf_counter_ns()
        process = subprocess.Popen(command, cwd=ROOT, env=env, stdout=stdout, stderr=stderr)
        _, status, usage = os.wait4(process.pid, 0)
        wall_ms = (time.perf_counter_ns() - started) / 1_000_000
        process.returncode = os.waitstatus_to_exitcode(status)
        stdout.seek(0)
        stderr.seek(0)
        if process.returncode:
            raise RuntimeError(f"index failed ({process.returncode}): {stderr.read().decode(errors='replace')}")
        contract.check_output(stdout.read(), expected)
    rss_bytes = usage.ru_maxrss if platform.system() == "Darwin" else usage.ru_maxrss * 1024
    return dict(wall_ms=wall_ms, user_ms=usage.ru_utime * 1000,
                system_ms=usage.ru_stime * 1000, peak_rss_bytes=rss_bytes)


def corpus(count):
    lines = []
    for index in range(count):
        text = (f"func Symbol{index % 2000} context_{index % 257} call request result "
                "Alpha alpha snake_case 123 café ไทย 😀\n") * 16
        value = contract.record(text, f"src/module_{index % 200}.go", f"Symbol{index % 2000}")
        value["id"] = index
        lines.append(json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode())
    data = b"\n".join(lines) + b"\n"
    if len(data) > contract.MAX_BYTES:
        raise ValueError("generated corpus exceeds 64 MiB; reduce --records")
    return data


def hashes(languages):
    result = common.source_hashes(languages)
    for name in ["scripts/benchmark-index.py", "scripts/index-smoke.py", "docs/trace-index-contract.md", "just/bench.just"]:
        result[name] = hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--languages", nargs="+", choices=["go", "rs", "js", "zig"], default=["go", "rs", "js", "zig"])
    parser.add_argument("--samples", type=common.positive, default=5)
    parser.add_argument("--warmups", type=common.positive, default=1)
    parser.add_argument("--records", type=int, default=12000)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if not hasattr(os, "wait4") or platform.system() not in {"Linux", "Darwin"}:
        parser.error("per-child CPU/RSS requires Linux or macOS wait4")
    if not 1 <= args.records <= 30000:
        parser.error("--records must be 1..30000 (also bounded by 64 MiB)")
    languages = list(dict.fromkeys(args.languages))
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    output = (args.output or ROOT / "benchmarks/cli/results" / f"index-{stamp}.json").absolute()
    data = corpus(args.records)
    expected = contract.oracle(data)
    result = dict(timestamp_utc=stamp, commit=common.capture([common.tool("git"), "rev-parse", "HEAD"]),
                  dirty=bool(common.capture([common.tool("git"), "status", "--porcelain", "--", *languages, "scripts", "docs/trace-index-contract.md", "just/bench.just"])),
                  source_sha256=hashes(languages), platform=platform.platform(), architecture=platform.machine(),
                  python=platform.python_version(), samples=args.samples, warmups=args.warmups,
                  corpus=dict(label="generated normalized MCP context results; not private transcripts", records=args.records,
                              bytes=len(data), sha256=hashlib.sha256(data).hexdigest(), expected=expected),
                  method="rotating round-robin, fresh index process per sample, warm filesystem cache; wait4 per child CPU/RSS; every summary checked",
                  limitations=["full input buffering allowed; actual postings retained", "not live MCP server throughput or transport latency", "not OS-cold measurements", "source lines are footprint, not time-to-prototype or productivity"], languages={})
    version_commands = {"go": [[common.tool("go"), "version"]] if "go" in languages else [],
                        "rs": [[common.tool("rustc"), "--version"], [common.tool("cargo"), "--version"]] if "rs" in languages else [],
                        "js": [[common.tool("bun"), "--version"]] if "js" in languages else [],
                        "zig": [[common.tool("zig"), "version"]] if "zig" in languages else []}
    with tempfile.TemporaryDirectory(prefix="maw-index-benchmark-") as temporary:
        temp = Path(temporary)
        fixture = temp / "context.jsonl"
        fixture.write_bytes(data)
        empty_path = temp / "empty-path"
        empty_path.mkdir()
        env = dict(os.environ, PATH=str(empty_path))
        result["runtime_path"] = str(empty_path)
        for language in languages:
            build, run, cwd, build_env = common.commands(language)
            elapsed = common.measure(build, cwd, build_env)
            evidence = contract.smoke(run, env)
            footprint = common.footprint(language)
            index_files = [file for file in footprint["files"] if "index" in Path(file).parts or "index" in Path(file).stem]
            index_lines = sum(len((ROOT / file).read_text().splitlines()) for file in index_files)
            result["languages"][language] = dict(versions=[dict(command=command, output=common.capture(command)) for command in version_commands[language]],
                build_command=build, build_cwd=str(cwd), initial_build_ms=elapsed, smoke=evidence,
                runtime_command=[*run, "index", str(fixture)], runtime_cwd=str(ROOT), source_footprint=footprint,
                workload_files=index_files, workload_physical_lines=index_lines,
                remaining_cli_and_build_physical_lines=footprint["physical_lines"] - index_lines,
                warmup_raw=[], raw=[])
        for iteration in range(args.warmups + args.samples):
            order = languages[iteration % len(languages):] + languages[:iteration % len(languages)]
            for language in order:
                entry = result["languages"][language]
                sample = measure(entry["runtime_command"], env, expected)
                entry["warmup_raw" if iteration < args.warmups else "raw"].append(sample)
        for entry in result["languages"].values():
            entry["median"] = {key: statistics.median(sample[key] for sample in entry["raw"]) for key in entry["raw"][0]}
            entry["mib_per_second"] = len(data) / (1024 * 1024) / (entry["median"]["wall_ms"] / 1000)
    if result["source_sha256"] != hashes(languages):
        raise SystemExit("source changed during benchmark; results discarded")
    result["end_commit"] = common.capture([common.tool("git"), "rev-parse", "HEAD"])
    if result["end_commit"] != result["commit"]:
        raise SystemExit("commit changed during benchmark; results discarded")
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x") as handle:
        json.dump(result, handle, indent=2)
        handle.write("\n")
    for language, entry in result["languages"].items():
        print(f"{language}: index median {entry['median']['wall_ms']:.3f} ms, {entry['mib_per_second']:.2f} MiB/s, peak RSS median {entry['median']['peak_rss_bytes']} bytes")
    print(output)


if __name__ == "__main__":
    main()
