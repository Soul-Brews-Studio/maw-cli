#!/usr/bin/env python3
"""Actual-process lifecycle fixture: local Git only, no user plugins or network."""
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
assert command, "usage: lifecycle-smoke.py -- EXECUTABLE [ENTRY]"
git = shutil.which("git")
assert git, "Git is required for lifecycle smoke"

with tempfile.TemporaryDirectory(prefix="maw-lifecycle-") as temporary:
    root = Path(temporary).resolve()
    source, home, plugins = (root / name for name in ("source", "home", "plugins"))
    source.mkdir()
    home.mkdir()
    env = {k: v for k, v in os.environ.items() if not k.startswith(("MAW_", "XDG_", "GIT_"))}
    env.update(HOME=str(home), USERPROFILE=str(home), MAW_PLUGINS_DIR=str(plugins),
               MAW_CONFIG_DIR=str(home / "config"), GIT_CONFIG_NOSYSTEM="1",
               GIT_CONFIG_GLOBAL="/dev/null", GIT_TERMINAL_PROMPT="0")

    def g(*args, cwd=source):
        result = subprocess.run([git, "-c", "core.hooksPath=/dev/null", *args], cwd=cwd,
                                env=env, text=True, capture_output=True, timeout=15)
        assert result.returncode == 0, (args, result.stderr)
        return result.stdout.strip()

    def commit(message):
        g("add", "--all")
        g("-c", "user.name=Smoke", "-c", "user.email=smoke@example.invalid", "commit", "-qm", message)
        return g("rev-parse", "HEAD")

    def run(*args, status=0):
        # Host must discard inherited Git routing; a mistake touches the fixture sentinel.
        run_env = dict(env, GIT_DIR=str(root / "not-a-repo"),
                       GIT_CONFIG_GLOBAL=str(home / ".gitconfig"))
        result = subprocess.run(command + list(args), cwd=home, env=run_env,
                                text=True, capture_output=True, timeout=20)
        assert result.returncode == status, (args, result.returncode, result.stdout, result.stderr)
        return result.stdout

    g("init", "-q", "--initial-branch=main")
    manifest = {"name": "demo", "version": "1.0", "entry": "index.js",
                "runtime": "bun-dev", "target": "js", "cli": {"interactive": True}}
    (source / "plugin.json").write_text(json.dumps(manifest))
    (source / "index.js").write_text("throw new Error('entry must not execute');\n")
    first = commit("first")
    first_hash = g("hash-object", "--no-filters", "index.js")
    hook = root / "hooks"
    hook.mkdir()
    (hook / "post-checkout").write_text(f"#!/bin/sh\ntouch '{root / 'hook-ran'}'\n")
    (hook / "post-checkout").chmod(0o755)
    (home / ".gitconfig").write_text(f'[core]\n hooksPath = "{hook}"\n')

    assert "herdr" in run("marketplace")
    assert run("marketplace", "ls") == run("marketplace", "list")
    assert not plugins.exists(), "marketplace created plugin root"
    run("plugin", "install", status=2)
    run("plugin", "install", str(source))
    installed = plugins / "demo"
    assert first in run("plugin", "info", "demo")
    assert first_hash in run("plugin", "check", "demo")
    assert "clean" in run("plugins", "check", "demo")
    assert run("plugin", "list") == run("plugin", "ls")
    assert not (root / "hook-ran").exists(), "Git hook executed"
    run("plugin", "install", str(source), status=1)
    assert g("rev-parse", "HEAD", cwd=installed) == first

    (source / "index.js").write_text("throw new Error('updated entry must not execute');\n")
    second = commit("second")
    run("plugin", "update", "demo")
    assert g("rev-parse", "HEAD", cwd=installed) == second
    assert second in run("plugin", "info", "demo")
    (installed / "index.js").write_text("tampered bytes\n")
    assert "modified" in run("plugin", "info", "demo")
    run("plugin", "check", "demo", status=1)
    run("plugin", "update", "demo", status=1)
    g("checkout", "--", "index.js", cwd=installed)
    (installed / "untracked").write_text("preserve me")
    run("plugin", "update", "demo", status=1)
    (installed / "untracked").unlink()
    run("plugin", "update", "demo", "--ref", first)
    assert g("rev-parse", "HEAD", cwd=installed) == first
    assert "pinned" in run("plugin", "update", "demo").lower()
    assert g("rev-parse", "HEAD", cwd=installed) == first
    run("plugin", "update", "demo", "--ref", second)
    assert g("rev-parse", "HEAD", cwd=installed) == second
    (installed / ".git/hooks").mkdir(exist_ok=True)
    (installed / ".git/hooks/post-checkout").write_text(f"#!/bin/sh\ntouch '{root / 'hook-ran'}'\n")
    (installed / ".git/hooks/post-checkout").chmod(0o755)
    run("plugin", "update", "demo", "--ref", first)
    run("plugin", "update", "demo", "--ref", second)
    assert not (root / "hook-ran").exists(), "installed repository hook executed"
    hostile = subprocess.run(command + ["plugin", "update", "demo", "--ref", "main:refs/heads/unsafe"],
                             cwd=home, env=env, text=True, capture_output=True, timeout=20)
    assert hostile.returncode != 0, "fetch refspec was accepted"
    assert g("rev-parse", "HEAD", cwd=installed) == second
    assert not g("branch", "--list", "unsafe", cwd=installed), "refspec changed a local branch"

    manifest["entry"] = ":(top)index.js"
    (source / "plugin.json").write_text(json.dumps(manifest))
    bad_pathspec = commit("invalid Git pathspec entry")
    run("plugin", "update", "demo", "--ref", bad_pathspec, status=1)
    assert g("rev-parse", "HEAD", cwd=installed) == second, "invalid candidate changed checkout"
    manifest["entry"] = "index.js"
    manifest["name"] = "renamed"
    (source / "plugin.json").write_text(json.dumps(manifest))
    renamed = commit("invalid name change")
    run("plugin", "update", "demo", "--ref", renamed, status=1)
    assert g("rev-parse", "HEAD", cwd=installed) == second
    manifest["name"] = "../escaped"
    (source / "plugin.json").write_text(json.dumps(manifest))
    bad_name = commit("invalid install name")
    run("plugin", "install", str(source), "--ref", bad_name, status=1)
    assert not (root / "escaped").exists()
    manifest["name"] = ".git"
    (source / "plugin.json").write_text(json.dumps(manifest))
    git_name = commit("reserved Git directory name")
    run("plugin", "install", str(source), "--ref", git_name, status=1)
    assert not (plugins / ".git").exists()
    manifest.update(name="linked", entry="link.js")
    (source / "plugin.json").write_text(json.dumps(manifest))
    (source / "link.js").symlink_to("index.js")
    link = commit("symlink entry")
    run("plugin", "install", str(source), "--ref", link, status=1)
    assert not (plugins / "linked").exists()
    (plugins / "alias").symlink_to(installed, target_is_directory=True)
    run("plugin", "update", "alias", status=1)
    run("plugin", "info", "alias", status=1)
    (plugins / "alias").unlink()

    # Full SHA installation succeeds even when it is not the remote's newest commit.
    shutil.rmtree(installed)  # fixture-owned path only
    run("plugin", "install", str(source), "--ref", first)
    assert first in run("plugin", "info", "demo")
    assert "pinned" in run("plugin", "update", "demo").lower()
    assert not (root / "hook-ran").exists()
    assert sorted(p.name for p in plugins.iterdir()) == ["demo"], "staging directories leaked"
    # Checkout transformations may differ from raw committed bytes. Installation
    # still succeeds; an explicitly requested raw-byte check reports the difference.
    manifest.update(name="crlf", entry="index.js")
    (source / "plugin.json").write_text(json.dumps(manifest))
    (source / ".gitattributes").write_text("index.js text eol=crlf\n")
    transformed = commit("checkout line-ending transform")
    run("plugin", "install", str(source), "--ref", transformed)
    assert (plugins / "crlf/index.js").read_bytes().endswith(b"\r\n")
    run("plugin", "check", "crlf", status=1)
    print("lifecycle: catalog, Git install/update/pins, entry blob check, dirty/symlink/name protection OK")
