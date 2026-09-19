#!/usr/bin/env python3
"""Go marketplace details: local metadata/Git only, with no plugin mutations."""
import hashlib
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
assert command, "usage: marketplace-smoke.py -- EXECUTABLE"
git = shutil.which("git")
assert git, "Git is required for marketplace smoke"

with tempfile.TemporaryDirectory(prefix="maw-marketplace-") as temporary:
    root = Path(temporary).resolve()
    home, plugins, config = [root / name for name in ("home", "plugins", "config")]
    home.mkdir()
    env = {k: v for k, v in os.environ.items() if not k.startswith(("MAW_", "XDG_", "GIT_"))}
    env.update(HOME=str(home), USERPROFILE=str(home), MAW_PLUGINS_DIR=str(plugins),
               MAW_CONFIG_DIR=str(config), GIT_CONFIG_NOSYSTEM="1",
               GIT_CONFIG_GLOBAL="/dev/null", GIT_TERMINAL_PROMPT="0")

    def snapshot():
        return {str(p.relative_to(root)): (p.lstat().st_mode, p.lstat().st_mtime_ns,
                os.readlink(p) if p.is_symlink() else
                hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else None)
                for p in root.rglob("*")}

    def run(expected, *args, extra=None, warning=None):
        before = snapshot()
        hostile = dict(env, GIT_DIR=str(root / "wrong-repo"), GIT_WORK_TREE=str(home),
                       GIT_CONFIG_COUNT="1", GIT_CONFIG_KEY_0="core.fsmonitor",
                       GIT_CONFIG_VALUE_0=str(root / "never-execute"))
        hostile.update(extra or {})
        result = subprocess.run(command + ["marketplace", *args], cwd=home, env=hostile,
                                text=True, capture_output=True, timeout=20)
        assert result.returncode == 0, result.stderr
        lines = result.stdout.splitlines()
        assert lines[0] == "NAME\tSTATUS\tVERSION\tREF\tCOMMIT\tSOURCE", lines
        fields = lines[1].split("\t")
        assert fields[:5] == ["herdr", *expected], fields
        assert fields[5] == "https://github.com/Soul-Brews-Studio/maw-herdr-plugin", fields
        if warning:
            assert warning in result.stderr, result.stderr
        else:
            assert not result.stderr, result.stderr
        assert snapshot() == before, "marketplace modified fixture files"

    def g(*args, cwd=None):
        result = subprocess.run([git, "-c", "core.hooksPath=/dev/null", "-c", "user.name=Smoke",
                                 "-c", "user.email=smoke@example.invalid", *args],
                                cwd=cwd or plugin, env=env, text=True, capture_output=True, timeout=15)
        assert result.returncode == 0, result.stderr
        return result.stdout.strip()

    run(["not-installed", "-", "-", "-"])
    run(["not-installed", "-", "-", "-"], "ls")
    assert not plugins.exists() and not config.exists()
    plugin = plugins / "herdr"
    plugin.mkdir(parents=True)
    (plugin / "plugin.json").write_text(json.dumps({"name": "herdr", "version": "1.2.3",
                                                  "entry": "index.js"}))
    (plugin / "index.js").write_text("throw new Error('must never execute');\n")
    run(["installed", "1.2.3", "-", "-"], "list")
    # Even inside an enclosing Git checkout, non-Git plugins have no Git identity.
    g("init", "-q", "--initial-branch=outer", cwd=root)
    g("add", "plugins", cwd=root)
    g("-c", "user.name=Smoke", "-c", "user.email=smoke@example.invalid",
      "commit", "-qm", "outer", cwd=root)
    run(["installed", "1.2.3", "-", "-"])
    g("init", "-q", "--initial-branch=alpha")
    g("add", ".")
    g("-c", "user.name=Smoke", "-c", "user.email=smoke@example.invalid", "commit", "-qm", "plugin")
    commit = g("rev-parse", "HEAD")
    run(["installed", "1.2.3", "alpha", commit[:12]])
    config.mkdir()
    (config / "maw.config.json").write_text('{"disabledPlugins":["herdr"]}')
    run(["disabled", "1.2.3", "alpha", commit[:12]])
    (config / "maw.config.json").write_text('{"disabledPlugins":[]}')
    g("checkout", "--detach", "-q", commit)
    run(["installed", "1.2.3", "detached", commit[:12]])
    g("tag", "v1.2.3")
    run(["installed", "1.2.3", "v1.2.3", commit[:12]])
    empty_path = root / "empty-path"
    empty_path.mkdir()
    run(["installed", "1.2.3", "-", "-"], extra={"PATH": str(empty_path)},
        warning="cannot read herdr Git metadata")
    head = plugin / ".git" / "HEAD"
    saved_head = head.read_text()
    head.write_text("not a valid HEAD\n")
    run(["installed", "1.2.3", "-", "-"], warning="cannot read herdr Git metadata")
    head.write_text("0" * 40 + "\n")
    run(["installed", "1.2.3", "-", "-"], warning="cannot read herdr Git metadata")
    head.write_text(saved_head)
    # Symlink installations report the actual plugin root, not its parent.
    actual = root / "linked-source"
    plugin.rename(actual)
    plugin.symlink_to(actual, target_is_directory=True)
    run(["installed", "1.2.3", "v1.2.3", commit[:12]])
    (plugin / "plugin.json").write_text("{broken")
    run(["invalid", "-", "-", "-"], warning="no valid plugin.json")
    (plugin / "plugin.json").unlink()
    run(["invalid", "-", "-", "-"], warning="no valid plugin.json")

print("marketplace smoke passed: absent, local/Git, disabled, branch/tag/commit, symlink, invalid, inert")
