"""Incoming request targets retain information that a decoded query map cannot express."""

import http.client
from pathlib import Path

import pytest

from tools.corpus_checks.common import Application

from .test_services import program


@pytest.mark.parametrize("engine", ["python", "rust"])
def test_original_request_target(tmp_path: Path, engine: str) -> None:
    source = """from py2rust.stdlib import WebRequest, WebResponse, json_dumps, web_response, web_serve
def handle(request: WebRequest) -> WebResponse:
    return web_response(200, json_dumps({"target": request.target, "path": request.path, "query": request.query}).encode(), {"Content-Type": "application/json"})
def run() -> None:
    web_serve("127.0.0.1", 0, handle)
    return
if __name__ == "__main__":
    run()
"""
    app = Application(program(tmp_path, source, engine), engine)
    with app.server(tmp_path, {}) as server:
        for target, path, query in [
            ("/echo", "/echo", {}),
            ("/echo?", "/echo", {}),
            ("/echo?tag=a&tag=b&blank=&q=a+b&encoded=%2f%2F", "/echo", {"tag": "b", "q": "a b", "encoded": "//"}),
            ("/a%2Fb?x=%E4%B8%96%E7%95%8C&x=last", "/a%2Fb", {"x": "last"}),
        ]:
            response = server.request("GET", target)
            assert response.status == 200
            result = response.json()
            assert result["target"] == target and result["path"] == path
            # The existing convenience map may omit blank values; the raw target never does.
            for key, value in query.items():
                assert result["query"][key] == value
    return  # noqa: PLR1711 - explicit return required by repository guidelines


@pytest.mark.parametrize("engine", ["python", "rust"])
def test_application_cache_control_replaces_default(tmp_path: Path, engine: str) -> None:
    source = """from py2rust.stdlib import WebRequest, WebResponse, web_response, web_serve
def handle(request: WebRequest) -> WebResponse:
    headers: dict[str, str] = {}
    if request.path == "/private":
        headers["cAcHe-CoNtRoL"] = "private, max-age=60"
    return web_response(200, b"body", headers)
def run() -> None:
    web_serve("127.0.0.1", 0, handle)
    return
if __name__ == "__main__":
    run()
"""
    app = Application(program(tmp_path, source, engine), engine)
    with app.server(tmp_path, {}) as server:
        for path, expected in [("/private", "private, max-age=60"), ("/default", "no-store")]:
            connection = http.client.HTTPConnection("127.0.0.1", server.port, timeout=5)
            try:
                connection.request("GET", path)
                response = connection.getresponse()
                assert response.status == 200 and response.read() == b"body"
                assert response.headers.get_all("cache-control") == [expected]
            finally:
                connection.close()
    return  # noqa: PLR1711 - explicit return required by repository guidelines
