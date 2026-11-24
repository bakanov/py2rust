"""Streaming client behavior against a server that waits for proof of incremental reads."""

import contextlib
import http.server
import ssl
import threading
import time
from collections.abc import Iterator
from pathlib import Path

import pytest

from . import test_service_tls
from .test_services import run

tls_files = test_service_tls.tls_files


@contextlib.contextmanager
def endpoint(tls: Path | None = None) -> Iterator[int]:
    release = threading.Event()

    class Handler(http.server.BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def do_GET(self) -> None:
            self.send_response(200)
            self.send_header("X-Stream", "yes")
            if self.path == "/chunked":
                self.send_header("Transfer-Encoding", "chunked")
            else:
                self.send_header("Content-Length", "0" if self.path == "/release" else "8")
            self.end_headers()
            with contextlib.suppress(OSError):
                if self.path == "/release":
                    release.set()
                elif self.path == "/gated":
                    self.wfile.write(b"abcd")
                    self.wfile.flush()
                    if release.wait(3):
                        self.wfile.write(b"efgh")
                elif self.path == "/chunked":
                    self.wfile.write(b"3\r\nabc\r\n5\r\ndefgh\r\n0\r\n\r\n")
                elif self.path == "/truncated":
                    self.wfile.write(b"abc")
                elif self.path == "/slow":
                    for value in b"abcdefgh":
                        self.wfile.write(bytes([value]))
                        self.wfile.flush()
                        time.sleep(0.12)
                else:
                    self.wfile.write(b"abcdefgh")
            return  # noqa: PLR1711 - explicit return required by repository guidelines

        def log_message(self, *args: object) -> None:
            return

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    if tls:
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(tls / "server.crt", tls / "server.key")
        server.socket = context.wrap_socket(server.socket, server_side=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server.server_port
    finally:
        release.set()
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)
    return


@pytest.mark.parametrize("engine", ["python", "rust"])
def test_incremental_reads_limits_lifetimes_and_deadlines(tmp_path: Path, engine: str) -> None:
    with endpoint() as port:
        source = f"""import time
from py2rust.stdlib import HttpReader, web_open, web_read, web_close, web_request
def read_and_close(handle: HttpReader) -> bytes:
    with handle as source:
        return web_read(source, 4)
def run() -> None:
    base: str = "http://127.0.0.1:{port}"
    headers: dict[str, str] = {{}}
    with web_open(base + "/gated", headers, 2500, 8) as source:
        assert source.status == 200 and source.headers["x-stream"] == "yes"
        assert web_read(source, 4) == b"abcd"
        web_request("GET", base + "/release", b"", headers, 1000, 1)
        assert web_read(source, 4) == b"efgh"
        assert web_read(source, 4) == b""
    with web_open(base + "/chunked", headers, 1000, 8) as source:
        content: str = ""
        while True:
            piece: bytes = web_read(source, 2)
            if len(piece) == 0:
                break
            content = content + piece.hex()
        assert content == "6162636465666768"
    failures: int = 0
    for path in ["/truncated", "/regular", "/chunked"]:
        try:
            with web_open(base + path, headers, 1000, 7) as source:
                while len(web_read(source, 2)) > 0:
                    pass
        except Exception:
            failures = failures + 1
    handle: HttpReader = web_open(base + "/regular", headers, 1000, 8)
    assert read_and_close(handle) == b"abcd"
    try:
        web_read(handle, 1)
    except Exception:
        failures = failures + 1
    web_close(handle)
    handle = web_open(base + "/regular", headers, 1000, 8)
    try:
        with handle as source:
            assert False, "close on error"
    except Exception:
        failures = failures + 1
    try:
        web_read(handle, 1)
    except Exception:
        failures = failures + 1
    with web_open(base + "/regular", headers, 1000, 8) as source:
        for count in [0, -1, 33554433]:
            try:
                web_read(source, count)
            except Exception:
                failures = failures + 1
    started: float = time.monotonic()
    try:
        with web_open(base + "/slow", headers, 250, 8) as source:
            while len(web_read(source, 1)) > 0:
                pass
    except Exception:
        failures = failures + 1
    assert time.monotonic() - started < 0.9
    try:
        with web_open(base + "/regular", headers, 100, 8) as source:
            time.sleep(0.2)
            web_read(source, 1)
    except Exception:
        failures = failures + 1
    assert failures == 11
    print("streaming reader passed")
    return
if __name__ == "__main__":
    run()
"""
        result = run(tmp_path, source, engine)
        assert result.returncode == 0, result.stderr
        assert result.stdout == "streaming reader passed\n"
    return  # noqa: PLR1711 - explicit return required by repository guidelines


@pytest.mark.parametrize("engine", ["python", "rust"])
def test_streaming_private_ca(tmp_path: Path, tls_files: Path, engine: str) -> None:
    with endpoint(tls_files) as port:
        source = f"""from py2rust.stdlib import web_open_ca, web_read
def run() -> None:
    headers: dict[str, str] = {{}}
    with web_open_ca("https://localhost:{port}/regular", headers, 2000, 8, {str(tls_files / "ca.crt")!r}) as source:
        assert web_read(source, 3) == b"abc"
        assert web_read(source, 10) == b"defgh"
        assert web_read(source, 1) == b""
    errors: int = 0
    try:
        web_open_ca("https://127.0.0.1:{port}/regular", headers, 2000, 8, {str(tls_files / "ca.crt")!r})
    except Exception:
        errors = errors + 1
    assert errors == 1
    return
if __name__ == "__main__":
    run()
"""
        result = run(tmp_path, source, engine)
        assert result.returncode == 0, result.stderr
    return  # noqa: PLR1711 - explicit return required by repository guidelines
