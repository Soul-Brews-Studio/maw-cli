#!/usr/bin/env python3
"""Go archive installs through actual processes; isolated HOME, no Git or runtime."""
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import pty
import stat
import subprocess
import sys
import tarfile
import tempfile

command = sys.argv[1:]
if command[:1] == ["--"]:
    command = command[1:]
assert command, "usage: archive-smoke.py EXECUTABLE"
command[0] = str(Path(command[0]).resolve())

with tempfile.TemporaryDirectory(prefix="maw-archive-") as temporary:
    root = Path(temporary).resolve()
    home, plugins, empty_path = (root / name for name in ("home", "plugins space", "empty-path"))
    for directory in (home, plugins, empty_path):
        directory.mkdir()
    backup_root = Path(str(plugins) + "-backups")
    target = plugins / "demo"
    env = {k: v for k, v in os.environ.items() if not k.startswith(("MAW_", "XDG_", "GIT_"))}
    env.update(HOME=str(home), USERPROFILE=str(home), MAW_PLUGINS_DIR=str(plugins),
               MAW_CONFIG_DIR=str(home / "config"), PATH=str(empty_path))
    checks = 0
    body = b"throw new Error('archive installation must never execute this');\n"
    metadata = dict(name="demo", version="1.0.0", entry="index.js", runtime="bun-dev",
                    target="js", cli=dict(interactive=True))

    def members(changes=None):
        return [("plugin.json", json.dumps(metadata | (changes or {})).encode(), tarfile.REGTYPE, 0o644),
                ("index.js", body, tarfile.REGTYPE, 0o644),
                ("bin/helper", b"#!/bin/sh\nexit 79\n", tarfile.REGTYPE, 0o6755)]

    def archive(name, entries=None, prefix="", global_pax=None, entry_pax=None):
        path = root / name
        with tarfile.open(path, "w:gz", format=tarfile.PAX_FORMAT if global_pax or entry_pax else tarfile.USTAR_FORMAT,
                          pax_headers=global_pax) as output:
            for member, data, kind, mode in (entries if entries is not None else members()):
                info = tarfile.TarInfo(prefix + member)
                info.type, info.mode = kind, mode
                info.pax_headers = (entry_pax or {}).get(member, {})
                info.size = len(data) if kind == tarfile.REGTYPE else 0
                if kind in (tarfile.SYMTYPE, tarfile.LNKTYPE):
                    info.linkname = "index.js"
                output.addfile(info, io.BytesIO(data) if kind == tarfile.REGTYPE else None)
        return path

    def run(path, *flags, success=True, timeout=15):
        global checks
        result = subprocess.run(command + ["plugin", "install", str(path), *flags],
                                env=env, cwd=home, input="", text=True,
                                capture_output=True, timeout=timeout)
        assert (result.returncode == 0) == success, (str(path), flags, result.returncode,
                                                    result.stdout, result.stderr)
        checks += 1
        return result

    def snapshot():
        return {str(p.relative_to(root)): (p.read_bytes(), stat.S_IMODE(p.stat().st_mode))
                for folder in (plugins, backup_root) if folder.exists()
                for p in folder.rglob("*") if p.is_file() and not p.is_symlink()}

    def backups():
        return list(backup_root.rglob("plugin.json")) if backup_root.exists() else []

    flat = archive("flat.tar.gz")
    wrapped = archive("wrapped.tgz", members(dict(version="2.0.0")), "repo-commit/")
    run(flat)
    assert (target / "index.js").read_bytes() == body
    assert stat.S_IMODE((target / "bin/helper").stat().st_mode) == 0o755
    assert not (target / ".git").exists()
    assert not (home / ".maw/plugins").exists(), "MAW_PLUGINS_DIR was ignored"
    before = snapshot()
    run(wrapped, success=False)
    assert snapshot() == before, "noninteractive replacement changed installed files"
    run(wrapped, "--backup")
    assert json.loads((target / "plugin.json").read_text())["version"] == "2.0.0"
    saved = backups()
    assert len(saved) == 1 and json.loads(saved[0].read_text())["version"] == "1.0.0"
    run(flat, "--replace")
    assert backups() == saved, "--replace must not leave a new backup"
    before = snapshot()
    run(flat, "--backup", "--replace", success=False)
    assert snapshot() == before

    dotted = archive("dotted.TGZ", [("./", b"", tarfile.DIRTYPE, 0o755)] +
                     [("./" + name, data, kind, mode) for name, data, kind, mode in members()])
    run(dotted, "--replace")
    nested = archive("nested-manifest.tar.gz", members() +
                     [("examples/plugin.json", b"{}", tarfile.REGTYPE, 0o644)])
    run(nested, "--replace")
    assert (target / "examples/plugin.json").read_bytes() == b"{}"

    github_pax = archive("github-pax.tar.gz", prefix="repo-commit/",
                         global_pax={"comment": "a" * 40})
    run(github_pax, "--replace")
    assert (target / "index.js").read_bytes() == body

    checksum = hashlib.sha256(body).hexdigest()
    hashed = archive("hashed.tar.gz", members(dict(artifact=dict(path="index.js", sha256="sha256:" + checksum),
                     bundledArtifacts=[dict(path="bin/helper", sha256=hashlib.sha256(b"#!/bin/sh\nexit 79\n").hexdigest())])))
    run(hashed, "--replace")
    before = snapshot()
    run(flat, "--ref", "main", success=False)
    assert snapshot() == before

    before = snapshot()
    result = run("http://127.0.0.1:1/plugin.tar.gz", "--replace", success=False)
    assert "https" in result.stderr.lower(), result.stderr
    assert snapshot() == before
    fifo = root / "pipe.tar.gz"
    os.mkfifo(fifo)
    run(fifo, "--replace", success=False, timeout=3)
    assert snapshot() == before, "FIFO source changed existing plugin"
    lock = plugins / ".install-demo.lock"
    lock.mkdir()
    try:
        result = run(flat, "--replace", success=False)
        assert "lock" in result.stderr.lower(), result.stderr
        result = subprocess.run(command + ["plugin", "update", "demo"], env=env, cwd=home,
                                input="", text=True, capture_output=True, timeout=15)
        assert result.returncode != 0 and "lock" in result.stderr.lower(), result
        checks += 1
        assert lock.is_dir() and snapshot() == before, "contended install changed plugin or lock"
    finally:
        lock.rmdir()

    # All malformed candidates fail before replacing an existing healthy plugin.
    bad = [archive("pax-traversal.tar.gz", entry_pax={"index.js": {"path": "../escape"}})]
    for name in ("../escape", "/absolute", "dir/../../escape", "dir\\escape", "control\nfile", ".git/config"):
        bad.append(archive("bad-path-" + str(len(bad)) + ".tar.gz",
                           members() + [(name, b"bad", tarfile.REGTYPE, 0o644)]))
    for kind in (tarfile.SYMTYPE, tarfile.LNKTYPE, tarfile.FIFOTYPE, tarfile.CHRTYPE, tarfile.BLKTYPE):
        bad.append(archive("bad-kind-" + str(len(bad)) + ".tar.gz",
                           members() + [("unsafe", b"", kind, 0o644)]))
    bad.append(archive("duplicate.tar.gz", members() + [members()[1]]))
    bad.append(archive("duplicate-directory.tar.gz", members() +
                       [("empty/", b"", tarfile.DIRTYPE, 0o755)] * 2))
    bad.append(archive("missing-entry.tar.gz", members(dict(entry="missing.js"))))
    bad.append(archive("entry-traversal.tar.gz", members(dict(entry="../index.js"))))
    bad.append(archive("entry-directory.tar.gz", members(dict(entry="bin"))))
    for changes in (dict(name="../demo"), dict(name=""), dict(version="")):
        bad.append(archive("bad-manifest-" + str(len(bad)) + ".tar.gz", members(changes)))
    bad.append(archive("invalid-json.tar.gz", [("plugin.json", b"{", tarfile.REGTYPE, 0o644)] + members()[1:]))
    bad.append(archive("no-manifest.tar.gz", members()[1:]))
    bad.append(archive("mixed-root.tar.gz", [("wrapped/" + name, data, kind, mode)
                      for name, data, kind, mode in members()] + [("outside.txt", b"outside", tarfile.REGTYPE, 0o644)]))
    for name, content in (("not-gzip.tar.gz", b"not gzip"),
                          ("truncated.tar.gz", flat.read_bytes()[:-8]),
                          ("bad-crc.tar.gz", flat.read_bytes()[:-8] + b"\0" * 8)):
        path = root / name
        path.write_bytes(content)
        bad.append(path)
    for changes in (dict(artifact=dict(path="index.js", sha256="0" * 64)),
                    dict(artifact=dict(path="index.js", sha256="not-a-digest")),
                    dict(bundledArtifacts=[dict(path="bin/helper", sha256="0" * 64)]),
                    dict(bundledArtifacts=[dict(path="../escape", sha256=checksum)]),
                    dict(bundledArtifacts=[dict(path="absent", sha256=checksum)]),
                    dict(artifact="invalid"), dict(bundledArtifacts="invalid"),
                    dict(artifact=dict(path="index.js", sha256=checksum),
                         bundledArtifacts=[dict(path="index.js", sha256=checksum)])):
        bad.append(archive("bad-hash-" + str(len(bad)) + ".tar.gz", members(changes)))
    bad.append(archive("large-manifest.tar.gz", members(dict(description="x" * (1024 * 1024)))))
    bad.append(archive("many-headers.tar.gz", members() +
                       [(f"dir-{n}/", b"", tarfile.DIRTYPE, 0o755) for n in range(4096)]))
    large_header = tarfile.TarInfo("too-large")
    large_header.size = 512 * 1024 * 1024 + 1
    oversized = root / "oversized-entry.tar.gz"
    oversized.write_bytes(gzip.compress(large_header.tobuf(format=tarfile.USTAR_FORMAT) + b"\0" * 1024))
    bad.append(oversized)
    for path in bad:
        before = snapshot()
        run(path, "--replace", success=False)
        assert snapshot() == before, f"invalid archive mutated old installation: {path.name}"
    assert not (root / "escape").exists()

    # A target symlink must never redirect replacement into another directory.
    preserved = plugins / "preserved"
    target.rename(preserved)
    target.symlink_to(preserved, target_is_directory=True)
    run(flat, "--replace", success=False)
    assert target.is_symlink() and (preserved / "index.js").read_bytes() == body
    target.unlink()
    target.write_text("not a directory")
    run(flat, "--backup", success=False)
    assert target.read_text() == "not a directory"
    target.unlink()
    preserved.rename(target)

    def prompt(answer, success):
        global checks
        master, slave = pty.openpty()
        try:
            process = subprocess.Popen(command + ["plugin", "install", str(wrapped)],
                                       env=env, cwd=home, stdin=slave, stdout=subprocess.PIPE,
                                       stderr=subprocess.PIPE, text=True)
            os.write(master, answer)
            try:
                stdout, stderr = process.communicate(timeout=15)
            except subprocess.TimeoutExpired:
                process.kill()
                process.communicate()
                raise AssertionError("archive replacement prompt did not complete")
            assert (process.returncode == 0) == success, (answer, process.returncode, stdout, stderr)
            assert "backup" in (stdout + stderr).lower(), (stdout, stderr)
            checks += 1
        finally:
            os.close(master)
            os.close(slave)

    before = snapshot()
    prompt(b"c\n", True)
    assert snapshot() == before, "cancel changed existing plugin"
    prompt(b"\x04", True)
    assert snapshot() == before, "terminal EOF changed existing plugin"
    count = len(backups())
    prompt(b"\n", True)
    assert len(backups()) == count + 1, "default prompt must backup before replacing"
    run(flat, "--replace")
    count = len(backups())
    prompt(b"r\n", True)
    assert len(backups()) == count, "replace prompt unexpectedly left backup"
    assert json.loads((target / "plugin.json").read_text())["version"] == "2.0.0"
    print(f"archive smoke: {checks} actual-process cases passed (no Git/runtime/network)")
