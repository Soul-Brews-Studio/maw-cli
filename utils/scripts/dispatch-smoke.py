#!/usr/bin/env python3
"""Subprocess contract checks; isolated plugins and a tiny stand-in Bun executable."""
import json
import os
from pathlib import Path
import pty
import shutil
import subprocess
import sys
import tempfile
import time

command = sys.argv[1:]
if command[:1] == ["--"]:
    command = command[1:]
if not command:
    raise SystemExit("usage: dispatch-smoke.py -- EXECUTABLE [ENTRY]")
command[0] = str(Path(command[0]).resolve())
if len(command) > 1:
    command[1] = str(Path(command[1]).resolve())
real_bun = shutil.which("bun")

with tempfile.TemporaryDirectory(prefix="maw-dispatch-") as temporary:
    root = Path(temporary)
    home, plugins, config, binaries = [root / name for name in ("home", "plugins # %", "config", "bin")]
    for directory in (home, plugins, config, binaries):
        directory.mkdir()
    env = {k: v for k, v in os.environ.items() if not k.startswith(("MAW_", "XDG_"))}
    env.update(HOME=str(home), USERPROFILE=str(home), MAW_PLUGINS_DIR=str(plugins),
               MAW_CONFIG_DIR=str(config), PATH=str(binaries), MAW_DISPATCH_VALUE="unchanged")
    marker = root / "marker"
    env["MAW_DISPATCH_MARKER"] = str(marker)
    runtime = binaries / "bun"
    runtime.write_text(f"#!{sys.executable}\n" + """import json, os, sys
from pathlib import Path
Path(os.environ['MAW_DISPATCH_MARKER']).write_text('executed')
if sys.argv[-1:] == ['--tty-probe']:
    print(json.dumps(dict(tty=sys.stdin.isatty())))
    sys.exit(0)
print(json.dumps(dict(argv=sys.argv[1:], stdin=sys.stdin.read(), cwd=os.getcwd(), value=os.environ['MAW_DISPATCH_VALUE'])))
print('plugin stderr', file=sys.stderr)
sys.exit(7)
""")
    runtime.chmod(0o755)

    def manifest(folder, name, **changes):
        directory = plugins / folder
        directory.mkdir(exist_ok=True)
        value = dict(name=name, version="1", runtime="bun-dev", target="js", entry="entry.mjs",
                     cli=dict(command=name, interactive=True))
        value.update(changes)
        (directory / "plugin.json").write_text(json.dumps(value))
        (directory / "entry.mjs").write_text("throw new Error('not imported while listing');\n")
        return directory

    probe = manifest("probe space", "probe")
    alias = manifest("alias", "other-name", cli=dict(command="alias", interactive=True),
                     entry="", artifact=dict(path="entry.mjs"))

    def run(args, code=0, changes=None, stdin=""):
        # code=None probes without asserting, for capability detection.
        current = env | (changes or {})
        result = subprocess.run(command + args, env=current, cwd=root, input=stdin,
                                text=True, capture_output=True, timeout=10)
        if code is not None:
            assert result.returncode == code, (args, result.returncode, result.stdout, result.stderr)
        return result

    for args in ([], ["help"], ["--help"], ["version"], ["plugin", "ls"], ["plugin", "ls", "-v"]):
        run(args)
    assert not marker.exists(), "listing/help imported or executed a plugin"
    passthrough = ["two words", "", "*.go", "$(touch injected)", "--", "-h"]
    result = run(["probe"] + passthrough, 7, stdin="hello stdin\n")
    assert json.loads(result.stdout) == dict(argv=[str(probe / "entry.mjs")] + passthrough,
        # getcwd resolves directory symlinks, including macOS /var -> /private/var.
        stdin="hello stdin\n", cwd=str(root.resolve()), value="unchanged"), result.stdout
    assert result.stderr == "plugin stderr\n", result.stderr
    assert not (root / "injected").exists()
    for args in (["probe", "--help"], ["help", "probe"]):
        result = run(args, 7)
        assert json.loads(result.stdout)["argv"] == [str(probe / "entry.mjs"), "--help"]
    assert json.loads(run(["alias"], 7).stdout)["argv"] == [str(alias / "entry.mjs")]
    run(["other-name"], 2)
    master, slave = pty.openpty()
    try:
        tty = subprocess.run(command + ["probe", "--tty-probe"], env=env, cwd=root,
                             stdin=slave, text=True, capture_output=True, timeout=10)
        assert tty.returncode == 0 and json.loads(tty.stdout) == dict(tty=True), tty
    finally:
        os.close(master)
        os.close(slave)
    marker.unlink()

    # `version` or `--version` as the ONLY argument is a reserved plugin verb:
    # the host answers from plugin.json and never runs plugin code (#52).
    sentinel = "PLUGIN-CODE-RAN"
    versioned = manifest("versioned", "versioned", version="2.5.0-rc.1")
    (versioned / "entry.mjs").write_text(f"console.log('{sentinel}');\nprocess.exit(3);\n")
    real_git = shutil.which("git")
    assert real_git, "dispatch smoke needs git on PATH"
    git_link = binaries / "git"
    git_link.symlink_to(real_git)  # present, so "not a Git checkout" is a real answer

    def answers(args, expected):
        result = run(args)
        assert result.stdout == expected + "\n" and result.stderr == "", (args, result)
        assert sentinel not in result.stdout + result.stderr, (args, result)
        assert not marker.exists(), ("version executed plugin code", args)

    fixture_git = {k: v for k, v in env.items() if not k.startswith("GIT_")}
    fixture_git.update(PATH=os.environ.get("PATH", ""), GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1")

    def git(directory, *args):
        return subprocess.run([real_git, "-C", str(directory), "-c", "user.name=maw", "-c", "user.email=maw@localhost",
                               *args], env=fixture_git, check=True, capture_output=True, text=True).stdout.strip()

    outside = subprocess.run([real_git, "-C", str(root), "rev-parse", "--is-inside-work-tree"],
                             env=fixture_git, capture_output=True).returncode != 0
    assert outside, (f"fixture root {root} is inside a Git work tree, so every plugin would show its commit; "
                     f"rerun from a temporary directory outside one:\n  TMPDIR=\"$(mktemp -d /tmp/maw-dispatch-XXXX)\" "
                     f"python3 utils/scripts/dispatch-smoke.py -- {' '.join(command)}")

    for verb in ("version", "--version"):
        answers(["versioned", verb], "versioned 2.5.0-rc.1 (not a Git checkout)")
        answers(["alias", verb], "other-name 1 (not a Git checkout)")  # manifest name, not the command
    for extra in (["version", "extra"], ["--version", "extra"], ["foo", "version"], ["-v"]):
        result = run(["versioned"] + extra, 7)
        assert json.loads(result.stdout)["argv"] == [str(versioned / "entry.mjs")] + extra, result.stdout
        marker.unlink()
    # Only dispatch's own name/alias resolution answers, never a raw folder name:
    # a stray copy declaring an existing name (a "herdrbak") and a folder named
    # unlike its manifest are reachable only by what their manifests declare.
    manifest("versionedbak", "versioned", version="0.4.0")
    manifest("folder-only", "manifest-only")
    for stray in ("versionedbak", "folder-only"):
        assert "unknown command" in run([stray, "version"], 2).stderr
    answers(["versioned", "version"], "versioned 2.5.0-rc.1 (not a Git checkout)")
    answers(["manifest-only", "version"], "manifest-only 1 (not a Git checkout)")
    for folder in ("versionedbak", "folder-only"):
        shutil.rmtree(plugins / folder)

    checkout = manifest("checkout", "checkout", version="3.0.0")
    git(checkout, "init", "-q")
    git(checkout, "commit", "-q", "--allow-empty", "-m", "fixture")
    short = git(checkout, "rev-parse", "--short", "HEAD")
    for verb in ("version", "--version"):
        answers(["checkout", verb], f"checkout 3.0.0 ({short})")
    # A plugin symlinked from a subfolder of a larger repository answers with that
    # repository's commit (installed plugins such as relic are shaped this way).
    monorepo = root / "monorepo"
    (monorepo / "tools").mkdir(parents=True)
    shutil.move(str(manifest("linked", "linked", version="4.0.0")), str(monorepo / "tools" / "linked"))
    (plugins / "linked").symlink_to(monorepo / "tools" / "linked", target_is_directory=True)
    git(monorepo, "init", "-q")
    git(monorepo, "add", ".")
    git(monorepo, "commit", "-q", "-m", "monorepo")
    answers(["linked", "version"], f"linked 4.0.0 ({git(monorepo, 'rev-parse', '--short', 'HEAD')})")
    # Any enclosing work tree answers; a nested checkout still answers for itself.
    git(root, "init", "-q")
    git(root, "commit", "-q", "--allow-empty", "-m", "enclosing")
    enclosing = git(root, "rev-parse", "--short", "HEAD")
    answers(["versioned", "version"], f"versioned 2.5.0-rc.1 ({enclosing})")
    answers(["checkout", "version"], f"checkout 3.0.0 ({short})")
    shutil.rmtree(root / ".git")
    # A git that hangs is cut short and falls back; no git at all falls back too.
    git_link.unlink()
    git_link.write_text(f"#!{sys.executable}\nimport time\ntime.sleep(30)\n")
    git_link.chmod(0o755)
    started = time.monotonic()
    answers(["checkout", "version"], "checkout 3.0.0 (not a Git checkout)")
    assert time.monotonic() - started < 8, "git timeout is not short"
    git_link.unlink()
    answers(["checkout", "version"], "checkout 3.0.0 (not a Git checkout)")

    disabled = config / "maw.config.10.json"
    disabled.write_text(json.dumps(dict(disabledPlugins=["probe", "other-name"])))
    for args in (["probe"], ["help", "probe"], ["alias"], ["probe", "version"], ["alias", "--version"]):
        assert "disabled" in run(args, 1).stderr
    manifest("shadow", "z-shadow", cli=dict(command="probe", interactive=True))
    assert "plugin probe is disabled" in run(["probe"], 1).stderr
    assert not marker.exists()
    disabled.write_text("{")
    run(["probe"], 1)
    assert not marker.exists()
    run(["version"])
    disabled.unlink()

    manifest("module", "module", cli=dict(command="module"))
    permissive = "not a standalone Bun CLI" not in run(["module"], None).stderr
    for name, fields in (("module", dict(cli=dict(command="module"))),
                         ("runtime", dict(runtime="other")), ("targetless", dict(target=None))):
        manifest(name, name, **fields)
        if not permissive:
            assert "not a standalone Bun CLI" in run([name], 126).stderr
            continue
        marker.unlink(missing_ok=True)
        run([name], 7)
        assert marker.exists(), name
    manifest("missing", "missing", entry="missing.mjs")
    manifest("directory", "directory", entry=".")
    for name in ("missing", "directory"):
        assert "entry is missing or not a regular file" in run([name], 126).stderr
    for name in ("go", "rs", "js", "zig", "index"):
        manifest("reserved-" + name, name)
        run([name], 2)
        run(["help", name], 2)
    manifest("invalid", "valid-name", cli=dict(command="UPPER", interactive=True))
    run(["UPPER"], 2)
    manifest("builtin", "version")
    run(["version"])
    path_probe = binaries / "maw-probe"
    path_probe.write_text("#!/bin/sh\nprintf 'PATH wins\\n'\n")
    path_probe.chmod(0o755)
    marker.unlink(missing_ok=True)
    assert run(["probe"]).stdout == "PATH wins\n"
    path_probe.unlink()
    assert not marker.exists()

    runtime.chmod(0o644)
    if permissive:
        assert "no maw-js/Bun fallback" in run(["probe"], 2).stderr
    else:
        assert "requires bun on PATH" in run(["probe"], 126).stderr
    runtime.chmod(0o755)
    if permissive:
        assert "no maw-js/Bun fallback" in run(["probe"], 2, dict(PATH="bin")).stderr
    else:
        assert "requires bun on PATH" in run(["probe"], 126, dict(PATH="bin")).stderr
    assert not marker.exists()
    runtime_source = runtime.read_text()
    runtime.write_text("#!/nonexistent-maw-dispatch-interpreter\n")
    result = run(["probe"], 126)
    assert "cannot execute" in result.stderr, result.stderr
    assert str(runtime) in result.stderr or str(runtime.resolve()) in result.stderr, result.stderr
    assert result.stderr.rsplit(": ", 1)[-1].strip(), result.stderr
    assert not marker.exists()
    runtime.write_text(runtime_source)

    # Where Bun is installed, also execute real source code, not only the runtime stand-in.
    if real_bun:
        runtime.unlink()
        runtime.symlink_to(real_bun)
        (probe / "entry.mjs").write_text("""import { readFileSync } from 'node:fs';
console.log(JSON.stringify({args:process.argv.slice(2), input:readFileSync(0,'utf8'), cwd:process.cwd()}));
console.error('real Bun stderr');
process.exitCode=9;
""")
        result = run(["probe"] + passthrough, 9, stdin="actual input")
        assert json.loads(result.stdout) == dict(args=passthrough, input="actual input", cwd=str(root.resolve()))
        assert result.stderr == "real Bun stderr\n"
        # Real Bun would print the sentinel; `version` alone must not reach it.
        assert run(["versioned", "version", "extra"], 3).stdout == sentinel + "\n"
        answers(["versioned", "version"], "versioned 2.5.0-rc.1 (not a Git checkout)")

print("dispatch smoke: installed Bun scripts, alias/help, reserved version verb, args/streams/cwd/exit, gating and precedence OK")
