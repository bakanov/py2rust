"""Stream framing, bounded production, disconnect lifetime and callback errors."""

import contextlib
import http.client
import socket
import time
from pathlib import Path

import pytest
from py2rust.compiler.service import ServiceCompiler, ServiceError

from tools.corpus_checks.common import Application

from .test_services import parity, program


def test_stream_constructor_boundaries(tmp_path: Path) -> None:
    assert (
        parity(
            tmp_path,
            """
from py2rust.stdlib import Json, StreamChunk, WebResponse, stream_chunk, web_stream
def run() -> None:
    large: str = "x"
    for index in range(16):
        large = large + large
    part: StreamChunk = stream_chunk(large.encode(), None, True)
    ok: WebResponse = web_stream({"Content-Type": "text/event-stream"}, {"cursor": 0}, 1)
    assert ok.status == 200 and len(ok.body) == 0
    errors: int = 0
    for interval in [0, -1, 60001]:
        try:
            web_stream({}, None, interval)
        except Exception:
            errors = errors + 1
    for header in ["Content-Length", "Transfer-Encoding", "Connection", "Trailer"]:
        try:
            web_stream({header: "0"}, None, 1)
        except Exception:
            errors = errors + 1
    try:
        stream_chunk((large + "x").encode(), None, True)
    except Exception:
        errors = errors + 1
    try:
        stream_chunk(b"", large, False)
    except Exception:
        errors = errors + 1
    try:
        web_stream({}, large, 1)
    except Exception:
        errors = errors + 1
    assert errors == 10
    print("bounded streams")
    return
if __name__ == "__main__":
    run()
""",
        )
        == "bounded streams\n"
    )


SOURCE = """
from py2rust.stdlib import (
    Json, StreamChunk, WebRequest, WebResponse, env_get, json_int, json_string,
    stream_chunk, web_stream, web_response, web_serve_stream, write_text,
)
def handle(request: WebRequest) -> WebResponse:
    if request.path == "/stream":
        interval: int = 1
        if request.query.get("mode", "finite") == "quiet":
            interval = 100
        return web_stream({"Content-Type": "application/octet-stream"},
            {"count": 0, "mode": request.query.get("mode", "finite")}, interval)
    return web_response(200, b"healthy", {})
def poll(state: Json) -> StreamChunk:
    mode: str = json_string(state["mode"])
    count: int = json_int(state["count"]) + 1
    state["count"] = count
    if mode == "quiet":
        write_text(env_get("COUNTER", "counter"), str(count))
        return stream_chunk(b"", state, False)
    if mode == "error":
        assert count < 2, "injected callback failure"
        return stream_chunk(b"before-error\\n", state, False)
    if mode == "slow":
        write_text(env_get("COUNTER", "counter"), str(count))
        data: str = "x"
        for index in range(16):
            data = data + data
        return stream_chunk(data.encode(), state, False)
    return stream_chunk((str(count) + "\\n").encode(), state, count == 3)
def run() -> None:
    web_serve_stream("127.0.0.1", 0, handle, poll)
    return
if __name__ == "__main__":
    run()
"""


@pytest.mark.parametrize("engine", ["python", "rust"])
def test_stream_transport_and_backpressure(tmp_path: Path, engine: str) -> None:
    application = Application(program(tmp_path, SOURCE, engine), engine)
    counter = tmp_path / "counter"
    with application.server(tmp_path, {"COUNTER": str(counter)}) as server:
        finite = server.request("GET", "/stream")
        assert finite.body == b"1\n2\n3\n"
        assert "content-length" not in finite.headers
        connection = http.client.HTTPConnection("127.0.0.1", server.port, timeout=5)
        try:
            connection.request("GET", "/stream?mode=error")
            response = connection.getresponse()
            assert response.status == 200 and response.readline() == b"before-error\n"
            try:
                assert response.read() == b""
            except http.client.IncompleteRead:
                pass  # HTTP/1.1 aborts chunked framing; HTTP/1.0 signals EOF.
            response.close()
        finally:
            connection.close()
        assert server.request("GET", "/health").body == b"healthy"

        # Advertise a tiny receive window, then never read the response body.
        stalled = socket.socket()
        stalled.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 1024)
        stalled.settimeout(5)
        try:
            stalled.connect(("127.0.0.1", server.port))
            stalled.sendall(b"GET /stream?mode=slow HTTP/1.1\r\nHost: localhost\r\n\r\n")
            time.sleep(1.5)
            produced = int(counter.read_text())
            assert 1 <= produced < 128, f"producer ran beyond bounded socket buffers: {produced} chunks"
            time.sleep(0.2)
            assert int(counter.read_text()) == produced, "a stalled writer must stop requesting chunks"
            assert server.request("GET", "/health").body == b"healthy"
            assert server.request("GET", "/stream").body == b"1\n2\n3\n"
        finally:
            stalled.close()
        time.sleep(0.2)
        ended = int(counter.read_text())
        time.sleep(0.2)
        assert int(counter.read_text()) == ended, "disconnected streams must not leave producer work running"
        assert server.request("GET", "/health").status == 200
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def test_empty_stream_deadline_stops_callbacks(tmp_path: Path) -> None:
    # Exercise both real 60-second connection deadlines together. Empty chunks
    # have no socket writes to notice EOF; timeout must cancel the poll loop.
    applications = []
    for engine in ["python", "rust"]:
        directory = tmp_path / engine
        directory.mkdir()
        applications.append((Application(program(directory, SOURCE, engine), engine), directory))
    with contextlib.ExitStack() as stack:
        clients = []
        for application, directory in applications:
            counter = directory / "counter"
            server = stack.enter_context(application.server(directory, {"COUNTER": str(counter)}))
            connection = http.client.HTTPConnection("127.0.0.1", server.port, timeout=65)
            stack.callback(connection.close)
            connection.request("GET", "/stream?mode=quiet")
            response = connection.getresponse()
            stack.callback(response.close)
            assert response.status == 200
            clients.append((server, response, counter))
        time.sleep(61)
        ended = []
        for server, response, counter in clients:
            with contextlib.suppress(http.client.IncompleteRead):
                assert response.read() == b""
            ended.append(int(counter.read_text()))
            assert ended[-1] > 1
            assert server.request("GET", "/health").body == b"healthy"
        time.sleep(0.4)
        assert [int(counter.read_text()) for _, _, counter in clients] == ended
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def test_bad_stream_callback_rejected_at_source() -> None:
    source = """
from py2rust.stdlib import Json, WebRequest, WebResponse, web_response, web_serve_stream
def handle(request: WebRequest) -> WebResponse:
    return web_response(200, b"", {})
def wrong(state: Json) -> Json:
    return state
if __name__ == "__main__":
    web_serve_stream("127.0.0.1", 0, handle, wrong)
"""
    with pytest.raises(ServiceError, match="stream poll callback must"):
        ServiceCompiler().compile(source)
    return  # noqa: PLR1711 - explicit return required by repository guidelines


@pytest.mark.parametrize("name", ["override", "abstract", "virtual", "true"])
def test_reserved_rust_binding_has_source_diagnostic(name: str) -> None:
    with pytest.raises(ServiceError, match="Rust keyword cannot be a binding") as caught:
        ServiceCompiler().compile(
            f"def run() -> int:\n    {name}: int = 1\n    return {name}\n"
            "if __name__ == '__main__':\n    print(run())\n"
        )
    assert caught.value.lineno == 2
    return  # noqa: PLR1711 - explicit return required by repository guidelines
