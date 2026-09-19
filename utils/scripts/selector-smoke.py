#!/usr/bin/env python3
"""Go @/# selectors through actual processes; local Git, no network."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

command = sys.argv[1:]
if command[:1] == ["--"]:
    command = command[1:]
command = [str(Path(p).resolve()) for p in command]
assert command, "usage: selector-smoke.py -- EXECUTABLE"
git = shutil.which("git")
assert git

with tempfile.TemporaryDirectory(prefix="maw-selectors-") as temporary:
    root = Path(temporary).resolve()
    source, home = root / "source", root / "home"
    source.mkdir()
    home.mkdir()
    env = {k: v for k, v in os.environ.items() if not k.startswith(("MAW_", "XDG_", "GIT_"))}
    env.update(HOME=str(home), USERPROFILE=str(home), MAW_CONFIG_DIR=str(home / "config"),
               GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL="/dev/null", GIT_TERMINAL_PROMPT="0")

    def g(*args):
        result = subprocess.run([git, "-c", "core.hooksPath=/dev/null", "-c", "user.name=Smoke",
                                 "-c", "user.email=smoke@example.invalid", *args],
                                cwd=source, env=env, text=True, capture_output=True, timeout=15)
        assert result.returncode == 0, result.stderr
        return result.stdout.strip()

    def run(*args, status=0, extra=None):
        result = subprocess.run(command + ["plugin", *args], cwd=home,
                                env=dict(env, **(extra or {})), text=True, capture_output=True, timeout=20)
        assert result.returncode == status, (args, result.returncode, result.stdout, result.stderr)
        return result

    g("init", "-q", "--initial-branch=main")
    (source / "plugin.json").write_text(json.dumps({"name": "demo", "version": "1.0", "entry": "index.js",
                                                  "runtime": "bun-dev", "target": "js", "cli": {"interactive": True}}))
    (source / "index.js").write_text("throw new Error('never execute');\n")
    g("add", ".")
    g("commit", "-qm", "first")
    first = g("rev-parse", "HEAD")
    g("tag", "v1")
    (source / "index.js").write_text("throw new Error('still never execute');\n")
    g("commit", "-qam", "second")
    second = g("rev-parse", "HEAD")
    for marker in ("@", "#"):
        env["MAW_PLUGINS_DIR"] = str(root / ("at" if marker == "@" else "hash"))
        assert first in run("install", str(source) + marker + "v1").stdout
        assert first in run("update", "demo").stdout  # selector installs stay pinned
        assert second in run("update", "demo" + marker + second).stdout
        assert second in run("info", "demo").stdout
        assert first in run("update", "demo", "--ref", "v1").stdout
        run("update", "demo" + marker + "v1", "--ref", "main", status=2)
        run("install", str(source) + marker + "v1", "--ref", "main", status=2)
        run("update", "demo" + marker, status=2)
        run("install", str(source) + marker, status=2)
    run("update", "demo@main#v1", status=2)
    run("info", "demo@v1", status=1)
    run("check", "demo#v1", status=1)
    # Existing source paths containing selector characters remain literal.
    for name in ("literal@repo", "literal#repo"):
        literal = root / name
        literal.symlink_to(source, target_is_directory=True)
        env["MAW_PLUGINS_DIR"] = str(root / (name + "-installed"))
        assert second in run("install", str(literal)).stdout
        for marker in ("@", "#"):
            env["MAW_PLUGINS_DIR"] = str(root / (name + "-pinned-" + marker))
            assert first in run("install", str(literal) + marker + "v1").stdout
            run("install", str(literal) + marker + "v1", "--ref", "main", status=2)
            run("install", str(literal) + marker, status=2)
            run("install", str(literal) + marker + "v1#main", status=2)

    # A shell-free Git shim redirects URL clones to the local fixture. No request
    # reaches a network; record the URL received from the real CLI parser.
    shim = root / "shim"
    shim.mkdir()
    record = root / "clone.json"
    script = shim / "git"
    script.write_text(f"#!{sys.executable}\nimport os, sys, json\n"
                      f"args = sys.argv[1:]\n"
                      f"if 'clone' in args:\n"
                      f"    open({str(record)!r}, 'w').write(json.dumps(args[-2]))\n"
                      f"    args[-2] = {str(source)!r}\n"
                      f"os.execv({git!r}, [{git!r}] + args)\n")
    script.chmod(0o755)
    cases = [("owner/repo@v1", "https://github.com/owner/repo", first),
             ("owner/repo#v1", "https://github.com/owner/repo", first),
             ("https://github.com/owner/repo@v1", "https://github.com/owner/repo", first),
             ("https://github.com/owner/repo#v1", "https://github.com/owner/repo", first),
             ("https://user@github.com/owner/repo", "https://user@github.com/owner/repo", second),
             ("https://user@github.com/owner/repo#v1", "https://user@github.com/owner/repo", first)]
    for index, (value, url, commit) in enumerate(cases):
        env["MAW_PLUGINS_DIR"] = str(root / f"url-{index}")
        assert commit in run("install", value, extra={"PATH": str(shim)}).stdout
        assert json.loads(record.read_text()) == url

print("selector smoke passed: @/#, branch/tag/commit, pin updates, duplicates, literal paths, HTTPS userinfo")
