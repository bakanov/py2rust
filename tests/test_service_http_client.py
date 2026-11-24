"""Binary HTTP clients against an independent server, including real TLS."""

import contextlib
import http.server
import ssl
import threading
from collections.abc import Iterator
from pathlib import Path

import pytest

from . import test_service_tls
from .test_services import run

tls_files = test_service_tls.tls_files


@contextlib.contextmanager
def endpoint(tls: Path | None = None) -> Iterator[tuple[int, list]]:
    received = []

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            body = self.rfile.read(int(self.headers.get("Content-Length", "0")))
            received.append(
                (self.path, body, self.headers.get("Idempotency-Key"), self.headers.get_all("Content-Type"))
            )
            if self.path == "/disconnect":
                self.close_connection = True
                return
            self.send_response(302 if self.path == "/redirect" else 503)
            self.send_header("Content-Length", str(len(body) + (1 if self.path == "/truncated" else 0)))
            self.send_header("Retry-After", "7")
            self.send_header("X-Repeat", "first")
            self.send_header("X-Repeat", "second")
            self.send_header("Location", "/unexpected")
            if self.path == "/bad-header":
                self.send_header("X-Invalid", "é")
            self.end_headers()
            self.wfile.write(body)
            return

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
        yield server.server_port, received
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


@pytest.mark.parametrize("engine", ["python", "rust"])
def test_binary_headers_status_and_failures(tmp_path: Path, engine: str) -> None:
    with endpoint() as (port, received):
        source = f"""from py2rust.stdlib import WebResponse, web_request
def run() -> None:
    headers: dict[str, str] = {{"Idempotency-Key": "event-1", "Content-Type": "application/custom"}}
    body: bytes = bytes.fromhex("00ff807ff09f9880")
    response: WebResponse = web_request("POST", "http://127.0.0.1:{port}/echo", body, headers, 2000, 1024)
    assert response.status == 503
    assert response.body == body
    assert response.headers["retry-after"] == "7"
    assert response.headers["x-repeat"] == "first"
    response = web_request("POST", "http://127.0.0.1:{port}/redirect", body, headers, 2000, 1024)
    assert response.status == 302
    failures: int = 0
    for path in ["/disconnect", "/overlimit"]:
        try:
            web_request("POST", "http://127.0.0.1:{port}" + path, body, headers, 2000, 3)
        except Exception:
            failures = failures + 1
    for path in ["/bad-header", "/truncated"]:
        try:
            web_request("POST", "http://127.0.0.1:{port}" + path, body, headers, 2000, 1024)
        except Exception:
            failures = failures + 1
    bad: list[dict[str, str]] = [{{"Bad Name": "x"}}, {{"x": "line\\nbreak"}}, {{"host": "x"}}, {{"X": "1", "x": "2"}}, {{"x": "é"}}]
    for item in bad:
        try:
            web_request("POST", "http://127.0.0.1:{port}/unexpected", body, item, 2000, 1024)
        except Exception:
            failures = failures + 1
    for timeout in [0, -1, 86400001]:
        try:
            web_request("POST", "http://127.0.0.1:{port}/unexpected", body, headers, timeout, 1024)
        except Exception:
            failures = failures + 1
    assert failures == 12
    print("binary client passed")
    return
if __name__ == "__main__":
    run()
"""
        result = run(tmp_path, source, engine)
        assert result.returncode == 0, result.stderr
        assert result.stdout.strip() == "binary client passed"
        assert [request[0] for request in received] == [
            "/echo",
            "/redirect",
            "/disconnect",
            "/overlimit",
            "/bad-header",
            "/truncated",
        ]
        assert all(
            body == bytes.fromhex("00ff807ff09f9880") and key == "event-1" and types == ["application/custom"]
            for _, body, key, types in received
        )


@pytest.mark.parametrize("engine", ["python", "rust"])
def test_binary_client_private_ca_and_hostname(tmp_path: Path, tls_files: Path, engine: str) -> None:
    with endpoint(tls_files) as (port, received):
        source = f"""from py2rust.stdlib import WebResponse, web_request, web_request_ca
def run() -> None:
    headers: dict[str, str] = {{}}
    body: bytes = bytes.fromhex("00ff")
    response: WebResponse = web_request_ca("POST", "https://localhost:{port}/tls", body, headers, 2000, 1024, {str(tls_files / "ca.crt")!r})
    assert response.body == body and response.status == 503
    failures: int = 0
    try:
        web_request_ca("POST", "https://127.0.0.1:{port}/tls", body, headers, 2000, 1024, {str(tls_files / "ca.crt")!r})
    except Exception:
        failures = failures + 1
    try:
        web_request("POST", "https://localhost:{port}/tls", body, headers, 2000, 1024)
    except Exception:
        failures = failures + 1
    assert failures == 2
    return
if __name__ == "__main__":
    run()
"""
        result = run(tmp_path, source, engine)
        assert result.returncode == 0, result.stderr
        assert len(received) == 1
