#!/usr/bin/env python3
"""Smoke the Git package entrypoint from an isolated directory/cache, without npm."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]

with tempfile.TemporaryDirectory(prefix="maw-package-") as temporary:
    work = Path(temporary)
    package = work / "package"
    package.mkdir()
    shutil.copy2(ROOT / "package.json", package / "package.json")
    shutil.copytree(ROOT / "src/js/src", package / "src/js/src")
    env = dict(os.environ, BUN_INSTALL_CACHE_DIR=str(work / "cache"), TMPDIR=str(work / "tmp"),
               MAW_HOME=str(work / "home"), MAW_PLUGINS_DIR=str(work / "home/plugins"))
    (work / "tmp").mkdir()
    command = ["bun", "x", "--bun", "--package", str(package), "maw-js"]
    for args, expected in ((["--help"], "Usage: maw"), (["version"], "maw dev"),
                           (["plugin", "ls"], "no plugins installed"), (["plugins", "ls"], "no plugins installed"),
                           (["plugins"], "no plugins installed")):
        result = subprocess.run(command + args, cwd=work, env=env, text=True, capture_output=True, check=True)
        if expected not in result.stdout:
            raise SystemExit(f"unexpected package output: {result.stdout!r}")
    result = subprocess.run(command + ["index", "-"], cwd=work, env=env,
                            text=True, input="", capture_output=True)
    if result.returncode != 2 or 'unknown command "index"' not in result.stderr:
        raise SystemExit(f"removed index command still available: {result}")
    metadata = json.loads((package / "package.json").read_text())
    if metadata.get("dependencies") or metadata.get("scripts"):
        raise SystemExit("Git package must not need dependencies or install/build hooks")
    print("PASS: isolated bunx package help/version/plugin ls aliases, no clone/build hooks required")
