#!/usr/bin/env python3
"""Go self-update process smoke: isolated TLS releases, copied binaries, no GitHub.

Requires Go and openssl for fixture setup only. A Go source overlay changes the
release origins and trusts the fixture CA; shipped source has no test URL switch.
"""
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
import json
import os
from pathlib import Path
import re
import shutil
import ssl
import subprocess
import tarfile
import tempfile
import threading

repo = Path(__file__).resolve().parents[2]
go = shutil.which("go")
openssl = shutil.which("openssl")
assert go and openssl, "Go and openssl are required for self-update smoke setup"
old_tag, tag = "v26.1.1-alpha.1", "v26.1.2-alpha.2"
commit = "a" * 40


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
        assert system in ("linux", "darwin") and arch in ("amd64", "arm64")
        archive_name = f"maw-go-{system}-{arch}.tar.gz"
        binaries = {}
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

        env = {k: v for k, v in os.environ.items()
               if not k.startswith(("MAW_", "XDG_")) and k.upper() not in
               ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "NO_PROXY")}
        env.update(HOME=str(home), USERPROFILE=str(home), PATH="",
                   MAW_PLUGINS_DIR=str(home / "plugins"), MAW_CONFIG_DIR=str(home / "config"),
                   SSL_CERT_FILE=str(certificate))
        install = root / "install"
        install.mkdir()
        executable = install / "maw-go"
        alias = install / "maw"
        alias.symlink_to("maw-go")
        passed = 0

        def reset(binary="old"):
            executable.write_bytes(binaries[binary])
            executable.chmod(0o755)
            requests.clear()

        def run(*args, success=True, through_alias=False):
            result = subprocess.run([str(alias if through_alias else executable), *args],
                                    cwd=home, env=env, text=True, capture_output=True, timeout=30)
            assert (result.returncode == 0) == success, (args, result.returncode,
                                                        result.stdout, result.stderr)
            assert not list(home.iterdir()), "updater mutated HOME/plugin configuration"
            assert set(p.name for p in install.iterdir()) == {"maw-go", "maw"}, "staging leaked"
            assert alias.is_symlink(), "updater replaced the alias instead of its target"
            return result.stdout + result.stderr

        def release(fault=None):
            responses.clear()
            binary = binaries["old" if fault == "candidate-version" else
                              "noisy" if fault == "candidate-noisy" else "new"]
            metadata = dict(tag=tag, commit=commit, language="go", os=system,
                            arch=arch, sha256=digest(binary))
            if fault == "metadata":
                metadata["commit"] = "b" * 40
            if fault == "binary-hash":
                metadata["sha256"] = "0" * 64
            members = [("maw-go", binary, 0o755),
                       ("RELEASE.json", json.dumps(metadata).encode(), 0o644)]
            if fault == "extra-member":
                members.append(("../escape", b"do not write", 0o644))
            if fault == "duplicate-member":
                members.append(members[0])
            buffer = io.BytesIO()
            with tarfile.open(fileobj=buffer, mode="w:gz", format=tarfile.USTAR_FORMAT) as archive:
                for name, data, mode in members:
                    member = tarfile.TarInfo(name)
                    member.size, member.mode = len(data), mode
                    if fault == "symlink-member" and name == "maw-go":
                        member.type, member.linkname, member.size = tarfile.SYMTYPE, "../escape", 0
                        archive.addfile(member)
                    else:
                        archive.addfile(member, io.BytesIO(data))
            archives = [f"maw-{language}-{platform}-{cpu}.tar.gz"
                        for language in ("go", "rs", "js", "zig")
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
        for fault in ("archive-hash", "metadata", "binary-hash", "extra-member",
                      "candidate-version", "candidate-noisy", "fetch", "gzip-footer",
                      "duplicate-member", "symlink-member"):
            reset()
            release(fault)
            output = run("update", "--version", tag, success=False)
            if fault == "candidate-noisy":
                assert "candidate version output too large" in output, output
            assert any(path.endswith("/" + archive_name) for path in requests), (fault, requests)
            assert executable.read_bytes() == binaries["old"], f"{fault} replaced executable"
            assert not (root / "escape").exists()
            passed += 1
        for binary in ("new", "future"):
            reset(binary)
            release()
            run("update")
            assert executable.read_bytes() == binaries[binary], "default update downgraded or rewrote current version"
            assert not any(path.endswith(".tar.gz") for path in requests)
            passed += 1
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
        run("update")
        assert executable.read_bytes() == binaries["new"]
        passed += 1
        print(f"self-update smoke: {passed} process scenarios passed (local TLS, empty PATH)")
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
