#!/usr/bin/env python3
"""Build, smoke, then measure equivalent help-command process startup."""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import statistics
import subprocess
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]


def positive(value):
    number = int(value)
    if not 1 <= number <= 10000:
        raise argparse.ArgumentTypeError("must be between 1 and 10000")
    return number


def tool(name):
    path = shutil.which(name)
    if not path:
        raise RuntimeError(f"missing executable: {name}")
    return str(Path(path).absolute())


def capture(command, cwd=ROOT, env=None):
    return subprocess.check_output(command, cwd=cwd, env=env, text=True,
                                   stderr=subprocess.STDOUT).strip()


def measure(command, cwd, env):
    start = time.perf_counter_ns()
    subprocess.run(command, cwd=cwd, env=env, stdout=subprocess.DEVNULL,
                   stderr=subprocess.PIPE, check=True)
    return (time.perf_counter_ns() - start) / 1_000_000


def stats(values):
    return {"raw_ms": values, "median_ms": statistics.median(values)}


def commands(language, scratch=None):
    env = os.environ.copy()
    cwd = ROOT
    if language == "go":
        output = (scratch / "maw-go") if scratch else ROOT / "bin/maw-go"
        build = [tool("go"), "-C", str(ROOT / "go"), "build", "-o", str(output), "./cmd/maw"]
        run = [str(output)]
        if scratch:
            env["GOCACHE"] = str(scratch / "cache")
    elif language == "rs":
        target = scratch / "target" if scratch else ROOT / "rs/target"
        build = [tool("cargo"), "build", "--release", "--manifest-path", str(ROOT / "rs/Cargo.toml")]
        env["CARGO_TARGET_DIR"] = str(target)
        run = [str(target / "release/maw-rs")]
    elif language == "js":
        output = scratch / "dist" if scratch else ROOT / "js/dist"
        build = [tool("bun"), "build", str(ROOT / "js/src/cli.ts"), "--target=bun", "--outdir", str(output)]
        run = [tool("bun"), str(output / "cli.js")]
    else:
        cwd = ROOT / "zig"
        build = [tool("zig"), "build", "-Doptimize=ReleaseFast"]
        prefix = scratch / "out" if scratch else cwd / "zig-out"
        if scratch:
            build += ["--cache-dir", str(scratch / "cache"), "--global-cache-dir",
                      str(scratch / "global-cache"), "--prefix", str(prefix)]
        run = [str(prefix / "bin/maw-zig")]
    return build, run, cwd, env


def footprint(language):
    base = ROOT / language
    excluded = {"target", "dist", "zig-out", ".zig-cache", "node_modules"}
    files = sorted(p for p in base.rglob("*") if p.is_file()
                   and not excluded.intersection(p.relative_to(base).parts)
                   and p.suffix in {".go", ".rs", ".ts", ".zig"})
    return {"files": [str(p.relative_to(ROOT)) for p in files],
            "physical_lines": sum(len(p.read_text().splitlines()) for p in files)}


def source_hashes(languages):
    files = ["scripts/benchmark.py", "scripts/smoke.sh", "go.work"]
    for language in languages:
        files.extend(footprint(language)["files"])
        files.extend(str(p.relative_to(ROOT)) for p in (ROOT / language).iterdir()
                     if p.is_file() and p.name in {"go.mod", "Cargo.toml", "Cargo.lock", "package.json"})
    return {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
            for name in sorted(set(files))}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--languages", nargs="+", choices=["go", "rs", "js", "zig"], default=["go", "rs", "js", "zig"])
    parser.add_argument("--samples", type=positive, default=20)
    parser.add_argument("--warmups", type=positive, default=3)
    parser.add_argument("--builds", action="store_true", help="also measure cache-isolated and repeated builds")
    parser.add_argument("--build-samples", type=positive, default=3, help="repeated build samples (minimum 2)")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.builds and args.build_samples < 2:
        parser.error("--build-samples must be at least 2")
    languages = list(dict.fromkeys(args.languages))
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    output = (args.output or ROOT / "benchmarks/cli/results" / f"{stamp}.json").absolute()
    result = {"timestamp_utc": stamp, "source_root": str(ROOT),
              "commit": capture([tool("git"), "rev-parse", "HEAD"]),
              "dirty": bool(capture([tool("git"), "status", "--porcelain", "--", *languages,
                                     "go.work", "scripts/benchmark.py", "scripts/smoke.sh"])),
              "source_sha256": source_hashes(languages),
              "platform": platform.platform(), "architecture": platform.machine(),
              "python": platform.python_version(), "samples": args.samples,
              "warmups": args.warmups, "languages": {},
              "method": "rotating round-robin, new process --help, stdout discarded; not OS-cold startup",
              "limitations": ["time-to-prototype unmeasured", "heavy MCP trace parsing/index throughput not implemented or measured",
                              "source lines describe footprint, not productivity", "build caches isolated only with --builds; OS/toolchain caches remain warm"]}
    versions = {"go": [[tool("go"), "version"]] if "go" in languages else [],
                "rs": [[tool("rustc"), "--version"], [tool("cargo"), "--version"]] if "rs" in languages else [],
                "js": [[tool("bun"), "--version"]] if "js" in languages else [],
                "zig": [[tool("zig"), "version"]] if "zig" in languages else []}
    with tempfile.TemporaryDirectory(prefix="maw-benchmark-") as temporary:
        temp = Path(temporary)
        empty_path = temp / "empty-path"
        empty_path.mkdir()
        runtime_env = dict(os.environ, PATH=str(empty_path))
        result["runtime_path"] = str(empty_path)
        for language in languages:
            build, run, cwd, env = commands(language)
            elapsed = measure(build, cwd, env)
            smoke = [tool("sh"), str(ROOT / "scripts/smoke.sh"), *run]
            evidence = capture(smoke)
            result["languages"][language] = {
                "versions": [{"command": cmd, "output": capture(cmd)} for cmd in versions[language]],
                "build_command": build, "build_cwd": str(cwd),
                "build_env_overrides": {k: v for k, v in env.items() if os.environ.get(k) != v},
                "initial_build_ms": elapsed, "smoke_command": smoke, "smoke": evidence,
                "runtime_command": [*run, "--help"], "runtime_cwd": str(ROOT),
                "source_footprint": footprint(language), "warmup_raw_ms": [], "startup": {"raw_ms": []}}
        for index in range(args.warmups + args.samples):
            order = languages[index % len(languages):] + languages[:index % len(languages)]
            for language in order:
                entry = result["languages"][language]
                elapsed = measure(entry["runtime_command"], ROOT, runtime_env)
                values = entry["warmup_raw_ms"] if index < args.warmups else entry["startup"]["raw_ms"]
                values.append(elapsed)
        for language, entry in result["languages"].items():
            entry["startup"] = stats(entry["startup"]["raw_ms"])
            if args.builds:
                scratch = temp / language
                scratch.mkdir()
                build, run, cwd, env = commands(language, scratch)
                first = measure(build, cwd, env)
                capture([tool("sh"), str(ROOT / "scripts/smoke.sh"), *run])
                warm = [measure(build, cwd, env) for _ in range(args.build_samples)]
                entry["builds"] = {"command": build, "cwd": str(cwd),
                    "env_overrides": {k: v for k, v in env.items() if os.environ.get(k) != v},
                    "first_label": "fresh output (compiler cache not isolated)" if language == "js" else "isolated compiler cache (not OS cold)",
                    "first_ms": first, "repeated": stats(warm)}
    if result["source_sha256"] != source_hashes(languages):
        raise SystemExit("benchmark source changed during measurement; results discarded")
    result["end_commit"] = capture([tool("git"), "rev-parse", "HEAD"])
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x") as handle:
        json.dump(result, handle, indent=2)
        handle.write("\n")
    for language, entry in result["languages"].items():
        print(f"{language}: --help median {entry['startup']['median_ms']:.3f} ms")
        if "builds" in entry:
            build = entry["builds"]
            print(f"  build first {build['first_ms']:.3f} ms; repeated median {build['repeated']['median_ms']:.3f} ms")
    print(output)


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as error:
        raise SystemExit(f"command failed ({error.returncode}): {error.cmd}\n{error.output or error.stderr or ''}")
