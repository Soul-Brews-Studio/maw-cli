#!/usr/bin/env python3
"""Preview CalVer or prepare/publish verified CI-built alpha prereleases."""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import tarfile
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[2]
REPO = "Soul-Brews-Studio/maw-cli"
UPSTREAM = "Soul-Brews-Studio/arra-oracle-skills-cli"
SNAPSHOT = "68110ad0641f5b7bc8a14a988971ff4ead9ad77a"
SHA256 = "5adcacb27c87282ee05960e61a88a9575af9c01ae195111395784fb0c8870c47"


def run(*args):
    return subprocess.check_output(args, cwd=ROOT, text=True).strip()


def api(endpoint, *args):
    return json.loads(run("gh", "api", endpoint, *args))


def calculator(now=None):
    # Import only the reviewed pure function: upstream main/--check can mutate.
    source = api(f"repos/{UPSTREAM}/contents/scripts/calver.ts?ref={SNAPSHOT}")
    data = base64.b64decode(source["content"])
    if hashlib.sha256(data).hexdigest() != SHA256:
        raise RuntimeError("upstream CalVer digest mismatch")
    with tempfile.TemporaryDirectory(prefix="maw-calver-") as temporary:
        directory = Path(temporary)
        (directory / "calver.ts").write_bytes(data)
        when = f",now:new Date({json.dumps(now)})" if now else ""
        wrapper = directory / "preview.ts"
        wrapper.write_text('import { computeVersion } from "./calver.ts";\n'
            'console.log("v" + computeVersion({stable:false,channel:"alpha",check:true'
            + when + '}));\n')
        tag = subprocess.check_output(["bun", str(wrapper)], cwd=ROOT,
            env=dict(os.environ, TZ="Asia/Bangkok"), text=True).strip()
    if not re.fullmatch(r"v[0-9]+\.[0-9]+\.[0-9]+-alpha\.[0-9]+", tag):
        raise RuntimeError("unexpected upstream CalVer output")
    return tag


def prepare(ci_run):
    if not re.fullmatch(r"[1-9][0-9]*", str(ci_run)):
        raise RuntimeError("CI run ID must be a positive integer")
    evidence = api(f"repos/{REPO}/actions/runs/{ci_run}")
    if (str(evidence["id"]) != str(ci_run)
            or evidence["path"] != ".github/workflows/ci.yml"
            or evidence["event"] != "push" or evidence["head_branch"] != "alpha"
            or evidence["head_repository"]["full_name"] != REPO
            or evidence["repository"]["full_name"] != REPO
            or evidence["status"] != "completed" or evidence["conclusion"] != "success"):
        raise RuntimeError("not a successful canonical alpha push CI run")
    commit = evidence["head_sha"]
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise RuntimeError("invalid CI commit")
    if api(f"repos/{REPO}/branches/alpha")["commit"]["sha"] != commit:
        return dict(skip=True, reason="CI commit superseded on alpha", ci_run=int(ci_run))
    base = calculator(evidence["created_at"])
    year, month, day, minute = re.fullmatch(r"v(\d+)\.(\d+)\.(\d+)-alpha\.(\d+)", base).groups()
    # Translate the upstream date into a v0-compatible nested Go-module label.
    go_version = f"v0.{2000 + int(year):04d}{int(month):02d}{int(day):02d}.{int(minute)}-alpha"
    # CI identity stays in provenance; the public selector is date + wall-clock minute.
    return dict(schema="maw.release.v1", skip=False, tag=base,
        go_version=go_version, go_tag=f"src/go/{go_version}", commit=commit,
        ci_run=int(ci_run), archives=[f"maw-{language}-{system}-{arch}.tar.gz"
            for language in ("go", "rs", "js", "zig")
            for system in ("linux", "darwin") for arch in ("amd64", "arm64")])


def encoded(value):
    return quote(value, safe="")


def canonical(value):
    return (json.dumps(value, sort_keys=True, indent=2) + "\n").encode()


def archive_check(path, plan):
    language, system, arch = path.name.removeprefix("maw-").removesuffix(".tar.gz").split("-")
    with tarfile.open(path, "r:gz") as archive:
        members = archive.getmembers()
        if (len(members) != 2 or {item.name for item in members} != {f"maw-{language}", "RELEASE.json"}
                or any(not item.isfile() for item in members)):
            raise RuntimeError(f"unsafe/unexpected archive members: {path.name}")
        executable = archive.getmember(f"maw-{language}")
        metadata = archive.getmember("RELEASE.json")
        if not 32 <= executable.size <= 512 * 1024 * 1024 or executable.mode != 0o755 or metadata.size > 16384:
            raise RuntimeError(f"invalid archive contents: {path.name}")
        with archive.extractfile(metadata) as stream:
            manifest = json.load(stream)
        expected = dict(tag=plan["tag"], commit=plan["commit"], language=language, os=system, arch=arch)
        if any(manifest.get(key) != value for key, value in expected.items()):
            raise RuntimeError(f"archive manifest mismatch: {path.name}")
        with archive.extractfile(executable) as stream:
            header = stream.read(32)
            digest = hashlib.sha256(header)
            while chunk := stream.read(1024 * 1024):
                digest.update(chunk)
        if system == "linux":
            valid = (header[:7] == b"\x7fELF\x02\x01\x01"
                and int.from_bytes(header[16:18], "little") in (2, 3)
                and int.from_bytes(header[18:20], "little") == {"amd64": 62, "arm64": 183}[arch])
        else:
            valid = (header[:4] == b"\xcf\xfa\xed\xfe"
                and int.from_bytes(header[4:8], "little") == {"amd64": 0x01000007, "arm64": 0x0100000C}[arch]
                and int.from_bytes(header[12:16], "little") == 2)
        if not valid:
            raise RuntimeError(f"binary format/architecture mismatch: {path.name}")
        if manifest.get("sha256") != digest.hexdigest():
            raise RuntimeError(f"binary digest mismatch: {path.name}")


def ensure_tag(tag, commit):
    refs = api(f"repos/{REPO}/git/matching-refs/tags/{encoded(tag)}")
    matching = [ref for ref in refs if ref["ref"] == f"refs/tags/{tag}"]
    if matching:
        obj = matching[0]["object"]
        # Accept an existing annotation only if its target is this exact commit.
        if obj["type"] == "tag":
            obj = api(f"repos/{REPO}/git/tags/{obj['sha']}")["object"]
        if obj["type"] != "commit" or obj["sha"] != commit:
            raise RuntimeError(f"immutable tag mismatch: {tag}")
        return
    api(f"repos/{REPO}/git/refs", "--method", "POST", "-f", f"ref=refs/tags/{tag}", "-f", f"sha={commit}")


def releases():
    pages = api(f"repos/{REPO}/releases?per_page=100", "--paginate", "--slurp")
    return [release for page in pages for release in page]


def existing_assets(release_id):
    pages = api(f"repos/{REPO}/releases/{release_id}/assets?per_page=100", "--paginate", "--slurp")
    return [asset for page in pages for asset in page]


def verify_asset(asset, path):
    if asset["size"] != path.stat().st_size:
        raise RuntimeError(f"immutable asset size mismatch: {path.name}")
    expected = hashlib.sha256(path.read_bytes()).hexdigest()
    # GitHub emits SHA256 digests for modern uploads. Download if absent.
    digest = asset.get("digest")
    if not digest:
        payload = subprocess.check_output(["gh", "api", f"repos/{REPO}/releases/assets/{asset['id']}",
            "-H", "Accept: application/octet-stream"], cwd=ROOT)
        digest = "sha256:" + hashlib.sha256(payload).hexdigest()
    if digest != "sha256:" + expected:
        raise RuntimeError(f"immutable asset digest mismatch: {path.name}")


def publish(plan_path, directory):
    plan = json.loads(plan_path.read_text())
    fresh = prepare(plan["ci_run"])
    if fresh["skip"]:
        return fresh
    if plan != fresh:
        raise RuntimeError("release plan differs from canonical CI evidence")
    if not directory.is_dir() or directory.is_symlink():
        raise RuntimeError("assets must be a real directory")
    allowed = set(plan["archives"]) | {"SHA256SUMS", "release.json"}
    if any(path.name not in allowed or not path.is_file() or path.is_symlink() for path in directory.iterdir()):
        raise RuntimeError("unexpected file/directory in assets")
    for name in plan["archives"]:
        archive_check(directory / name, plan)
    manifest = directory / "release.json"
    manifest.write_bytes(canonical(plan))
    content = sorted([*plan["archives"], "release.json"])
    checksums = "".join(f"{hashlib.sha256((directory / name).read_bytes()).hexdigest()}  {name}\n" for name in content)
    (directory / "SHA256SUMS").write_text(checksums)
    paths = {name: directory / name for name in sorted(allowed)}
    # Recheck immediately before the first remote mutation; never retarget stale work.
    if api(f"repos/{REPO}/branches/alpha")["commit"]["sha"] != plan["commit"]:
        return dict(skip=True, reason="alpha advanced before publication")
    ensure_tag(plan["tag"], plan["commit"])
    ensure_tag(plan["go_tag"], plan["commit"])
    matching = [release for release in releases() if release["tag_name"] == plan["tag"]]
    if len(matching) > 1:
        raise RuntimeError("duplicate release tag")
    if matching:
        release = matching[0]
        if release["target_commitish"] != plan["commit"] or not release["prerelease"]:
            raise RuntimeError("existing release metadata mismatch")
    else:
        notes = api(f"repos/{REPO}/releases/generate-notes", "--method", "POST", "-f", f"tag_name={plan['tag']}", "-f", f"target_commitish={plan['commit']}")
        release = api(f"repos/{REPO}/releases", "--method", "POST", "-f", f"tag_name={plan['tag']}",
            "-f", f"target_commitish={plan['commit']}", "-f", f"name={plan['tag']}", "-f", f"body={notes['body']}",
            "-F", "draft=true", "-F", "prerelease=true", "-f", "make_latest=false")
    assets = existing_assets(release["id"])
    if len({asset["name"] for asset in assets}) != len(assets) or any(asset["name"] not in paths for asset in assets):
        raise RuntimeError("unexpected existing release assets")
    by_name = {asset["name"]: asset for asset in assets}
    for name, path in paths.items():
        if name in by_name:
            verify_asset(by_name[name], path)
        elif not release["draft"]:
            raise RuntimeError("published release is incomplete; refusing mutation")
        else:
            subprocess.run(["gh", "release", "upload", plan["tag"], str(path), "--repo", REPO], cwd=ROOT, check=True, stdout=sys.stderr)
    final = existing_assets(release["id"])
    if len(final) != len(paths) or {asset["name"] for asset in final} != set(paths):
        raise RuntimeError("release asset set incomplete")
    for asset in final:
        verify_asset(asset, paths[asset["name"]])
    if release["draft"]:
        # Stale in-flight uploads remain an unpublished draft, never a newer alias.
        if api(f"repos/{REPO}/branches/alpha")["commit"]["sha"] != plan["commit"]:
            return dict(skip=True, reason="alpha advanced; verified assets remain draft")
        release = api(f"repos/{REPO}/releases/{release['id']}", "--method", "PATCH",
            "-F", "draft=false", "-F", "prerelease=true", "-f", "make_latest=false")
    return dict(skip=False, tag=plan["tag"], commit=plan["commit"], url=release["html_url"], assets=len(paths))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command")
    prepare_parser = commands.add_parser("prepare", help="derive immutable plan from a successful canonical CI run")
    prepare_parser.add_argument("--ci-run", required=True)
    prepare_parser.add_argument("--output", type=Path, required=True)
    publish_parser = commands.add_parser("publish", help="publish verified CI archives as an alpha prerelease")
    publish_parser.add_argument("--plan", type=Path, required=True)
    publish_parser.add_argument("--assets", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "prepare":
        result = prepare(args.ci_run)
        args.output.write_bytes(canonical(result))
    elif args.command == "publish":
        result = publish(args.plan, args.assets)
    else:
        result = dict(mode="preview", tag=calculator(), commit=run("git", "rev-parse", "HEAD"),
            calculator=f"{UPSTREAM}@{SNAPSHOT}", warning="read-only preview; successful alpha CI publishes date-time tags")
    print(canonical(result).decode(), end="")


if __name__ == "__main__":
    main()
