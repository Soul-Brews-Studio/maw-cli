#!/usr/bin/env python3
"""Local forward development windows and committed source footprint; not productivity rankings."""
import argparse
import datetime
import json
from pathlib import Path
import re
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "benchmarks/cli/results/development"


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def snapshot():
    return {"commit": git("rev-parse", "HEAD"), "dirty": bool(git("status", "--porcelain")),
            "utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "monotonic_ns": time.monotonic_ns()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    for action in ("start", "finish"):
        child = sub.add_parser(action)
        child.add_argument("label", help="non-sensitive issue/language identifier")
    sub.choices["finish"].add_argument("--verified-compile-smoke", action="store_true", required=True,
                                      help="attest both real compiler and CLI smoke succeeded")
    sub.add_parser("footprint").add_argument("--commit", default="HEAD")
    args = parser.parse_args()
    if args.action == "footprint":
        commit = git("rev-parse", "--verify", args.commit + "^{commit}")
        rows = {}
        for language, suffix in (("go", ".go"), ("rs", ".rs"), ("js", ".ts"), ("zig", ".zig")):
            names = git("ls-tree", "-r", "--name-only", commit, "--", language).splitlines()
            source = [name for name in names if name.endswith(suffix)]
            build = [name for name in names if Path(name).name in
                     {"Cargo.toml", "Cargo.lock", "go.mod", "go.sum", "package.json", "bun.lock", "build.zig", "build.zig.zon"}]
            def count(files):
                return sum(len(subprocess.check_output(["git", "show", f"{commit}:{name}"], cwd=ROOT).splitlines()) for name in files)
            implementation = [name for name in source if name not in build]
            rows[language] = {"implementation_files": implementation,
                              "implementation_physical_lines": count(implementation),
                              "build_manifest_lock_files": build,
                              "build_manifest_lock_physical_lines": count(build)}
        print(json.dumps({"commit": commit, "footprint": rows}, indent=2))
        return
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", args.label):
        parser.error("label must be 1-64 letters/digits/underscore/hyphen")
    RESULTS.mkdir(parents=True, exist_ok=True)
    path = RESULTS / (args.label + ".json")
    if args.action == "start":
        with path.open("x") as handle:
            json.dump({"label": args.label, "start": snapshot()}, handle, indent=2)
    else:
        data = json.loads(path.read_text())
        if "finish" in data:
            parser.error("window already finished; use a new label")
        finish = snapshot()
        elapsed = (finish["monotonic_ns"] - data["start"]["monotonic_ns"]) / 1e9
        if elapsed < 0:
            parser.error("monotonic clock reset; historical interval cannot be measured")
        data.update(finish=finish, elapsed_wall_seconds=elapsed,
                    verification="operator attestation: compile and actual CLI smoke passed",
                    limitation="includes interruptions/parallel work; not active coding effort; same running host required")
        path.write_text(json.dumps(data, indent=2) + "\n")
        print(f"{args.label}: {elapsed:.3f} elapsed wall seconds (not coding effort)")
    print(path.relative_to(ROOT))


if __name__ == "__main__":
    main()
