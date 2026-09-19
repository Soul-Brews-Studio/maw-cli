#!/usr/bin/env python3
"""Preview a source-only CalVer release; publishing requires an explicit tag gate."""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
REPO = "Soul-Brews-Studio/maw-herdr"
UPSTREAM = "Soul-Brews-Studio/arra-oracle-skills-cli"
SNAPSHOT = "68110ad0641f5b7bc8a14a988971ff4ead9ad77a"
SHA256 = "5adcacb27c87282ee05960e61a88a9575af9c01ae195111395784fb0c8870c47"


def run(*args):
    return subprocess.check_output(args, cwd=ROOT, text=True).strip()


def api(endpoint, *args):
    return json.loads(run("gh", "api", endpoint, *args))


def preview():
    # Reuse the reviewed upstream pure calculator, never its main()/--apply:
    # upstream --check can repair package.json, so even that entrypoint is unsafe.
    source = api(f"repos/{UPSTREAM}/contents/scripts/calver.ts?ref={SNAPSHOT}")
    data = base64.b64decode(source["content"])
    if hashlib.sha256(data).hexdigest() != SHA256:
        raise RuntimeError("upstream CalVer digest mismatch")
    with tempfile.TemporaryDirectory(prefix="maw-calver-") as temporary:
        calculator = Path(temporary) / "calver.ts"
        calculator.write_bytes(data)
        wrapper = Path(temporary) / "preview.ts"
        wrapper.write_text('import { computeVersion } from "./calver.ts";\n'
                           'console.log("v" + computeVersion({stable:false,channel:"alpha",check:true}));\n')
        tag = subprocess.check_output(["bun", str(wrapper)], cwd=ROOT,
            env=dict(os.environ, TZ="Asia/Bangkok"), text=True).strip()
    if not re.fullmatch(r"v[0-9]+\.[0-9]+\.[0-9]+-alpha\.[0-9]+", tag):
        raise RuntimeError("unexpected upstream CalVer output")
    return tag


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--publish", action="store_true", help="create source tag/release only after explicit user approval")
    parser.add_argument("--approve", metavar="TAG", help="explicitly approved tag; required with --publish")
    parser.add_argument("--commit", help="exact approved alpha commit; required with --publish")
    args = parser.parse_args()
    if bool(args.approve or args.commit) != args.publish or (args.publish and not (args.approve and args.commit)):
        parser.error("publish requires both --approve TAG and --commit SHA; otherwise use read-only preview")
    commit = run("git", "rev-parse", "HEAD")
    tag = args.approve if args.publish else preview()
    if not re.fullmatch(r"v[0-9]+\.[0-9]+\.[0-9]+-alpha\.[0-9]+", tag):
        parser.error("expected an explicitly previewed alpha CalVer tag")
    if args.publish:
        if args.commit != commit or run("git", "branch", "--show-current") != "alpha":
            raise RuntimeError("publish requires checkout of the exact approved alpha commit")
        if run("git", "status", "--porcelain", "--untracked-files=no"):
            raise RuntimeError("tracked changes present; merge the release source before publishing")
        remote = api(f"repos/{REPO}/branches/alpha")["commit"]["sha"]
        if remote != commit:
            raise RuntimeError("local and remote alpha must match approved commit")
        checks = api(f"repos/{REPO}/commits/{commit}/check-runs?per_page=100")
        names = {check["name"] for check in checks["check_runs"] if check["conclusion"] == "success"}
        expected = {f"smoke ({system}, {language})" for system in ("ubuntu-latest", "macos-latest") for language in ("go", "rs", "js", "zig")}
        if checks["total_count"] > 100 or not expected.issubset(names) or any(check["status"] != "completed" or check["conclusion"] not in ("success", "skipped", "neutral") for check in checks["check_runs"]):
            raise RuntimeError("all eight compile/smoke checks must pass before publication")
    # Query the same canonical repository used by all publication gates. API
    # failures propagate; never treat authentication/network errors as absence.
    if any(ref["ref"] == f"refs/tags/{tag}" for ref in api(f"repos/{REPO}/git/matching-refs/tags/{tag}")):
        raise RuntimeError("tag already exists; preview a new minute slot")
    notes = api(f"repos/{REPO}/releases/generate-notes", "--method", "POST", "-f", f"tag_name={tag}", "-f", f"target_commitish={commit}")
    result = dict(mode="publish" if args.publish else "preview", tag=tag, commit=commit,
                  calculator=f"{UPSTREAM}@{SNAPSHOT}", notes=notes["body"],
                  assets=[], warning="repository CalVer tags; use Go @alpha or @commit, not semantic module tags")
    if not args.publish:
        print(json.dumps(result, indent=2))
        return
    # Nothing below this gate is reached by the default preview.
    annotation = api(f"repos/{REPO}/git/tags", "--method", "POST", "-f", f"tag={tag}", "-f", f"message={tag}", "-f", f"object={commit}", "-f", "type=commit")
    api(f"repos/{REPO}/git/refs", "--method", "POST", "-f", f"ref=refs/tags/{tag}", "-f", f"sha={annotation['sha']}")
    with tempfile.TemporaryDirectory(prefix="maw-release-notes-") as temporary:
        path = Path(temporary) / "notes.md"
        path.write_text(notes["body"] + "\n")
        subprocess.run(["gh", "release", "create", tag, "--repo", REPO, "--verify-tag", "--prerelease", "--title", tag, "--notes-file", str(path)], cwd=ROOT, check=True)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
