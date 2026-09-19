"""Install the pinned official Zig toolchain into this GitHub runner's temp dir."""
import hashlib
import json
import os
from pathlib import Path
import platform
import tarfile
import tempfile
from urllib.request import urlopen

version = "0.16.0"
arch = {"x86_64": "x86_64", "arm64": "aarch64", "aarch64": "aarch64"}[platform.machine()]
system = {"Linux": "linux", "Darwin": "macos"}[platform.system()]
with urlopen("https://ziglang.org/download/index.json", timeout=60) as response:
    entry = json.load(response)[version][f"{arch}-{system}"]
if not entry["tarball"].startswith(f"https://ziglang.org/download/{version}/"):
    raise SystemExit("unexpected Zig download URL")
destination = Path(tempfile.mkdtemp(prefix="maw-zig-", dir=os.environ["RUNNER_TEMP"]))
archive = destination / "zig.tar.xz"
with urlopen(entry["tarball"], timeout=120) as response:
    data = response.read()
if hashlib.sha256(data).hexdigest() != entry["shasum"]:
    raise SystemExit("Zig archive checksum mismatch")
archive.write_bytes(data)
with tarfile.open(archive) as bundle:
    bundle.extractall(destination, filter="data")
binary, = destination.glob("*/zig")
with open(os.environ["GITHUB_PATH"], "a") as output:
    output.write(str(binary.parent) + "\n")
print(f"Installed Zig {version} ({arch}-{system}); official SHA256 verified")
