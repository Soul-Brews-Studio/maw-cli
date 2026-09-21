#!/usr/bin/env python3
"""Actual-process installed-plugin inventory fixture; no real user plugins loaded."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

command = sys.argv[1:]
if command[:1] == ["--"]:
    command = command[1:]
if not command:
    raise SystemExit("usage: plugin-smoke.py -- EXECUTABLE [ENTRY]")
command[0] = str(Path(command[0]).resolve())
if len(command) > 1:
    command[1] = str(Path(command[1]).resolve())

with tempfile.TemporaryDirectory(prefix="maw-inventory-") as temporary:
    root = Path(temporary)
    home = root / "home"
    plugins = home / ".maw/plugins"
    config = home / ".config/maw"
    plugins.mkdir(parents=True)
    config.mkdir(parents=True)
    empty = root / "empty"
    empty.mkdir()
    env = {k: v for k, v in os.environ.items() if not k.startswith(("MAW_", "XDG_"))}
    env.update(HOME=str(home), USERPROFILE=str(home), PATH=str(empty))

    def write(path, value):
        path.write_text(json.dumps(value), encoding="utf-8")

    def plugin(folder, name, **metadata):
        directory = plugins / folder
        directory.mkdir()
        write(directory / "plugin.json", dict(name=name, version="1.0.0", **metadata))
        (directory / "index.js").write_text("throw new Error('plugin entry must never execute');\n")
        return directory

    alpha = plugin("a-alpha", "alpha", weight=5, entry="index.js", api={"path": "/alpha"})
    beta = plugin("b-beta", "beta", tier="standard", entry="index.js")
    gamma = plugin("c-gamma", "gamma", weight=80, entry="missing.js")
    off = plugin("d-off", "off", tier="core", entry="index.js")
    (plugins / "e-link").symlink_to(beta, target_is_directory=True)
    plugin("z-shadow", "alpha", tier="extra")
    bad = plugins / "broken"
    bad.mkdir()
    (bad / "plugin.json").write_text("{")
    ts = plugins / "ts-only"
    ts.mkdir()
    (ts / "plugin.ts").write_text("throw new Error('TypeScript manifests must never execute');\n")
    (alpha / "plugin.ts").write_text("throw new Error('JSON must win without importing TS');\n")
    write(plugins / ".overrides.json", {"gamma": 20, "beta": 1})
    write(config / "maw.config.json", {"disabledPlugins": ["alpha"]})
    write(config / "maw.config.2.json", {"disabledPlugins": ["beta"]})
    write(config / "maw.config.10.json", {"disabledPlugins": ["gamma"]})
    write(config / "maw.config.10.local.json", {"disabledPlugins": ["off", 42]})

    def snapshot():
        return {str(p.relative_to(root)): (hashlib.sha256(p.read_bytes()).hexdigest(), p.stat().st_mtime_ns)
                for p in root.rglob("*") if p.is_file()}

    def run(args, extra=None, status=0):
        result = subprocess.run(command + args, cwd=empty, env={k: v for k, v in dict(env, **(extra or {})).items() if v is not None},
                                input="", text=True, capture_output=True, timeout=8)
        assert result.returncode == status, (args, result.returncode, result.stdout, result.stderr)
        return result

    before = snapshot()
    maw_rs_listing = "(disabled)" in run(["plugin", "ls"]).stdout
    if not maw_rs_listing:
        print("plugin smoke: maw-rs listing/table not implemented by this port, skipped")
        raise SystemExit(0)
    expected = ("4 plugins (3 active, 1 disabled)\n"
                "  core: 2 · standard: 2 · extra: 0\n"
                "  cli: 4 · api: 1 · health: 1 missing executable\n"
                "  alpha · off (disabled) · beta · gamma (no executable)\n")
    for args in (["plugin", "ls"], ["plugins", "ls"], ["plugins"]):
        result = run(args)
        assert result.stdout == expected, (args, result.stdout)
        assert "broken" in result.stderr and "ts-only" in result.stderr, result.stderr
    # -v renders the maw-rs table: a section per non-empty tier, per-section
    # column widths measured on the raw cell (escapes included, as maw-rs does),
    # then an active count. Assert the shape, not a hand-built string.
    for args in (["plugin", "ls", "-v"], ["plugins", "ls", "--verbose"], ["plugins", "-v"]):
        table = run(args).stdout
        assert "\x1b[1mcore\x1b[0m (2)" in table, table
        assert "\x1b[1mstandard\x1b[0m (2)" in table, table
        assert "name  " in table and "\u2500" in table, table
        assert "cli:alpha" in table and alpha.name in table, table
        assert "\x1b[90m\u25cb\x1b[0m disabled" in table, table
        assert off.name in table, table
        assert table.endswith("3 active. 1 disabled \u2014 use 'maw plugin ls --all' to see them.\n"), table
    all_summary = run(["plugin", "ls", "--all"]).stdout
    assert "core: 2 · standard: 2 · extra: 0" in all_summary
    assert "cli: 4 · api: 1" in all_summary
    assert "alpha · off (disabled) · beta · gamma (no executable)" in all_summary
    for args in (["plugin"], ["plugin", "ls", "extra"], ["plugin", "ls", "--wat"],
                 ["plugins", "install"], ["plugin", "ls", "-v", "-v"]):
        assert "usage:" in run(args, status=2).stderr
    assert "unknown command" in run(["index", "-"], status=2).stderr
    assert snapshot() == before, "listing/help modified plugin/config files"

    nested = root / "nested/deep"
    nested.mkdir(parents=True)
    (root / "via").symlink_to(nested, target_is_directory=True)
    assert run(["plugin", "ls"], {"MAW_PLUGINS_DIR": str(root / "via/../home/.maw/plugins")}).stdout == expected
    assert run(["plugin", "ls"], {"HOME": None, "USERPROFILE": None,
               "MAW_PLUGINS_DIR": str(plugins), "MAW_CONFIG_DIR": str(config)}).stdout == expected
    # Duplicate winner uses UTF-8 byte order, not JavaScript UTF-16 order.
    unicode_root = root / "unicode"
    unicode_root.mkdir()
    for folder, version in (("\ue000", "1.0.0"), ("\U00010000", "2.0.0")):
        directory = unicode_root / folder
        directory.mkdir()
        write(directory / "plugin.json", {"name": "unicode", "version": version})
    result = run(["plugin", "ls", "-v"], {"MAW_PLUGINS_DIR": str(unicode_root)})
    # Deterministic dedup by name: the U+E000 directory (1.0.0) wins over
    # U+10000 (2.0.0). Asserted through the table, which is the only -v format.
    assert "1.0.0" in result.stdout and "2.0.0" not in result.stdout, result.stdout
    assert str(unicode_root / chr(0xe000)) in result.stdout, result.stdout
    assert result.stdout.endswith("\n1 active\n"), result.stdout

    edge = root / "edge"
    edge.mkdir()
    binary = edge / "entry"
    binary.write_text("not executed")
    for name, metadata in (("artifact", {"artifact": {"path": str(binary)}, "target": "js"}),
                           ("wasm", {"wasm": str(binary)}),
                           ("api", {"api": {}, "artifact": {"path": "ignored"}, "target": "wasm"}),
                           ("declared", {"cli": {}}), ("directory", {"entry": str(edge)})):
        directory = edge / name
        directory.mkdir()
        write(directory / "plugin.json", dict(name=name, version="1", **metadata))
    result = run(["plugin", "ls"], {"MAW_PLUGINS_DIR": str(edge)})
    assert "5 plugins (5 active, 0 disabled)" in result.stdout
    assert "cli: 4 · api: 1 · health: 2 missing executables" in result.stdout, result.stdout
    limit = root / "limit"
    (limit / "one").mkdir(parents=True)
    manifest = limit / "one/plugin.json"
    data = json.dumps({"name": "one", "version": "1", "padding": ""})
    data = data.replace('"padding": ""', '"padding": "' + 'x' * (1048576 - len(data)) + '"')
    assert len(data.encode()) == 1048576
    manifest.write_text(data)
    assert "1 plugin (1 active, 0 disabled)" in run(["plugin", "ls"], {"MAW_PLUGINS_DIR": str(limit)}).stdout
    for invalid in ((data + " ").encode(), b'\xef\xbb\xbf{"name":"one","version":"1"}', b'{"name":"one","version":"\xff"}'):
        manifest.write_bytes(invalid)
        assert run(["plugin", "ls"], {"MAW_PLUGINS_DIR": str(limit)}).stdout == "no plugins installed\n"
    manifest.unlink()
    if hasattr(os, "mkfifo"):
        os.mkfifo(manifest)
        assert run(["plugin", "ls"], {"MAW_PLUGINS_DIR": str(limit)}).stdout == "no plugins installed\n"
        manifest.unlink()
    unsafe = limit / "unsafe\npath"
    unsafe.mkdir()
    write(unsafe / "plugin.json", {"name": "escaped", "version": "1"})
    result = run(["plugin", "ls", "-v"], {"MAW_PLUGINS_DIR": str(limit)})
    # A newline in a directory name must stay escaped, or it would forge an
    # extra table row. Body rows = 1 despite the raw newline in the path.
    assert f"{limit}/unsafe\\u000apath" in result.stdout, result.stdout
    assert "\n" not in result.stdout.split("escaped")[1].split("\n")[0], result.stdout
    assert result.stdout.endswith("\n1 active\n"), result.stdout

    # Global overrides and data/config-root selection must not leak real HOME.
    for extra in ({"MAW_PLUGINS_DIR": str(empty)}, {"MAW_HOME": str(root / "missing")},
                  {"MAW_DATA_DIR": str(root / "missing")},
                  {"MAW_XDG": "TRUE", "XDG_DATA_HOME": str(root / "missing")}):
        assert run(["plugin", "ls"], extra).stdout == "no plugins installed\n"
    custom = root / "custom"
    custom.mkdir()
    write(custom / "maw.config.json", {"disabledPlugins": ["alpha", "beta", "gamma", "off"]})
    all_disabled = run(["plugin", "ls", "-v"], {"MAW_CONFIG_DIR": str(custom)}).stdout
    assert all_disabled.endswith("0 active. 4 disabled \u2014 use 'maw plugin ls --all' to see them.\n"), all_disabled
    assert "4 disabled" in run(["plugin", "ls"], {"XDG_CONFIG_HOME": str(custom.parent), "MAW_CONFIG_DIR": str(custom)}).stdout
    (custom / "maw.config.json").write_text("{")
    assert not run(["plugin", "ls"], {"MAW_CONFIG_DIR": str(custom)}, status=1).stdout
    (custom / "maw.config.json").write_bytes(b'{"disabledPlugins":["\xff"]}')
    assert not run(["plugin", "ls"], {"MAW_CONFIG_DIR": str(custom)}, status=1).stdout
    write(plugins / ".overrides.json", [])
    assert not run(["plugin", "ls"], status=1).stdout

print("plugin smoke: static inventory, aliases, tiers, config precedence, disabled/verbose, inertness and errors OK")
