#!/usr/bin/env python3
"""Build and smoke one native prebuilt, then package only the binary and provenance."""
import argparse
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile

ROOT = Path(__file__).resolve().parents[2]


def run(command, **kwargs):
    print("+ " + " ".join(map(str, command)), flush=True)
    subprocess.run(command, check=True, cwd=ROOT, **kwargs)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--language", choices=("go", "rs", "js", "zig"), required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--os", choices=("linux", "darwin"), required=True)
    parser.add_argument("--arch", choices=("amd64", "arm64"), required=True)
    args = parser.parse_args()
    if not re.fullmatch(r"v[0-9]+\.[0-9]+\.[0-9]+-alpha\.[0-9]+", args.version):
        parser.error("version must be an alpha CalVer tag: vYY.M.D-alpha.HMM (no run-ID suffix)")
    if not re.fullmatch(r"[0-9a-f]{40}", args.commit):
        parser.error("commit must be a full lowercase 40-character SHA")
    host_arch = {"x86_64": "amd64", "amd64": "amd64", "aarch64": "arm64", "arm64": "arm64"}.get(platform.machine().lower())
    if (platform.system().lower(), host_arch) != (args.os, args.arch):
        parser.error("native runner OS/architecture must match the requested asset")
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    if head != args.commit:
        parser.error("requested commit does not match checked-out HEAD")
    if subprocess.run(["git", "diff", "--quiet", "HEAD", "--"], cwd=ROOT).returncode:
        parser.error("commit tracked changes before building release provenance")
    untracked = subprocess.check_output(
        ["git", "ls-files", "--others", "--exclude-standard", "--", "src", "package.json", "utils/scripts"],
        cwd=ROOT, text=True)
    if untracked:
        parser.error("commit new source/build files before building release provenance")
    epoch = int(subprocess.check_output(["git", "show", "-s", "--format=%ct", "HEAD"], cwd=ROOT, text=True))
    name = "maw-" + args.language
    destination = args.output.resolve()
    destination.mkdir(parents=True, exist_ok=True)
    archive = destination / f"maw-{args.language}-{args.os}-{args.arch}.tar.gz"
    if archive.exists():
        parser.error(f"refusing to replace existing archive: {archive}")
    with tempfile.TemporaryDirectory(prefix="maw-release-") as temporary:
        work = Path(temporary)
        binary = work / name
        env = dict(os.environ, SOURCE_DATE_EPOCH=str(epoch))
        if args.language == "go":
            env.update(CGO_ENABLED="0", GOOS=args.os, GOARCH=args.arch)
            run(["go", "build", "-trimpath", "-buildvcs=false", "-ldflags", f"-s -w -X main.releaseVersion={args.version}",
                 "-o", str(binary), "./src/go/cmd/maw-go"], env=env)
        elif args.language == "rs":
            env.update(MAW_VERSION=args.version, CARGO_TARGET_DIR=str(work / "cargo"), CARGO_REGISTRIES_CRATES_IO_PROTOCOL="sparse")
            run(["cargo", "build", "--locked", "--release", "--manifest-path", "src/rs/Cargo.toml"], env=env)
            binary = work / "cargo/release/maw-rs"
        elif args.language == "js":
            run(["bun", "build", "--compile", "--minify", "--define", "MAW_VERSION=" + json.dumps(args.version),
                 "src/js/src/cli.ts", "--outfile", str(binary)], env=env)
        else:
            run(["zig", "build", "--build-file", "src/zig/build.zig", "-Doptimize=ReleaseFast", "-Dversion=" + args.version,
                 "--cache-dir", str(work / "zig-cache"), "--prefix", str(work / "zig-out")], env=env)
            binary = work / "zig-out/bin/maw-zig"
        # No ambient operational maw plugins should run during the version check.
        empty_path = work / "empty-path"
        empty_path.mkdir()
        smoke_env = dict(env, PATH=str(empty_path))
        actual = subprocess.check_output([str(binary), "version"], env=smoke_env, text=True)
        if actual != f"maw {args.version}\n":
            raise SystemExit(f"unexpected binary version: {actual!r}")
        run(["sh", "utils/scripts/smoke.sh", str(binary)], env=env)
        if args.language == "go":
            run([sys.executable, "utils/scripts/mcp-smoke.py", str(binary)], env=env)
        payload = binary.read_bytes()
        metadata = json.dumps(dict(tag=args.version, commit=args.commit, language=args.language,
                                   os=args.os, arch=args.arch, sha256=hashlib.sha256(payload).hexdigest()),
                              sort_keys=True, indent=2).encode() + b"\n"
        # Stable tar headers and gzip envelope; compiler reproducibility is separate.
        packed = work / archive.name
        with packed.open("wb") as raw:
            with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=epoch) as compressed:
                with tarfile.open(fileobj=compressed, mode="w", format=tarfile.USTAR_FORMAT) as tar:
                    for member, mode, data in ((name, 0o755, payload), ("RELEASE.json", 0o644, metadata)):
                        info = tarfile.TarInfo(member)
                        info.size, info.mode, info.mtime = len(data), mode, epoch
                        tar.addfile(info, io.BytesIO(data))
        # Exclusive creation avoids overwriting another concurrent publisher's output.
        with archive.open("xb") as output, packed.open("rb") as source:
            shutil.copyfileobj(source, output)
    print(archive)


if __name__ == "__main__":
    main()
