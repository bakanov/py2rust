"""Exercise a mypy/IR-compiled callback through a real native HTTP server."""

import http.client
import os
import socket
import subprocess
import time
from pathlib import Path

import pytest

from py2rust.compiler.frontend import FrontendError
from py2rust.compiler.pipeline import compile_typed
from py2rust.compiler.service import write_service_project

from .test_services import TARGET


def test_typed_web_callback(tmp_path: Path) -> None:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    source = f"""from py2rust.stdlib import WebRequest, WebResponse, web_response, web_serve

def failing_default() -> str:
    assert False, "default must still execute"
    return ""

def handle(request: WebRequest) -> WebResponse:
    assert request.method == "POST"
    assert request.path == "/echo"
    assert request.query["tag"] == "test"
    assert request.query.get("tag", "") == "test"
    assert request.query.get("missing", "") == ""
    assert len(request.body) == 12
    caught: bool = False
    try:
        request.query.get("tag", failing_default())
    except Exception:
        caught = True
    assert caught
    return web_response(201, request.body, {{"Content-Type": "application/octet-stream"}})
if __name__ == "__main__":
    web_serve("127.0.0.1", {port}, handle)
"""
    code = compile_typed({"main": (tmp_path / "main.py", source)})
    handle = code.split("fn py__main__handle(", 1)[1].split("\nfn ", 1)[0]
    assert "request.body.clone()" not in handle
    # The unknown failing default deliberately retains the conservative snapshot.
    assert 'get("tag").cloned().unwrap_or_default()' in handle
    assert 'get("missing").cloned().unwrap_or_default()' in handle
    write_service_project(code, tmp_path)
    env = dict(os.environ, CARGO_TARGET_DIR=str(TARGET), CARGO_PROFILE_DEV_DEBUG="0", CARGO_INCREMENTAL="0")
    result = subprocess.run(
        ["cargo", "build", "--locked", "--offline", "--manifest-path", str(tmp_path / "Cargo.toml")],
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
        env=env,
    )
    assert result.returncode == 0, result.stderr + code
    with subprocess.Popen(
        [str(TARGET / "debug" / "py2rust-service")], stdout=subprocess.PIPE, stderr=subprocess.PIPE
    ) as server:
        try:
            deadline = time.monotonic() + 10
            while True:
                assert server.poll() is None, server.communicate()
                try:
                    with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                        break
                except OSError:
                    if time.monotonic() >= deadline:
                        pytest.fail("native web server did not start")
                    time.sleep(0.02)
            connection = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
            try:
                payload = b"hello\x00native"
                connection.request("POST", "/echo?tag=test", payload)
                response = connection.getresponse()
                assert response.status == 201
                assert response.getheader("Content-Type") == "application/octet-stream"
                assert response.read() == payload
            finally:
                connection.close()
        finally:
            server.terminate()
            try:
                server.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                server.kill()
                server.communicate(timeout=5)


def test_web_callback_signature_is_checked(tmp_path: Path) -> None:
    source = """from py2rust.stdlib import web_serve

def wrong(value: int) -> int:
    return value
if __name__ == "__main__":
    web_serve("127.0.0.1", 12345, wrong)
"""
    with pytest.raises(FrontendError, match="incompatible type"):
        compile_typed({"main": (tmp_path / "main.py", source)})
