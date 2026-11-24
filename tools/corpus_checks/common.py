"""Process and HTTP fixtures; these checks are not application source."""

from __future__ import annotations

import contextlib
import http.client
import json
import os
import queue
import re
import subprocess
import threading
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Response:
    status: int
    headers: dict[str, str]
    body: bytes

    def json(self) -> object:
        return json.loads(self.body)


@dataclass
class Server:
    port: int
    scheme: str = "http"
    process: subprocess.Popen | None = None
    unix_path: str = ""

    @property
    def url(self) -> str:
        return f"{self.scheme}://127.0.0.1:{self.port}"

    def request(self, method: str, path: str, body: bytes = b"", headers: dict | None = None) -> Response:
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        try:
            connection.request(method, path, body=body, headers=headers or {})
            response = connection.getresponse()
            return Response(response.status, {k.lower(): v for k, v in response.getheaders()}, response.read())
        finally:
            connection.close()


@dataclass
class Application:
    command: list[str]
    engine: str

    def environment(self, settings: dict[str, str]) -> dict[str, str]:
        env = dict(os.environ, **settings)
        if self.engine == "rust":
            # The application runs without an interpreter on PATH or a usable
            # Python installation. Rust is built before entering this environment.
            env.update(PATH="/nonexistent", PYTHONHOME="/nonexistent", PYTHONPATH="/nonexistent")
        return env

    def run(self, directory: Path, settings: dict[str, str], timeout: int = 20) -> subprocess.CompletedProcess:
        return subprocess.run(
            self.command,
            cwd=directory,
            env=self.environment(settings),
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )

    @contextlib.contextmanager
    def server(self, directory: Path, settings: dict[str, str]) -> Iterator[Server]:
        process = subprocess.Popen(
            self.command,
            cwd=directory,
            env=self.environment(settings),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        lines: queue.Queue = queue.Queue()
        output: list[str] = []

        def read() -> None:
            for line in process.stdout:
                output.append(line)
                lines.put(line)
            lines.put(None)
            return  # noqa: PLR1711 - explicit return required by repository guidelines

        reader = threading.Thread(target=read, daemon=True)
        reader.start()
        try:
            for _ in range(50):
                line = lines.get(timeout=10)
                assert line is not None, "server exited before readiness:\n" + "".join(output)
                match = re.search(r"LISTENING (http|tcp|udp)://127\.0\.0\.1:(\d+)", line)
                if match:
                    yield Server(int(match[2]), match[1], process)
                    return
                if line.startswith("LISTENING unix://"):
                    path = Path(line.removeprefix("LISTENING unix://").rstrip("\n"))
                    if not path.is_absolute():
                        path = directory / path
                    yield Server(0, "unix", process, str(path))
                    return
            raise AssertionError("server did not announce readiness")
        finally:
            process.terminate()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=3)
            reader.join(timeout=3)
            process.stdout.close()
            with (directory / "process.log").open("a") as stream:
                stream.writelines(output)
        return
