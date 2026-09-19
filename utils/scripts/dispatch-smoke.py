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
        current = env | (changes or {})
        result = subprocess.run(command + args, env=current, cwd=root, input=stdin,
                                text=True, capture_output=True, timeout=10)
        assert result.returncode == code, (args, result.returncode, result.stdout, result.stderr)
        return result

    for args in ([], ["help"], ["--help"], ["version"], ["plugin", "ls"], ["plugin", "ls", "-v"]):
        run(args)
    assert not marker.exists(), "listing/help imported or executed a plugin"
    passthrough = ["two words", "", "*.go", "$(touch injected)", "--", "-h"]
    result = run(["probe"] + passthrough, 7, stdin="hello stdin\n")
    assert json.loads(result.stdout) == dict(argv=[str(probe / "entry.mjs")] + passthrough,
        stdin="hello stdin\n", cwd=str(root), value="unchanged"), result.stdout
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

    disabled = config / "maw.config.10.json"
    disabled.write_text(json.dumps(dict(disabledPlugins=["probe", "other-name"])))
    for args in (["probe"], ["help", "probe"], ["alias"]):
        assert "disabled" in run(args, 1).stderr
    manifest("shadow", "z-shadow", cli=dict(command="probe", interactive=True))
    assert "plugin probe is disabled" in run(["probe"], 1).stderr
    assert not marker.exists()
    disabled.write_text("{")
    run(["probe"], 1)
    assert not marker.exists()
    run(["version"])
    disabled.unlink()

    for name, fields in (("module", dict(cli=dict(command="module"))),
                         ("wasm", dict(target="wasm")), ("runtime", dict(runtime="other"))):
        manifest(name, name, **fields)
        assert "not a standalone Bun CLI" in run([name], 126).stderr
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
    assert run(["probe"]).stdout == "PATH wins\n"
    path_probe.unlink()
    assert not marker.exists()

    runtime.chmod(0o644)
    assert "requires bun on PATH" in run(["probe"], 126).stderr
    runtime.chmod(0o755)
    assert "requires bun on PATH" in run(["probe"], 126, dict(PATH="bin")).stderr
    assert not marker.exists()
    runtime_source = runtime.read_text()
    runtime.write_text("#!/nonexistent-maw-dispatch-interpreter\n")
    result = run(["probe"], 126)
    assert "cannot execute" in result.stderr, result.stderr
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
        assert json.loads(result.stdout) == dict(args=passthrough, input="actual input", cwd=str(root))
        assert result.stderr == "real Bun stderr\n"

print("dispatch smoke: installed Bun scripts, alias/help, args/streams/cwd/exit, gating and precedence OK")
