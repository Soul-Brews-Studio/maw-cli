#!/usr/bin/env python3
"""Self-update process smoke: isolated TLS releases, copied binaries, no GitHub.

    update-smoke.py                  maw-go, built with a Go source overlay
    update-smoke.py -- BUN ENTRY     maw-js, compiled by BUN from an overlay copy
                                     of src/js/src, plus source-checkout updates
                                     in a throwaway bare origin + clone; ENTRY is
                                     the source-run CLI under smoke, given only
                                     side-effect-free usage errors

Requires openssl plus Go or Bun for fixture setup only. The overlay changes the
release origins and trusts the fixture CA; shipped source has no test URL switch.
The updater only ever replaces a copied executable, or fast-forwards a clone,
inside the temporary tree; the real ENTRY never reaches git or the network.
"""
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import ssl
import subprocess
import sys
import tarfile
import tempfile
import threading

repo = Path(__file__).resolve().parents[2]
arguments = sys.argv[1:]
if arguments[:1] == ["--"]:
    arguments = arguments[1:]
language = "js" if arguments else "go"
assert language == "go" or len(arguments) == 2, "usage: update-smoke.py [-- BUN ENTRY]"
go = shutil.which("go") if language == "go" else None
bun = shutil.which(arguments[0]) if language == "js" else None
entry = Path(arguments[1]).resolve() if language == "js" else None
openssl = shutil.which("openssl")
git = shutil.which("git")
assert openssl and (go or bun), f"openssl and {'Go' if language == 'go' else 'Bun'} are required for self-update smoke setup"
assert language == "go" or git, "Git is required for the js source-checkout cases"
program = f"maw-{language}"
old_tag, tag = "v26.1.1-alpha.1", "v26.1.2-alpha.2"
commit = "a" * 40
# Every failure message the ports share with Go, keyed by fixture fault.
refusals = {
    "archive-hash": "archive checksum mismatch; original executable unchanged",
    "metadata": "archive metadata/binary checksum mismatch",
    "binary-hash": "archive metadata/binary checksum mismatch",
    "extra-member": "unsafe or unexpected archive member",
    "unknown-member": "unsafe or unexpected archive member",
    "directory-member": "unsafe or unexpected archive member",
    "duplicate-member": "unsafe or unexpected archive member",
    "symlink-member": "unsafe or unexpected archive member",
    "candidate-version": "candidate version mismatch; original executable unchanged",
    "candidate-noisy": "candidate version output too large",
    "fetch": "HTTP 404",
    "gzip-footer": "",
}


def digest(data):
    return hashlib.sha256(data).hexdigest()


with tempfile.TemporaryDirectory(prefix="maw-update-") as temporary:
    root = Path(temporary).resolve()
    home = root / "home"
    home.mkdir()
    certificate, key = root / "cert.pem", root / "key.pem"
    config = root / "openssl.cnf"
    config.write_text("[req]\ndistinguished_name=dn\nx509_extensions=ext\nprompt=no\n"
                      "[dn]\nCN=maw-update-smoke\n[ext]\n"
                      "subjectAltName=IP:127.0.0.1\nbasicConstraints=critical,CA:TRUE\n")
    subprocess.run([openssl, "req", "-x509", "-newkey", "rsa:2048", "-nodes",
                    "-keyout", str(key), "-out", str(certificate), "-days", "1",
                    "-config", str(config)], check=True, capture_output=True)
    responses = {}
    requests = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            requests.append(self.path)
            data = responses.get(self.path)
            self.send_response(200 if data is not None else 404)
            data = data if data is not None else b"fixture not found"
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, *_args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    tls = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    tls.load_cert_chain(certificate, key)
    server.socket = tls.wrap_socket(server.socket, server_side=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        origin = f"https://127.0.0.1:{server.server_port}"
        binaries = {}
        if language == "go":
            release_path = repo / "src/go/internal/commands/update/release.go"
            source = release_path.read_text()
            for name, expected in (("apiOrigin", "https://api.github.com"),
                                   ("downloadOrigin", "https://github.com")):
                source, count = re.subn(rf'({name}\s*=\s*)"{re.escape(expected)}"',
                                        rf'\g<1>"{origin}"', source)
                assert count == 1, f"expected one production {name} constant"
            mapped = root / "release.go"
            mapped.write_text(source)
            # Trust only our generated fixture certificate, independent of macOS's
            # system verifier. This extra file exists solely in the build overlay.
            roots = root / "fixture_tls.go"
            roots.write_text('package update\nimport ("crypto/tls"; "crypto/x509"; "net/http")\n'
                             'func init() { roots := x509.NewCertPool(); '
                             f'if !roots.AppendCertsFromPEM([]byte({json.dumps(certificate.read_text())})) '
                             '{ panic("bad fixture certificate") }; '
                             'transport := http.DefaultTransport.(*http.Transport).Clone(); '
                             'transport.TLSClientConfig = &tls.Config{RootCAs: roots}; '
                             'http.DefaultTransport = transport }\n')
            overlay = root / "overlay.json"
            overlay.write_text(json.dumps({"Replace": {
                str(release_path): str(mapped),
                str(release_path.parent / "fixture_tls.go"): str(roots),
            }}))
            system, arch = subprocess.check_output(
                [go, "env", "GOOS", "GOARCH"], text=True).split()
            for name, version in (("old", old_tag), ("new", tag), ("dev", "dev"),
                                  ("future", "v26.1.3-alpha.3"),
                                  ("pseudo", "v0.0.0-20260101000000-bbbbbbbbbbbb")):
                path = root / name
                subprocess.run([go, "build", "-overlay", str(overlay), "-ldflags",
                                f"-X main.releaseVersion={version}", "-o", str(path),
                                "./cmd/maw-go"], cwd=repo / "src/go", check=True)
                binaries[name] = path.read_bytes()

            noisy_source = root / "noisy.go"
            noisy_source.write_text('package main\nimport "os"\nfunc main() { '
                                    '_, _ = os.Stdout.Write(make([]byte, 8192)) }\n')
            noisy_binary = root / "noisy"
            subprocess.run([go, "build", "-o", str(noisy_binary), str(noisy_source)], check=True)
            binaries["noisy"] = noisy_binary.read_bytes()
        else:
            # The overlay is a copy of src/js/src committed in a throwaway seed
            # repository, pushed to a bare origin and cloned: the clone is the
            # dev checkout, the seed publishes new commits, and the compiled
            # fixtures come from the same overlay.
            seed, origin_repo, clone = root / "seed", root / "origin.git", root / "clone"
            overlay = seed / "src/js/src"
            shutil.copytree(repo / "src/js/src", overlay)
            origins = overlay / "mod.validReleaseUrl.ts"
            source = origins.read_text()
            for name, expected in (("apiOrigin", "https://api.github.com"),
                                   ("downloadOrigin", "https://github.com")):
                source, count = re.subn(rf'({name}\s*=\s*)"{re.escape(expected)}"',
                                        rf'\g<1>"{origin}"', source)
                assert count == 1, f"expected one production {name} constant"
            origins.write_text(source)
            # Trust only our generated fixture certificate. This file and its
            # import exist solely in the overlay copy.
            (overlay / "fixture_tls.ts").write_text(
                f"const ca = {json.dumps(certificate.read_text())};\n"
                "const original = globalThis.fetch;\n"
                "globalThis.fetch = ((input: any, init?: any) => original(input, { ...init, tls: { ca } })) as typeof fetch;\n")
            cli = overlay / "cli.ts"
            source, count = re.subn(r"^(import \{ run \})", 'import "./fixture_tls";\n\\1',
                                    cli.read_text(), count=1, flags=re.M)
            assert count == 1, "expected the cli.ts run import"
            cli.write_text(source)
            git_env = {k: v for k, v in os.environ.items() if not k.startswith(("GIT_", "MAW_"))}
            git_env.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL="/dev/null", GIT_TERMINAL_PROMPT="0")

            def g(repo, *args, date=None):
                dated = dict(git_env, GIT_AUTHOR_DATE=date, GIT_COMMITTER_DATE=date) if date else git_env
                result = subprocess.run([git, "-c", "core.hooksPath=/dev/null", "-c", "user.name=Smoke",
                                         "-c", "user.email=smoke@example.invalid", "-C", str(repo), *args],
                                        env=dated, text=True, capture_output=True, timeout=15)
                assert result.returncode == 0, (args, result.stderr)
                return result.stdout.strip()

            def publish(name, date):
                # A new commit on origin's alpha; the overlay source is untouched.
                (seed / name).write_text(date + "\n")
                g(seed, "add", name)
                g(seed, "commit", "-qm", name, date=date)
                g(seed, "push", "-q", str(origin_repo), "alpha")
                return g(seed, "rev-parse", "HEAD")

            g(seed, "init", "-q", "--initial-branch=alpha")
            g(seed, "add", "--all")
            g(seed, "commit", "-qm", "fixture", date="2026-01-01T00:00:00+07:00")
            g(root, "clone", "-q", "--bare", str(seed), str(origin_repo))
            g(root, "clone", "-q", str(origin_repo), str(clone))
            system, arch = subprocess.check_output(
                [bun, "-e", "console.log(process.platform, process.arch)"], text=True).split()
            arch = {"x64": "amd64"}.get(arch, arch)
            (root / "noisy.ts").write_text("process.stdout.write(new Uint8Array(8192));\n")
            for name, version in (("old", old_tag), ("new", tag), ("dev", None),
                                  ("future", "v26.1.3-alpha.3"), ("noisy", None)):
                command = [bun, "build", "--compile", str(root / "noisy.ts" if name == "noisy" else cli),
                           "--outfile", str(root / name)]
                if version:
                    command[3:3] = ["--define", f"MAW_VERSION={json.dumps(version)}"]
                subprocess.run(command, cwd=root, check=True, capture_output=True)
                binaries[name] = (root / name).read_bytes()
        assert system in ("linux", "darwin") and arch in ("amd64", "arm64")
        archive_name = f"{program}-{system}-{arch}.tar.gz"

        env = {k: v for k, v in os.environ.items()
               if not k.startswith(("MAW_", "XDG_", "GIT_")) and k.upper() not in
               ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "NO_PROXY")}
        env.update(HOME=str(home), USERPROFILE=str(home), PATH="",
                   MAW_PLUGINS_DIR=str(home / "plugins"), MAW_CONFIG_DIR=str(home / "config"),
                   SSL_CERT_FILE=str(certificate))
        install = root / "install"
        install.mkdir()
        executable = install / program
        alias = install / "maw"
        alias.symlink_to(program)
        passed = 0

        def reset(binary="old"):
            # A fresh inode avoids macOS retaining signing/cache state from a
            # previously executed binary when the next scenario changes bytes.
            fresh = install / "reset-candidate"
            fresh.write_bytes(binaries[binary])
            fresh.chmod(0o755)
            fresh.replace(executable)
            requests.clear()

        def run(*args, success=True, through_alias=False):
            result = subprocess.run([str(alias if through_alias else executable), *args],
                                    cwd=home, env=env, text=True, capture_output=True, timeout=30)
            assert (result.returncode == 0) == success, (args, result.returncode,
                                                        result.stdout, result.stderr)
            assert not list(home.iterdir()), "updater mutated HOME/plugin configuration"
            assert set(p.name for p in install.iterdir()) == {program, "maw"}, "staging leaked"
            assert alias.is_symlink(), "updater replaced the alias instead of its target"
            if language == "js" and not success:
                # js errors end with the command that fixes or narrows them.
                assert result.stderr.splitlines()[-1].startswith("  "), result.stderr
            return result.stdout + result.stderr

        def release(fault=None):
            responses.clear()
            binary = binaries["old" if fault == "candidate-version" else
                              "noisy" if fault == "candidate-noisy" else "new"]
            metadata = dict(tag=tag, commit=commit, language=language, os=system,
                            arch=arch, sha256=digest(binary))
            if fault == "metadata":
                metadata["commit"] = "b" * 40
            if fault == "binary-hash":
                metadata["sha256"] = "0" * 64
            members = [(program, binary, 0o755),
                       ("RELEASE.json", json.dumps(metadata).encode(), 0o644)]
            if fault == "extra-member":
                members.append(("../escape", b"do not write", 0o644))
            if fault == "unknown-member":
                members.append(("README.md", b"not part of a release", 0o644))
            if fault == "duplicate-member":
                members.append(members[0])
            buffer = io.BytesIO()
            with tarfile.open(fileobj=buffer, mode="w:gz", format=tarfile.USTAR_FORMAT) as archive:
                for name, data, mode in members:
                    member = tarfile.TarInfo(name)
                    member.size, member.mode = len(data), mode
                    if fault == "symlink-member" and name == program:
                        member.type, member.linkname, member.size = tarfile.SYMTYPE, "../escape", 0
                        archive.addfile(member)
                    elif fault == "directory-member" and name == program:
                        member.type, member.size = tarfile.DIRTYPE, 0
                        archive.addfile(member)
                    else:
                        archive.addfile(member, io.BytesIO(data))
            archives = [f"maw-{port}-{platform}-{cpu}.tar.gz"
                        for port in ("go", "rs", "js", "zig")
                        for platform in ("linux", "darwin") for cpu in ("amd64", "arm64")]
            plan = dict(schema="maw.release.v1", skip=False, tag=tag,
                        go_version="v0.20260102.2-alpha", go_tag="src/go/v0.20260102.2-alpha",
                        commit=commit, ci_run=1, archives=archives)
            archive_data = buffer.getvalue()
            if fault == "gzip-footer":
                archive_data = archive_data[:-8] + bytes([archive_data[-8] ^ 0xff]) + archive_data[-7:]
            assets = {archive_name: archive_data, "release.json": json.dumps(plan).encode()}
            assets["SHA256SUMS"] = "".join(
                f'{"0" * 64 if fault == "archive-hash" and name == archive_name else digest(data)}  {name}\n'
                for name, data in assets.items()).encode()
            download = f"/Soul-Brews-Studio/maw-cli/releases/download/{tag}"
            listing = dict(tag_name=tag, draft=False, prerelease=True, target_commitish=commit,
                           published_at="2026-01-02T00:00:00Z", assets=[
                               dict(name=name, size=len(assets.get(name, b"unused")), browser_download_url=f"{origin}{download}/{name}")
                               for name in archives + ["release.json", "SHA256SUMS"]])
            api = "/repos/Soul-Brews-Studio/maw-cli/releases"
            responses[api] = json.dumps([listing]).encode()
            responses[api + "?per_page=100"] = responses[api]
            responses[api + "?per_page=30"] = responses[api]
            responses[api + f"/tags/{tag}"] = json.dumps(listing).encode()
            for name, data in assets.items():
                responses[f"{download}/{name}"] = data
            if fault == "fetch":
                responses.pop(f"{download}/{archive_name}")

        for args in (("update", "--version", "../bad"), ("update", "--unknown"),
                     ("update", "unexpected")):
            reset()
            run(*args, success=False)
            assert not requests and executable.read_bytes() == binaries["old"]
            passed += 1
        reset("dev")
        run("update", success=False)
        assert not requests and executable.read_bytes() == binaries["dev"]
        passed += 1
        for binary in ("old", "dev"):
            reset(binary)
            release()
            output = run("update", "--check")
            assert tag in output and requests
            assert executable.read_bytes() == binaries[binary], "--check replaced executable"
            assert not any(path.endswith(".tar.gz") for path in requests), "--check downloaded executable"
            passed += 1
        for fault, refusal in refusals.items():
            reset()
            release(fault)
            output = run("update", "--version", tag, success=False)
            assert refusal in output, (fault, output)
            assert any(path.endswith("/" + archive_name) for path in requests), (fault, requests)
            assert executable.read_bytes() == binaries["old"], f"{fault} replaced executable"
            assert not (root / "escape").exists()
            passed += 1
        for binary, status in (("new", "already up to date"),
                               ("future", "installed version is newer than published release")):
            reset(binary)
            release()
            output = run("update")
            assert f"status\t{status}\n" in output, output
            assert executable.read_bytes() == binaries[binary], "default update downgraded or rewrote current version"
            assert not any(path.endswith(".tar.gz") for path in requests)
            passed += 1
        if language == "go":
            compare_path = f"/repos/Soul-Brews-Studio/maw-cli/compare/{'b' * 12}...{commit}?per_page=1"
            for status in ("ahead", "identical", "behind", "diverged", "api-error", "base-mismatch", "unknown"):
                reset("pseudo")
                release()
                if status != "api-error":
                    responses[compare_path] = json.dumps(dict(
                        status="ahead" if status == "base-mismatch" else status,
                        base_commit=dict(sha=("c" if status == "base-mismatch" else "b") * 40))).encode()
                run("update", success=status not in ("api-error", "base-mismatch", "unknown"))
                assert compare_path in requests, "source install skipped ancestry verification"
                expected = "new" if status in ("ahead", "identical") else "pseudo"
                assert executable.read_bytes() == binaries[expected], (status, "unexpected source update")
                if expected == "pseudo":
                    assert not any(path.endswith(".tar.gz") for path in requests)
                passed += 1
        for through_alias in (False, True):
            reset()
            release()
            run("update", "--version", tag, through_alias=through_alias)
            assert executable.read_bytes() == binaries["new"], "update did not replace executable"
            assert run("version").strip() == f"maw {tag}"
            assert executable.stat().st_mode & 0o777 == 0o755
            passed += 1
        reset()
        release()
        output = run("update")
        assert f"current\t{old_tag}\ntarget\t{tag}\ncommit\t{commit}\nstatus\tupdate available\nupdated\t{executable}\n" == output, output
        assert executable.read_bytes() == binaries["new"]
        passed += 1

        if language == "js":
            # Unknown channel words are usage errors that name the one channel.
            reset()
            output = run("update", "beta", success=False)
            assert 'unknown channel "beta"; only alpha is published' in output and output.endswith("  maw update alpha\n"), output
            assert not requests and executable.read_bytes() == binaries["old"]
            passed += 1
            # `maw update alpha` on a release build is the same as `maw update`.
            reset()
            release()
            output = run("update", "alpha")
            assert output.endswith(f"status\tupdate available\nupdated\t{executable}\n"), output
            assert executable.read_bytes() == binaries["new"]
            passed += 1

            # A dev build from a git checkout fast-forwards that checkout, which is
            # the clone here: the checkout comes from the running source file.
            gitbin = root / "gitbin"
            gitbin.mkdir()
            (gitbin / "git").symlink_to(git)
            source_home = root / "source-home"
            source_home.mkdir()
            source_env = dict(env, HOME=str(source_home), USERPROFILE=str(source_home), PATH=str(gitbin),
                              GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL="/dev/null")
            script = clone / "src/js/src/cli.ts"
            quoted = shlex.quote(str(clone))
            responses.clear()
            requests.clear()

            def source_run(*args, status=0, trap=False):
                # trap: an inherited GIT_DIR must not redirect maw's git to another repository.
                run_env = dict(source_env, GIT_DIR=str(root / "not-a-repo")) if trap else source_env
                result = subprocess.run([bun, str(script), "update", *args], cwd=source_home, env=run_env,
                                        text=True, capture_output=True, timeout=60)
                assert result.returncode == status, (args, result.returncode, result.stdout, result.stderr)
                if status:
                    assert result.stderr.splitlines()[-1].startswith("  "), result.stderr
                assert not requests, "source checkout update reached the release server"
                return result.stdout, result.stderr

            def state():
                return (g(clone, "rev-parse", "HEAD"), g(clone, "rev-parse", "refs/remotes/origin/alpha"),
                        g(clone, "symbolic-ref", "--quiet", "--short", "HEAD"), g(clone, "status", "--porcelain"))

            def running(commit_hash, stamp):
                return f"dev {stamp} ({g(clone, 'rev-parse', '--short', commit_hash)})"

            first = g(clone, "rev-parse", "HEAD")
            stdout, _ = source_run()
            assert stdout == (f"current\t{running(first, 'v26.1.1-alpha.0')}\ntarget\torigin/alpha\n"
                              f"commit\t{first}\nstatus\talready up to date\n"), stdout
            assert state()[0] == first
            passed += 1
            _, stderr = source_run("beta", status=2)
            assert stderr.endswith("  maw update alpha\n") and state()[0] == first, stderr
            passed += 1
            second = publish("second.txt", "2026-01-02T12:34:00+07:00")
            before = state()
            stdout, _ = source_run("--check")
            assert stdout == (f"current\t{running(first, 'v26.1.1-alpha.0')}\ntarget\torigin/alpha\n"
                              f"commit\t{second}\nstatus\tupdate available: behind origin/alpha by 1\n"), stdout
            assert state()[0] == before[0] and state()[2:] == before[2:], "--check changed the checkout"
            passed += 1
            stdout, _ = source_run()
            assert stdout == (f"current\t{running(first, 'v26.1.1-alpha.0')}\ntarget\torigin/alpha\n"
                              f"commit\t{second}\nstatus\tupdate available: behind origin/alpha by 1\n"
                              f"updated\t{running(second, 'v26.1.2-alpha.1234')}\n"), stdout
            assert state()[0] == second and state()[2] == "alpha"
            passed += 1
            third = publish("third.txt", "2026-01-03T09:05:00+07:00")
            scratch = clone / "scratch.txt"
            scratch.write_text("local work\n")
            before = state()
            stdout, stderr = source_run(status=1)
            assert not stdout and "uncommitted changes" in stderr and stderr.endswith(f"  git -C {quoted} status\n"), stderr
            assert state() == before and scratch.read_text() == "local work\n", "dirty tree touched (or fetched)"
            scratch.unlink()
            passed += 1
            g(clone, "switch", "-q", "-c", "feature")
            before = state()
            _, stderr = source_run(status=1)
            assert "feature has no upstream" in stderr and stderr.endswith("  maw update alpha\n"), stderr
            assert state()[0] == before[0] and state()[2:] == before[2:]
            passed += 1
            stdout, _ = source_run("alpha", trap=True)
            assert "status\tswitch feature -> alpha; update available: behind origin/alpha by 1\n" in stdout, stdout
            assert "\nupdated\tdev" in stdout, stdout
            assert state()[:3] == (third, third, "alpha"), "alpha was not switched to and fast-forwarded"
            assert g(clone, "rev-parse", "feature") == second and not (root / "not-a-repo").exists()
            passed += 1
            fourth = publish("fourth.txt", "2026-01-04T18:00:00+07:00")
            (clone / "local.txt").write_text("unpublished\n")
            g(clone, "add", "local.txt")
            g(clone, "commit", "-qm", "local", date="2026-01-04T19:00:00+07:00")
            local = g(clone, "rev-parse", "HEAD")
            stdout, _ = source_run("--check")
            assert f"commit\t{fourth}\nstatus\tdiverged from origin/alpha (1 ahead, 1 behind); fast-forward impossible\n" in stdout, stdout
            _, stderr = source_run(status=1)
            assert stderr.endswith(f"  git -C {quoted} log --oneline --left-right HEAD...@{{upstream}}\n"), stderr
            assert state()[:3] == (local, fourth, "alpha"), "diverged checkout was changed"
            passed += 1
            # The real CLI under smoke gets only usage errors: no git, no network.
            result = subprocess.run([bun, str(entry), "update", "beta"], cwd=source_home, env=source_env,
                                    text=True, capture_output=True, timeout=60)
            assert result.returncode == 2 and result.stderr.endswith("  maw update alpha\n"), result.stderr
            passed += 1
        print(f"self-update smoke ({program}): {passed} process scenarios passed (local TLS, empty PATH)")
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
