"""Behavioral parity and real HTTP tests for the typed service profile."""

import contextlib
import http.client
import http.server
import json
import os
import queue
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest
from py2rust.compiler.service import ServiceCompiler, ServiceError, create_service_project

ROOT = Path(__file__).parents[1]
TARGET = Path(os.environ.get("PY2RUST_BUILD_DIR", str(ROOT / "build"))) / "service-test-target"


def program(tmp_path, source, engine, name="app"):
    if engine == "python":
        path = tmp_path / f"{name}.py"
        path.write_text(source)
        return [sys.executable, "-u", str(path)]
    if not shutil.which("cargo"):
        pytest.skip("cargo is required")
    output = tmp_path / name
    create_service_project(source, output)
    # Test binaries are copied per case; full DWARF data would retain gigabytes.
    env = dict(
        os.environ,
        CARGO_TARGET_DIR=str(TARGET),
        CARGO_PROFILE_DEV_DEBUG="0",
        CARGO_INCREMENTAL="0",
    )
    result = subprocess.run(
        [
            "cargo",
            "build",
            "--locked",
            "--offline",
            "--manifest-path",
            str(output / "Cargo.toml"),
        ],
        env=env,
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )
    assert result.returncode == 0, result.stderr + "\n" + (output / "src" / "main.rs").read_text()
    # Copy the executable: later compilations share the target name and must not
    # replace a server binary that is already running (ETXTBSY on Linux).
    binary = tmp_path / (name + "-bin")
    shutil.copyfile(TARGET / "debug" / "py2rust-service", binary)
    binary.chmod(0o755)
    return [str(binary)]


def run(tmp_path, source, engine, name="app"):
    return subprocess.run(
        program(tmp_path, source, engine, name),
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
        cwd=tmp_path,
    )


def parity(tmp_path, source):
    py = run(tmp_path, source, "python", "python")
    rs = run(tmp_path, source, "rust", "rust")
    assert py.returncode == rs.returncode == 0, py.stderr + rs.stderr
    assert py.stdout == rs.stdout
    assert py.stderr == rs.stderr
    return rs.stdout


def test_unicode_strings(tmp_path):
    parity(
        tmp_path,
        """
def run() -> None:
    text: str = "  Héllo 世界😀  "
    clean: str = text.strip()
    assert len(clean) == 9
    assert clean[-1] == "😀"
    assert clean.find("世界") == 6
    assert clean.startswith("Hé")
    assert clean.endswith("😀")
    assert "世界" in clean
    assert clean.encode().decode() == clean
    assert "\\x1c hello \\x1f".strip() == "hello"
    assert "one\\x1dtwo\\u00a0three".split() == ["one", "two", "three"]
    words: list[str] = "one,,two,".split(",")
    assert len(words) == 4
    assert "|".join(words) == "one||two|"
    assert "Straße".upper() == "STRASSE"
    assert "HELLO".lower() == "hello"
    print(clean.replace("世界", "world"))
if __name__ == "__main__":
    run()
""",
    )


def test_list_index_assignment(tmp_path: Path) -> None:
    output = parity(
        tmp_path,
        """
def value() -> int:
    print("value first")
    return 42
def position() -> int:
    print("index second")
    return -1
def run() -> None:
    items: list[int] = [10, 20, 30]
    items[position()] = value()
    assert items == [10, 20, 42]
    items[0] = items[-1]
    failures: int = 0
    for index in [-4, 3, 9223372036854775807, -9223372036854775808]:
        try:
            items[index] = 99
        except Exception:
            failures = failures + 1
    assert failures == 4
    assert items == [42, 20, 42]
    empty: list[int] = []
    try:
        empty[0] = 1
    except Exception:
        print("empty rejected")
    return
if __name__ == "__main__":
    run()
""",
    )
    assert output == "value first\nindex second\nempty rejected\n"


def test_stdlib_demo(tmp_path):
    source = (ROOT / "examples/services/stdlib_demo.py").read_text()
    output = parity(tmp_path, source)
    assert json.loads(output)["timestamp"] == "2024-03-01T00:00:00.000000+00:00"


def test_json_nested_types_and_pretty(tmp_path):
    parity(
        tmp_path,
        """
import json
from py2rust.stdlib import Json, json_string, json_int, json_bool, json_float, json_is_null, pretty
def run() -> None:
    data: Json = {"unicode": "世界", "items": [1, True, None, {"name": "x"}]}
    text: str = json.dumps(data)
    decoded: Json = json.loads(text)
    assert json_string(decoded["unicode"]) == "世界"
    assert json_int(decoded["items"][0]) == 1
    assert json_bool(decoded["items"][1])
    assert json_is_null(decoded["items"][2])
    assert json_float(json.loads("3.125")) == 3.125
    assert json_float(decoded["items"][0]) == 1.0
    assert json_string(decoded["items"][-1]["name"]) == "x"
    decoded["new"] = "value"
    print(pretty(decoded))
if __name__ == "__main__":
    run()
""",
    )


def test_time_datetime(tmp_path):
    parity(
        tmp_path,
        """
import time
from py2rust.stdlib import DateTime, datetime_parse, datetime_iso, datetime_add_seconds, utc_now
def run() -> None:
    start: float = time.monotonic()
    time.sleep(0.005)
    assert time.monotonic() >= start
    assert time.time() > 1700000000.0
    stamp: DateTime = datetime_parse("2024-02-29T23:59:59.123456+03:00")
    assert datetime_iso(stamp) == "2024-02-29T20:59:59.123456+00:00"
    after: DateTime = datetime_add_seconds(stamp, 1)
    assert datetime_iso(after) == "2024-02-29T21:00:00.123456+00:00"
    now: DateTime = utc_now()
    assert now > stamp
    print(datetime_iso(after))
if __name__ == "__main__":
    run()
""",
    )


def test_logging(tmp_path):
    parity(
        tmp_path,
        """
import logging
from py2rust.stdlib import log_configure
def run() -> None:
    log_configure(logging.INFO)
    logging.debug("hidden")
    logging.info("hello 世界")
    logging.warning("warning")
    logging.error("error")
if __name__ == "__main__":
    run()
""",
    )


def test_files_directories_and_collections(tmp_path):
    parity(
        tmp_path,
        """
from py2rust.stdlib import mkdir_all, path_join, path_exists, write_text, read_text, write_bytes, read_bytes, list_dir, remove_file, remove_dir, pretty
def run() -> None:
    root: str = "files"
    mkdir_all(root)
    name: str = path_join(root, "text.txt")
    write_text(name, "世界\\r\\ntext\\n")
    assert read_text(name) == "世界\\r\\ntext\\n"
    binary: str = path_join(root, "binary.dat")
    write_bytes(binary, b"\\x00\\xffA")
    assert read_bytes(binary) == b"\\x00\\xffA"
    assert path_exists(name)
    names: list[str] = list_dir(root)
    assert names == ["binary.dat", "text.txt"]
    names.append("third")
    assert names[-1] == "third"
    counts: dict[str, int] = {"one": 1, "two": 2}
    counts["two"] = 3
    assert counts["two"] == 3
    assert counts.get("absent", 7) == 7
    assert "one" in counts
    unique: set[str] = {"a", "a", "b"}
    unique.add("c")
    assert len(unique) == 3
    assert "c" in unique
    total: int = 0
    numbers: list[int] = [1, 2, 3]
    for number in numbers:
        total = total + number
    assert total == 6
    pair: tuple[int, str] = (4, "four")
    assert pair[0] == 4
    assert pair[1] == "four"
    print(pretty(counts))
    remove_file(name)
    remove_file(binary)
    remove_dir(root)
    assert not path_exists(root)
if __name__ == "__main__":
    run()
""",
    )


def test_regex_and_enums(tmp_path):
    parity(
        tmp_path,
        """
from enum import Enum
from py2rust.stdlib import regex_search, regex_fullmatch, regex_findall, regex_replace, pretty
class Status(Enum):
    OK = "ok"
    ERROR = "error"
class Code(Enum):
    OK = 200
    MISSING = 404
def run() -> None:
    status: Status = Status.OK
    assert status == Status.OK
    assert status.name == "OK"
    assert status.value == "ok"
    assert Code.MISSING.value == 404
    assert regex_search(r"\\d+", "abc12")
    assert not regex_fullmatch(r"\\d+", "abc12")
    matches: list[str] = regex_findall(r"([a-z]+)-(\\d+)", "a-1 bb-22")
    assert matches == ["a-1", "bb-22"]
    assert regex_replace(r"\\d+", "$1", "a12b34") == "a$1b$1"
    print(pretty(matches))
if __name__ == "__main__":
    run()
""",
    )


@pytest.mark.parametrize(
    "expression",
    [
        'json_loads("{")',
        'json_loads("NaN")',
        'json_loads("9223372036854775808")',
        'json_loads("18446744073709551616")',
        'json_loads("-18446744073709551616")',
        'json_loads("1e400")',
        'datetime_parse("2024-02-30T00:00:00Z")',
        'datetime_parse("2024-01-01T00:00:00")',
        'datetime_parse("2024-01-01T00:00:00+01:60")',
        'regex_search("[", "abc")',
        'regex_search("(?=a)", "abc")',
        r'regex_search(r"(a)\1", "aa")',
        'read_text("missing-file")',
        "sleep(-1.0)",
    ],
)
def test_library_errors_propagate(tmp_path, expression):
    source = f"""from py2rust.stdlib import json_loads, datetime_parse, regex_search, read_text, sleep
def run() -> None:
    {expression}
if __name__ == "__main__":
    run()
"""
    for engine in ("python", "rust"):
        result = run(tmp_path, source, engine, engine)
        assert result.returncode != 0
        assert "panicked" not in result.stderr


@pytest.mark.parametrize(
    "expression,typ",
    [
        ('"abc"[9]', "str"),
        ('b"\\xff".decode()', "str"),
        ('"a".split("")', "list[str]"),
        ('regex_findall("a*", "bbb")', "list[str]"),
        ('json_string(json_loads("1"))', "str"),
        ('json_loads("{}") ["missing"]', "Json"),
    ],
)
def test_value_errors_do_not_panic(tmp_path, expression, typ):
    source = f"""from py2rust.stdlib import Json, json_loads, json_string, regex_findall
def run() -> None:
    value: {typ} = {expression}
if __name__ == "__main__":
    run()
"""
    for engine in ("python", "rust"):
        result = run(tmp_path, source, engine, engine)
        assert result.returncode != 0
        assert "panicked" not in result.stderr


@contextlib.contextmanager
def server_process(command):
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    lines = queue.Queue()
    threading.Thread(target=lambda: lines.put(process.stdout.readline()), daemon=True).start()
    try:
        line = lines.get(timeout=10)
        if not line.strip().isdigit():
            process.kill()
            _, stderr = process.communicate(timeout=5)
            pytest.fail(line + stderr)
        yield process, int(line)
    finally:
        if process.poll() is None:
            process.kill()
        process.communicate(timeout=5)


@pytest.mark.parametrize("server_engine", ["python", "rust"])
@pytest.mark.parametrize("client_engine", ["python", "rust"])
def test_http_json_examples(tmp_path, server_engine, client_engine):
    examples = ROOT / "examples" / "services"
    source = (examples / "json_server.py").read_text().replace("8080", "0")
    with server_process(program(tmp_path, source, server_engine, "server")) as (
        process,
        port,
    ):
        client = (examples / "json_client.py").read_text().replace("8080", str(port))
        result = run(tmp_path, client, client_engine, "client")
        assert result.returncode == 0, result.stderr
        assert json.loads(result.stdout) == {"message": "Hello, 世界", "ok": True}
        _, stderr = process.communicate(timeout=5)
        assert process.returncode == 0, stderr


@pytest.mark.parametrize("engine", ["python", "rust"])
def test_http_bad_json_and_body_limit(tmp_path, engine):
    source = """from py2rust.stdlib import HttpServer, Json, http_listen, http_port, http_serve_json
def handle(method: str, path: str, body: Json) -> Json:
    return body
def run() -> None:
    server: HttpServer = http_listen("127.0.0.1", 0)
    print(http_port(server))
    http_serve_json(server, handle, 2, 16)
if __name__ == "__main__":
    run()
"""
    with server_process(program(tmp_path, source, engine)) as (process, port):
        for body, status in [("{", 400), ("x" * 17, 413)]:
            connection = http.client.HTTPConnection("127.0.0.1", port, timeout=3)
            try:
                connection.request("POST", "/", body, {"Content-Type": "application/json"})
                response = connection.getresponse()
                assert response.status == status
                assert json.loads(response.read()) == {"error": "invalid request"}
            finally:
                connection.close()
        _, stderr = process.communicate(timeout=5)
        assert process.returncode == 0, stderr


@pytest.mark.parametrize("engine", ["python", "rust"])
def test_http_status_chunking_and_limits(tmp_path, engine):
    class Handler(http.server.BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, *args):
            return

        def do_GET(self):
            self.send_response(404)
            self.send_header("Transfer-Encoding", "chunked")
            self.end_headers()
            self.wfile.write(b"4\r\ntest\r\n3\r\n123\r\n0\r\n\r\n")

    with http.server.HTTPServer(("127.0.0.1", 0), Handler) as server:
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            for limit, success in [(20, True), (5, False)]:
                source = f"""from py2rust.stdlib import HttpResponse, http_request
def run() -> None:
    response: HttpResponse = http_request("GET", "http://127.0.0.1:{server.server_port}/", "", 1000, {limit})
    assert response.status == 404
    assert response.body == "test123"
if __name__ == "__main__":
    run()
"""
                result = run(tmp_path, source, engine, f"limit{limit}")
                assert (result.returncode == 0) == success, result.stderr
        finally:
            server.shutdown()
            thread.join(timeout=5)


@pytest.mark.parametrize("engine", ["python", "rust"])
def test_http_redirect_timeout_and_invalid_utf8(tmp_path, engine):
    class Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, *args):
            return

        def do_GET(self):
            if self.path == "/slow":
                time.sleep(0.2)
            status = 302 if self.path == "/redirect" else 200
            body = b"\xff" if self.path == "/invalid" else b"response"
            try:
                self.send_response(status)
                self.send_header("Content-Length", str(len(body)))
                if status == 302:
                    self.send_header("Location", "/unexpected")
                self.end_headers()
                self.wfile.write(body)
            except OSError:
                pass  # The timeout case deliberately closes its connection.

    with http.server.HTTPServer(("127.0.0.1", 0), Handler) as server:
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            for route, timeout, success in [
                ("redirect", 1000, True),
                ("slow", 30, False),
                ("invalid", 1000, False),
            ]:
                source = f"""from py2rust.stdlib import HttpResponse, http_request
def run() -> None:
    response: HttpResponse = http_request("GET", "http://127.0.0.1:{server.server_port}/{route}", "", {timeout}, 1024)
    assert response.status == 302
    assert response.body == "response"
if __name__ == "__main__":
    run()
"""
                result = run(tmp_path, source, engine, route)
                assert (result.returncode == 0) == success, result.stderr
                assert "panicked" not in result.stderr
        finally:
            server.shutdown()
            thread.join(timeout=5)


def test_generated_project_is_locked(tmp_path):
    create_service_project("if __name__ == '__main__':\n    print('hello')\n", tmp_path)
    assert (tmp_path / "Cargo.lock").read_bytes() == (ROOT / "py2rust/compiler/service_runtime/Cargo.lock").read_bytes()


@pytest.mark.parametrize("members", ["A = 1\n    A = 2", "A = 1\n    B = 1", "A = 9223372036854775808"])
def test_invalid_enums_are_rejected(members):
    source = f"from enum import Enum\nclass State(Enum):\n    {members}\nif __name__ == '__main__':\n    pass\n"
    with pytest.raises(ServiceError):
        ServiceCompiler().compile(source)


def test_numeric_overflow_is_an_error(tmp_path):
    for expression, typ in [
        ("9223372036854775807 + 1", "int"),
        ("1e308 * 1e308", "float"),
    ]:
        source = f"def run() -> None:\n    number: {typ} = {expression}\nif __name__ == '__main__':\n    run()\n"
        result = run(tmp_path, source, "rust", typ)
        assert result.returncode != 0
        assert "panicked" not in result.stderr


@pytest.mark.parametrize(
    "body",
    [
        "x = 1",
        'x: int = "str"',
        'x: list[int] = [1, "s"]',
        "import socket",
        "x: str = unknown()",
        "x: int = 1 < 2 < 3",
        'x: int = eval("1")',
        "x: int = None",
        "x: tuple[int] = (1, 2)",
        "x: int = {}",
        "x: int = [1]",
    ],
)
def test_unsupported_source_is_rejected(body):
    source = f"def run() -> None:\n    {body}\nif __name__ == '__main__':\n    run()\n"
    with pytest.raises(ServiceError) as error:
        ServiceCompiler().compile(source)
    assert error.value.lineno == 2
