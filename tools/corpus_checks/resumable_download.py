"""Independent byte-range peer and interruption oracle for complete native downloads."""

import contextlib
import hashlib
import http.server
import json
import re
import shutil
import threading
from collections.abc import Iterator
from pathlib import Path

from .common import Application


@contextlib.contextmanager
def range_api(body: bytes) -> Iterator[tuple[str, dict, list]]:
    control = {"body": body, "etag": '"fixture-v1"', "mode": "normal"}
    calls = []
    errors = []

    class Handler(http.server.BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def do_GET(self) -> None:
            match = re.fullmatch(r"bytes=(\d+)-(\d+)", self.headers.get("Range", ""))
            if not match or self.headers.get("Accept-Encoding") != "identity":
                errors.append("missing range or identity encoding")
                self.close_connection = True
                return
            start, requested_end = map(int, match.groups())
            calls.append((start, requested_end, self.headers.get("If-Range")))
            content = control["body"]
            total = len(content)
            end = min(requested_end, total - 1)
            data = content[start : end + 1]
            mode = control["mode"]
            status = 206 if total else 416
            etag = control["etag"]
            content_range = f"bytes {start}-{end}/{total}" if total else "bytes */0"
            if self.headers.get("If-Range") not in (None, etag) or mode == "ignored":
                status, data = 200, content
            if mode == "etag":
                etag = '"fixture-v2"'
            elif mode == "weak":
                etag = 'W/"fixture-v1"'
            elif mode == "length":
                content_range = f"bytes {start}-{end}/{total + 1}"
            elif mode == "start":
                content_range = f"bytes {start + 1}-{end}/{total}"
            elif mode == "end":
                content_range = f"bytes {start}-{requested_end + 1}/{total}"
            elif mode == "invalid-range":
                content_range = "bytes */unknown"
            elif mode == "redirect":
                status = 302
            elif mode == "disconnect":
                self.close_connection = True
                return
            self.send_response(status)
            self.send_header("Content-Range", content_range)
            if mode != "missing-etag":
                self.send_header("ETag", etag)
            if mode == "encoding":
                self.send_header("Content-Encoding", "gzip")
            if mode == "redirect":
                self.send_header("Location", "/must-not-follow")
            if mode == "chunked":
                self.send_header("Transfer-Encoding", "chunked")
            elif mode not in ("overlong", "short"):
                self.send_header("Content-Length", str(len(data) + (1 if mode == "bad-length" else 0)))
            self.end_headers()
            if mode in ("truncated", "short"):
                data = data[:-1]
            elif mode == "overlong":
                data += b"!"
            with contextlib.suppress(OSError):
                if mode == "chunked":
                    for offset in range(0, len(data), 8191):
                        chunk = data[offset : offset + 8191]
                        self.wfile.write(f"{len(chunk):x}\r\n".encode() + chunk + b"\r\n")
                    self.wfile.write(b"0\r\n\r\n")
                else:
                    self.wfile.write(data)
            return

        def log_message(self, *args: object) -> None:
            return

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/artifact.bin", control, calls
        assert errors == [], errors
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)
    return


def check(application: Application, directory: Path) -> dict:
    body = bytes(range(256)) * 1024 + "attachment Привет 世界\x00".encode()
    digest = hashlib.sha256(body).hexdigest()
    chunk_size = 131072
    observations = {}
    with range_api(body) as (url, control, calls):

        def setup(name: str, patch: dict | None = None) -> tuple[Path, Path, dict]:
            root = directory / name
            root.mkdir()
            output = root / "attachment.bin"
            policy = {
                "url": url,
                "target": str(output),
                "sha256": digest,
                "chunk_size": chunk_size,
                "max_bytes": len(body),
                "timeout_ms": 2000,
                **(patch or {}),
            }
            (root / "download.json").write_text(json.dumps(policy))
            return root, output, policy

        def run(root: Path, code: int = 0, **settings: str) -> dict:
            result = application.run(root, {"DOWNLOAD_STEPS": "100", **settings})
            assert result.returncode == code, result.stderr + result.stdout
            if code == 75:
                return {}
            report = json.loads((root / "attachment.bin.report.json").read_text())
            assert json.loads(result.stdout) == {key: report[key] for key in ["phase", "offset", "total"]}
            assert bool(report["error"]) == (code != 0), report
            return report

        def state(output: Path) -> Path:
            return Path(str(output) + ".download.json")

        def part(output: Path) -> Path:
            return Path(str(output) + ".part")

        def complete(root: Path, output: Path) -> None:
            final = run(root)
            assert final["phase"] == "published" and final["offset"] == final["total"] == len(control["body"])
            assert output.read_bytes() == control["body"] and not part(output).exists()
            assert final["sha256"] == hashlib.sha256(control["body"]).hexdigest()
            return  # noqa: PLR1711 - explicit return required by repository guidelines

        root, output, policy = setup("resume")
        first = run(root, DOWNLOAD_STEPS="1")
        assert first["phase"] == "downloading" and first["offset"] == chunk_size and not output.exists()
        assert part(output).read_bytes() == body[:chunk_size]
        assert calls == [(0, chunk_size - 1, None)]
        # A synced but uncommitted tail must be discarded before requesting the checkpoint offset.
        with part(output).open("ab") as stream:
            stream.write(b"uncommitted tail")
        complete(root, output)
        assert calls[1:] == [
            (chunk_size, 2 * chunk_size - 1, '"fixture-v1"'),
            (2 * chunk_size, len(body) - 1, '"fixture-v1"'),
        ]
        checkpoint = state(output).read_bytes()
        before_calls = len(calls)
        complete(root, output)
        assert len(calls) == before_calls and state(output).read_bytes() == checkpoint
        observations["resume"] = {"bytes": len(body), "sha256": digest, "ranges": len(calls)}

        crash_results = {}
        for boundary in ["mid_body", "after_write", "after_checkpoint", "before_publish", "after_publish"]:
            root, output, _ = setup(boundary)
            run(root, code=75, DOWNLOAD_STOP=boundary)
            saved = json.loads(state(output).read_text())
            expected_offset = 0 if boundary in ("mid_body", "after_write") else chunk_size
            if boundary in ("before_publish", "after_publish"):
                expected_offset = len(body)
                assert saved["phase"] == "ready"
            assert saved["offset"] == expected_offset
            assert output.exists() == (boundary == "after_publish")
            if boundary == "mid_body":
                assert part(output).stat().st_size == 65536
            if boundary == "after_write":
                assert part(output).stat().st_size == chunk_size
            if boundary == "after_publish":
                assert output.samefile(part(output))
            before_calls = len(calls)
            complete(root, output)
            resumed_ranges = [item[0] for item in calls[before_calls:]]
            expected_ranges = [0, chunk_size, 2 * chunk_size] if expected_offset == 0 else [chunk_size, 2 * chunk_size]
            if expected_offset == len(body):
                expected_ranges = []
            assert resumed_ranges == expected_ranges
            crash_results[boundary] = resumed_ranges
        observations["interruptions"] = crash_results

        modes = [
            "etag",
            "weak",
            "missing-etag",
            "length",
            "start",
            "end",
            "invalid-range",
            "ignored",
            "redirect",
            "disconnect",
            "encoding",
            "bad-length",
            "truncated",
            "short",
            "overlong",
        ]
        for mode in modes:
            root, output, _ = setup(mode)
            run(root, DOWNLOAD_STEPS="1")
            saved = state(output).read_bytes()
            control["mode"] = mode
            rejected = run(root, code=1)
            assert rejected["offset"] == chunk_size and state(output).read_bytes() == saved
            assert not output.exists() and part(output).read_bytes()[:chunk_size] == body[:chunk_size]
            control["mode"] = "normal"
            complete(root, output)
        observations["rejected_responses"] = modes

        root, output, _ = setup("if-range-mismatch")
        run(root, DOWNLOAD_STEPS="1")
        saved = state(output).read_bytes()
        control["etag"] = '"new-version"'
        run(root, code=1)
        assert state(output).read_bytes() == saved and not output.exists()
        control["etag"] = '"fixture-v1"'
        complete(root, output)

        for damage in ["prefix", "truncated", "missing"]:
            root, output, _ = setup("damage-" + damage)
            run(root, DOWNLOAD_STEPS="1")
            saved = state(output).read_bytes()
            damaged = b"x" + body[1:chunk_size] + b"keep this tail"
            if damage == "prefix":
                part(output).write_bytes(damaged)
            elif damage == "truncated":
                damaged = body[:100]
                part(output).write_bytes(damaged)
            else:
                part(output).unlink()
            before_calls = len(calls)
            run(root, code=1)
            assert len(calls) == before_calls and state(output).read_bytes() == saved and not output.exists()
            if damage != "missing":
                assert part(output).read_bytes() == damaged
            else:
                assert not part(output).exists()
        observations["corrupt_prefixes"] = ["prefix", "truncated", "missing"]

        root, output, _ = setup("digest-mismatch", {"sha256": "0" * 64})
        report = run(root, code=1)
        assert report["offset"] == len(body) and report["phase"] == "downloading" and not output.exists()
        before_calls = len(calls)
        run(root, code=1)
        assert len(calls) == before_calls and part(output).read_bytes() == body
        root, output, _ = setup("size-limit", {"max_bytes": len(body) - 1})
        assert run(root, code=1)["offset"] == 0 and part(output).read_bytes() == b""

        control["mode"] = "chunked"
        root, output, _ = setup("chunked")
        complete(root, output)
        control["mode"] = "normal"
        control["body"] = b""
        root, output, _ = setup("empty", {"sha256": hashlib.sha256(b"").hexdigest(), "max_bytes": 0})
        complete(root, output)
        control["body"] = body
        observations["empty_chunked_digest_and_size"] = "passed"

        for conflict in ["destination", "orphan", "symlink", "broken-symlink", "report-hardlink", "config-target"]:
            root, output, policy = setup("conflict-" + conflict)
            protected = root / "protected"
            protected.write_bytes(b"keep me")
            if conflict == "destination":
                output.write_bytes(b"existing")
            elif conflict == "orphan":
                part(output).write_bytes(b"orphan")
            elif conflict in ("symlink", "broken-symlink"):
                part(output).symlink_to(protected if conflict == "symlink" else root / "missing")
            elif conflict == "report-hardlink":
                Path(str(output) + ".report.json").hardlink_to(root / "download.json")
            else:
                policy["target"] = str(root / "download.json")
                (root / "download.json").write_text(json.dumps(policy))
            before = {path.name: path.read_bytes() for path in root.iterdir() if path.is_file()}
            before_calls = len(calls)
            assert application.run(root, {}).returncode != 0
            assert len(calls) == before_calls and protected.read_bytes() == b"keep me"
            assert {path.name: path.read_bytes() for path in root.iterdir() if path.is_file()} == before
        observations["path_conflicts"] = 6

        for changed in [
            {"chunk_size": 0},
            {"max_bytes": True},
            {"url": "http://user@localhost/file"},
            {"url": "http://localhost:65536/file"},
            {"url": url + "%bad%escape"},
            {"sha256": "invalid"},
            {"target": "directory/"},
            {"extra": 1},
        ]:
            root, output, _ = setup("invalid-" + str(len(list(directory.iterdir()))), changed)
            before_calls = len(calls)
            assert application.run(root, {}).returncode != 0
            assert not state(output).exists() and not part(output).exists() and len(calls) == before_calls

        root, output, policy = setup("corrupt-checkpoint")
        run(root, DOWNLOAD_STEPS="1")
        saved = json.loads(state(output).read_text())
        for change in [
            {"offset": -1},
            {"offset": len(body) + 1},
            {"total": -2},
            {"etag": 'W/"weak"'},
            {"phase": "ready"},
            {"version": 2},
            {"extra": True},
            {"policy": {}},
            {"prefix": "bad"},
        ]:
            state(output).write_text(json.dumps({**saved, **change}, sort_keys=True))
            before = state(output).read_bytes()
            before_calls = len(calls)
            assert application.run(root, {}).returncode != 0
            assert state(output).read_bytes() == before and part(output).read_bytes() == body[:chunk_size]
            assert len(calls) == before_calls and not output.exists()
        observations["invalid_policy_and_checkpoint"] = {"policies": 8, "checkpoints": 9}
        # The process address-space limit is lower than the artifact size. A
        # whole-file buffering implementation cannot pass this Linux check.
        limiter = shutil.which("prlimit")
        assert limiter is not None, "Linux prlimit is required for the bounded-memory check"
        control["body"] = bytes(range(256)) * (192 * 1024 * 1024 // 256)
        large_digest = hashlib.sha256(control["body"]).hexdigest()
        root, output, _ = setup(
            "bounded-memory",
            {
                "sha256": large_digest,
                "max_bytes": len(control["body"]),
                "chunk_size": 16 * 1024 * 1024,
            },
        )
        limited = Application([limiter, "--as=134217728", "--", *application.command], application.engine)
        result = limited.run(root, {"DOWNLOAD_STEPS": "100"}, timeout=60)
        assert result.returncode == 0, result.stderr + result.stdout
        assert output.stat().st_size == len(control["body"]) and not part(output).exists()
        with output.open("rb") as stream:
            actual = hashlib.file_digest(stream, "sha256").hexdigest()
        assert actual == large_digest
        observations["bounded_memory"] = {
            "file_bytes": len(control["body"]),
            "address_space_bytes": 134217728,
            "sha256": large_digest,
        }
        control["body"] = body
    return observations
