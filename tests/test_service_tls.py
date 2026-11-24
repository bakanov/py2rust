"""Real TLS certificate validation and absolute server-deadline tests."""

import http.client
import json
import shutil
import socket
import ssl
import subprocess
import threading
import time

import pytest

from .test_services import ROOT, program, run, server_process


@pytest.fixture(scope="module")
def tls_files(tmp_path_factory):
    if not shutil.which("openssl"):
        pytest.skip("openssl is required to generate temporary TLS test certificates")
    root = tmp_path_factory.mktemp("service-tls")

    def openssl(*args):
        subprocess.run(["openssl", *args], cwd=root, capture_output=True, check=True, timeout=30)

    for name in ("ca", "wrong-ca"):
        openssl(
            "req",
            "-x509",
            "-newkey",
            "rsa:2048",
            "-nodes",
            "-days",
            "2",
            "-subj",
            f"/CN={name}",
            "-addext",
            "basicConstraints=critical,CA:TRUE",
            "-addext",
            "keyUsage=critical,keyCertSign,cRLSign",
            "-keyout",
            f"{name}.key",
            "-out",
            f"{name}.crt",
        )
    openssl(
        "req",
        "-newkey",
        "rsa:2048",
        "-nodes",
        "-subj",
        "/CN=localhost",
        "-keyout",
        "server.key",
        "-out",
        "server.csr",
    )
    (root / "extensions.cnf").write_text(
        "basicConstraints=critical,CA:FALSE\nkeyUsage=critical,digitalSignature,keyEncipherment\n"
        "extendedKeyUsage=serverAuth\nsubjectAltName=DNS:localhost\n"
    )
    for name, days in [("server", "2"), ("expired", "-1")]:
        openssl(
            "x509",
            "-req",
            "-in",
            "server.csr",
            "-CA",
            "ca.crt",
            "-CAkey",
            "ca.key",
            "-CAcreateserial",
            "-days",
            days,
            "-extfile",
            "extensions.cnf",
            "-out",
            f"{name}.crt",
        )
    return root


def server_source(
    tls_files=None,
    count=1,
    certificate="server",
    accept_timeout=10000,
    connection_timeout=10000,
):
    listen = 'http_listen("127.0.0.1", 0)'
    if tls_files is not None:
        listen = f'https_listen("127.0.0.1", 0, {str(tls_files / (certificate + ".crt"))!r}, {str(tls_files / "server.key")!r})'
    return f"""from py2rust.stdlib import HttpServer, Json, http_listen, https_listen, http_port, http_serve_json_timeout
def handle(method: str, path: str, body: Json) -> Json:
    return body
def run() -> None:
    server: HttpServer = {listen}
    print(http_port(server))
    http_serve_json_timeout(server, handle, {count}, 65536, {accept_timeout}, {connection_timeout})
if __name__ == "__main__":
    run()
"""


@pytest.mark.parametrize("server_engine", ["python", "rust"])
@pytest.mark.parametrize("client_engine", ["python", "rust"])
def test_https_json_interoperability(tmp_path, tls_files, server_engine, client_engine):
    source = (ROOT / "examples/services/https_server.py").read_text()
    source = source.replace("8443", "0").replace("build/tls/", str(tls_files) + "/")
    command = program(tmp_path, source, server_engine, "tls-server")
    with server_process(command) as (process, port):
        client = (ROOT / "examples/services/https_client.py").read_text()
        client = client.replace("8443", str(port)).replace("build/tls/", str(tls_files) + "/")
        result = run(tmp_path, client, client_engine, "tls-client")
        assert result.returncode == 0, result.stderr
        assert json.loads(result.stdout) == {"message": "Hello, 世界", "ok": True}
        _, stderr = process.communicate(timeout=5)
        assert process.returncode == 0, stderr


@pytest.mark.parametrize("server_engine", ["python", "rust"])
@pytest.mark.parametrize("client_engine", ["python", "rust"])
@pytest.mark.parametrize("failure", ["untrusted", "wrong_ca", "hostname", "expired"])
def test_https_rejects_invalid_certificates(tmp_path, tls_files, server_engine, client_engine, failure):
    source = server_source(tls_files, certificate="expired" if failure == "expired" else "server")
    with server_process(program(tmp_path, source, server_engine, "server")) as (
        process,
        port,
    ):
        host = "127.0.0.1" if failure == "hostname" else "localhost"
        arguments = f'"GET", "https://{host}:{port}/", "", 2000, 1024'
        if failure == "untrusted":
            function = "http_request"
        else:
            function = "https_request_ca"
            ca = tls_files / ("wrong-ca.crt" if failure == "wrong_ca" else "ca.crt")
            arguments += f", {str(ca)!r}"
        client = f"from py2rust.stdlib import {function}\nif __name__ == '__main__':\n    {function}({arguments})\n"
        result = run(tmp_path, client, client_engine, "client")
        assert result.returncode != 0
        assert "panicked" not in result.stderr
        assert any(word in result.stderr.lower() for word in ("certificate", "cert", "issuer", "tls")), result.stderr
        _, stderr = process.communicate(timeout=5)
        assert process.returncode == 0, stderr


@pytest.mark.parametrize("engine", ["python", "rust"])
def test_server_idle_deadline(tmp_path, engine):
    source = server_source(accept_timeout=150)
    with server_process(program(tmp_path, source, engine)) as (process, _):
        _, stderr = process.communicate(timeout=3)
        assert process.returncode != 0
        assert "panicked" not in stderr
        assert "time" in stderr.lower() or "deadline" in stderr.lower()


@pytest.mark.parametrize("engine", ["python", "rust"])
@pytest.mark.parametrize("phase", ["headers", "body", "trickle", "tls"])
def test_connection_deadline_recovers_for_next_client(tmp_path, tls_files, engine, phase):
    source = server_source(tls_files if phase == "tls" else None, count=2, connection_timeout=400)
    with server_process(program(tmp_path, source, engine)) as (process, port):
        with socket.create_connection(("127.0.0.1", port), timeout=3) as slow:
            started = time.monotonic()
            if phase == "body":
                slow.sendall(b"POST / HTTP/1.1\r\nHost: localhost\r\nContent-Length: 20\r\n\r\n{")
            elif phase in ("headers", "trickle"):
                slow.sendall(b"POST / HTTP/1.1\r\nX-Slow: ")
            if phase == "trickle":
                for _ in range(8):
                    time.sleep(0.075)
                    try:
                        slow.sendall(b"x")
                    except OSError:
                        break
            try:
                assert slow.recv(4096) == b""
            except ConnectionResetError:
                pass
            assert time.monotonic() - started < 2.5
        if phase == "tls":
            context = ssl.create_default_context(cafile=str(tls_files / "ca.crt"))
            client = http.client.HTTPSConnection("localhost", port, context=context, timeout=3)
        else:
            client = http.client.HTTPConnection("127.0.0.1", port, timeout=3)
        try:
            client.request("POST", "/healthy", '{"ok":true}')
            response = client.getresponse()
            assert response.status == 200
            assert json.loads(response.read()) == {"ok": True}
        finally:
            client.close()
        _, stderr = process.communicate(timeout=3)
        assert process.returncode == 0, stderr


@pytest.mark.parametrize("engine", ["python", "rust"])
def test_tls_configuration_errors(tmp_path, tls_files, engine):
    bad = tmp_path / "bad.pem"
    bad.write_text("not a certificate or key")
    calls = [
        f'https_request_ca("GET", "http://localhost/", "", 1000, 1024, {str(tls_files / "ca.crt")!r})',
        f'https_request_ca("GET", "https://localhost/", "", 1000, 1024, {str(bad)!r})',
        f'https_listen("127.0.0.1", 0, {str(bad)!r}, {str(tls_files / "server.key")!r})',
        f'https_listen("127.0.0.1", 0, {str(tls_files / "server.crt")!r}, {str(tls_files / "wrong-ca.key")!r})',
    ]
    for index, call in enumerate(calls):
        source = f"from py2rust.stdlib import https_request_ca, https_listen\nif __name__ == '__main__':\n    {call}\n"
        result = run(tmp_path, source, engine, f"bad-{index}")
        assert result.returncode != 0
        assert "panicked" not in result.stderr


@pytest.mark.parametrize("engine", ["python", "rust"])
def test_https_client_handshake_timeout(tmp_path, engine):
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        port = listener.getsockname()[1]
        source = f"""from py2rust.stdlib import http_request
if __name__ == "__main__":
    http_request("GET", "https://localhost:{port}/", "", 200, 1024)
"""
        command = program(tmp_path, source, engine)
        release = threading.Event()

        def stall():
            listener.settimeout(5)
            connection, _ = listener.accept()
            with connection:
                release.wait(timeout=5)

        thread = threading.Thread(target=stall, daemon=True)
        thread.start()
        try:
            started = time.monotonic()
            result = subprocess.run(command, capture_output=True, text=True, timeout=3, check=False)
            assert result.returncode != 0
            assert "panicked" not in result.stderr
            assert 0.1 <= time.monotonic() - started < 2.5
            # Unix socket timeouts can surface as WouldBlock through rustls.
            assert any(word in result.stderr.lower() for word in ("tim", "wouldblock")), result.stderr
        finally:
            release.set()
            thread.join(timeout=6)


@pytest.mark.parametrize("engine", ["python", "rust"])
def test_server_write_deadline(tmp_path, engine):
    source = server_source(count=2, connection_timeout=500).replace(
        "    return body",
        """    if path == "/large":
        text: str = "x"
        for index in range(24):
            text = text + text
        return text
    return body""",
    )
    with server_process(program(tmp_path, source, engine)) as (process, port):
        with socket.socket() as stalled:
            stalled.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 1024)
            stalled.connect(("127.0.0.1", port))
            stalled.sendall(b"GET /large HTTP/1.1\r\nHost: localhost\r\n\r\n")
            time.sleep(0.8)
            # The first peer stays connected without reading. A healthy second
            # request must succeed, proving the blocked response write ended.
            client = http.client.HTTPConnection("127.0.0.1", port, timeout=3)
            try:
                client.request("POST", "/healthy", '{"ok":true}')
                response = client.getresponse()
                assert response.status == 200
                assert json.loads(response.read()) == {"ok": True}
            finally:
                client.close()
        _, stderr = process.communicate(timeout=3)
        assert process.returncode == 0, stderr


@pytest.mark.parametrize("engine", ["python", "rust"])
@pytest.mark.parametrize("accept,connection", [(0, 100), (100, -1), (86400001, 100), (100, 86400001)])
def test_invalid_server_timeouts(tmp_path, engine, accept, connection):
    result = run(
        tmp_path,
        server_source(accept_timeout=accept, connection_timeout=connection),
        engine,
    )
    assert result.returncode != 0
    assert "panicked" not in result.stderr
