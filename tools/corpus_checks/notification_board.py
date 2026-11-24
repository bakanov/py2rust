"""Independent SSE parsing, replay, lag and persistence assertions."""

from __future__ import annotations

import contextlib
import http.client
import json
import socket
import time
from pathlib import Path

from .common import Application, Response, Server


class Subscription:
    def __init__(self, server: Server, path: str = "/subscribe", headers: dict | None = None) -> None:
        self.connection = http.client.HTTPConnection("127.0.0.1", server.port, timeout=5)
        self.connection.request("GET", path, headers=headers or {})
        self.response = self.connection.getresponse()
        assert self.response.status == 200, self.response.read()
        assert self.response.getheader("Content-Type").startswith("text/event-stream")
        assert self.response.getheader("Content-Length") is None, "stream must not advertise a complete buffered body"
        self.last_id = ""

    def block(self) -> list[str]:
        lines = []
        for _ in range(50):
            line = self.response.readline(20000)
            assert line, "stream ended before an event delimiter"
            assert len(line) < 20000, "oversized event line"
            if line in {b"\n", b"\r\n"}:
                return lines
            lines.append(line.decode("utf-8").rstrip("\r\n"))
        raise AssertionError("stream frame has too many lines")

    def event(self) -> dict:
        # Parse fields independently from the application's frame encoder.
        for _ in range(20):
            kind = "message"
            data = []
            for line in self.block():
                if line.startswith(":"):
                    continue
                name, separator, value = line.partition(":")
                if separator and value.startswith(" "):
                    value = value[1:]
                if name == "id" and "\0" not in value:
                    self.last_id = value
                elif name == "event":
                    kind = value
                elif name == "data":
                    data.append(value)
            if data:
                return {"id": self.last_id, "event": kind, "data": json.loads("\n".join(data))}
        raise AssertionError("no event after 20 frames")

    def close(self) -> None:
        self.response.close()
        self.connection.close()
        return  # noqa: PLR1711 - explicit return required by repository guidelines


@contextlib.contextmanager
def subscription(server: Server, path: str = "/subscribe", headers: dict | None = None):
    client = Subscription(server, path, headers)
    try:
        yield client
    finally:
        client.close()
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def publish(server: Server, key: str, data: object, topic: str = "updates") -> Response:
    return server.request(
        "POST", "/events", json.dumps({"key": key, "topic": topic, "data": data}, ensure_ascii=False).encode()
    )


def check(application: Application, directory: Path) -> dict:
    snapshot = directory / "board.json"
    settings = {"BOARD_STATE": str(snapshot), "BOARD_PORT": "0", "BOARD_NOW": "1000", "BOARD_RETAIN": "5"}
    observations = {}
    with application.server(directory, settings) as server:
        assert server.request("GET", "/status").json() == {"oldest": 1, "last": 0, "retained": 0}
        with subscription(server) as first, subscription(server) as second:
            assert first.block() == second.block() == ["retry: 1000", ": connected"]
            # Both responses are already open when the publication is made.
            payload = {"text": "Привет 世界\n\nid: 999\nevent: forged\r\n", "values": [True, None, 5]}
            created = publish(server, "one", payload)
            assert created.status == 201
            expected = {"id": "1", "event": "notification", "data": created.json()}
            assert first.event() == second.event() == expected
            observations["live"] = expected
            before = snapshot.read_bytes()
            duplicate = publish(server, "one", payload)
            assert duplicate.status == 200 and duplicate.json() == created.json()
            assert snapshot.read_bytes() == before
            assert publish(server, "one", payload, "different").status == 409
            assert publish(server, "bad\nkey", {}).status == 400
            assert publish(server, "too-big", "x" * 8193).status == 400
            assert server.request("POST", "/events", b"x" * 16385).status == 413
            assert server.request("POST", "/events", b"{broken").status == 400
            assert snapshot.read_bytes() == before
            assert first.block() == [": keepalive"]
            assert publish(server, "two", "second", "other").status == 201
            assert first.event()["id"] == "2"
        with subscription(server, "/subscribe?after=0", {"Last-Event-ID": "1"}) as resumed:
            assert resumed.event()["id"] == "2", "Last-Event-ID must override the original URL cursor"
            assert publish(server, "three", 3).status == 201
            assert resumed.event()["id"] == "3"
        page = server.request("GET", "/events?after=0&limit=1").json()
        assert [event["id"] for event in page["events"]] == [1] and page["next"] == 1
        filtered = server.request("GET", "/events?after=0&topic=other").json()
        assert [event["id"] for event in filtered["events"]] == [2] and filtered["next"] == 3
        before = snapshot.read_bytes()
        for cursor in ["-1", "01", "1.0", "true", "1000000000000000000", "abc"]:
            assert server.request("GET", "/subscribe?after=" + cursor).status == 400
        for path in ["/events?limit=0", "/events?limit=101", "/events?topic=%0A"]:
            assert server.request("GET", path).status == 400
        assert server.request("GET", "/subscribe?after=4").status == 409
        assert snapshot.read_bytes() == before
        for index in range(4, 9):
            assert publish(server, "event-" + str(index), index).status == 201
        limits = {"oldest": 4, "last": 8, "retained": 5}
        assert server.request("GET", "/status").json() == limits
        assert server.request("GET", "/subscribe", headers={"Last-Event-ID": "2"}).status == 409
        assert server.request("GET", "/events?after=2").status == 409
        with subscription(server, "/subscribe?after=3") as replay:
            assert [replay.event()["id"] for _ in range(5)] == [str(n) for n in range(4, 9)]
        observations["retained"] = server.request("GET", "/events").json()

    with application.server(directory, dict(settings, BOARD_NOW="900")) as server:
        before = snapshot.read_bytes()
        with subscription(server, headers={"Last-Event-ID": "7"}) as replay:
            assert replay.event()["id"] == "8"
            assert snapshot.read_bytes() == before, "subscriptions must not rewrite persistent state"
            result = publish(server, "nine", {"restart": True})
            assert result.status == 201 and result.json()["created"] == 1000
            assert replay.event()["id"] == "9"
        # A pruned key may be reused, but sequence IDs never rewind.
        reused = publish(server, "one", "new retained publication")
        assert reused.status == 201 and reused.json()["id"] == 10
        observations["restart"] = server.request("GET", "/events").json()

    lag_settings = dict(settings, BOARD_STATE=str(directory / "lag.json"), BOARD_RETAIN="2", BOARD_POLL="1000")
    with application.server(directory, lag_settings) as server:
        with subscription(server) as lagging:
            assert lagging.block() == ["retry: 1000", ": connected"]
            for index in range(3):
                assert publish(server, "lag-" + str(index), index).status == 201
            gap = lagging.event()
            assert gap == {"id": "", "event": "gap", "data": {"oldest": 2, "last": 3, "retained": 2}}
            assert lagging.response.read() == b"", "a lost replay window must end, never silently skip events"
            observations["gap"] = gap
        with subscription(server) as fresh:
            assert [fresh.event()["id"] for _ in range(2)] == ["2", "3"]

    # Fill a non-reading peer's receive window while another peer consumes every
    # publication. The bounded replay log may close the lagging peer with a gap;
    # it must never stall the publisher or the healthy subscription.
    pressure_settings = dict(settings, BOARD_STATE=str(directory / "pressure.json"), BOARD_POLL="1")
    with application.server(directory, pressure_settings) as server:
        stalled = socket.socket()
        stalled.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 1024)
        stalled.settimeout(5)
        try:
            stalled.connect(("127.0.0.1", server.port))
            stalled.sendall(b"GET /subscribe?after=0 HTTP/1.1\r\nHost: localhost\r\n\r\n")
            initial = b""
            while b": connected\n\n" not in initial:
                piece = stalled.recv(1)
                assert piece and len(initial) < 2048
                initial += piece
            with subscription(server, "/subscribe?after=0") as healthy:
                assert healthy.block() == ["retry: 1000", ": connected"]
                payload = "x" * 8000
                for index in range(1, 601):
                    created = publish(server, "pressure-" + str(index), payload)
                    assert created.status == 201
                    received = healthy.event()
                    assert received["id"] == str(index) and received["data"]["data"] == payload
            assert server.request("GET", "/status").json() == {"oldest": 596, "last": 600, "retained": 5}
        finally:
            stalled.close()
        observations["slow_reader"] = "600 events delivered to a healthy peer beside a stalled peer"

    # The cap reserves room for publishers, and closed clients release their slots.
    capacity_settings = dict(settings, BOARD_STATE=str(directory / "capacity.json"), BOARD_POLL="10")
    with application.server(directory, capacity_settings) as server:
        clients = []
        try:
            for _ in range(32):
                client = Subscription(server)
                clients.append(client)
                assert client.block() == ["retry: 1000", ": connected"]
            assert server.request("GET", "/subscribe").status == 503
            assert publish(server, "capacity", "publish still works").status == 201
            assert clients[-1].event()["id"] == "1"
        finally:
            for client in clients:
                client.close()
        # Releasing a disconnected quiet client can await its next heartbeat.
        time.sleep(2.2)
        with subscription(server, "/subscribe?after=1") as recovered:
            assert recovered.block() == ["retry: 1000", ": connected"]
            assert publish(server, "recovered", {}).status == 201
            assert recovered.event()["id"] == "2"
        observations["capacity"] = "32 capped subscriptions; publication and recovery passed"

    original = snapshot.read_text()
    for mutation in ["sequence", "duplicate-key", "future-time", "version"]:
        damaged = json.loads(original)
        if mutation == "sequence":
            damaged["events"][0]["id"] += 1
        elif mutation == "duplicate-key":
            damaged["events"][1]["key"] = damaged["events"][0]["key"]
        elif mutation == "future-time":
            damaged["events"][-1]["created"] = 1001
        else:
            damaged["version"] = 2
        snapshot.write_text(json.dumps(damaged))
        before = snapshot.read_bytes()
        result = application.run(directory, settings)
        assert result.returncode != 0, mutation
        assert snapshot.read_bytes() == before
    snapshot.write_text(original)
    observations["corruptions_rejected"] = 4
    return observations
