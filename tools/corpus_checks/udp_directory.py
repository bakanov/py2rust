"""Independent UDP peers, deterministic expiry, discovery paging and retry/correlation faults."""

from __future__ import annotations

import json
import socket
import threading
import time
from pathlib import Path

from .common import Application, Server


def announce(service_id: str, sequence: int = 1, **changes: object) -> dict:
    value = {
        "op": "announce",
        "request": service_id + "-" + str(sequence),
        "id": service_id,
        "seq": sequence,
        "service": "chat",
        "name": "Комната 🌍",
        "port": 8765,
        "ttl_ms": 1000,
        "tags": ["web", "desktop"],
    }
    value.update(changes)
    return value


def fixture(work: Path, **changes: int) -> dict[str, str]:
    work.mkdir(parents=True, exist_ok=True)
    policy = {"max_services": 30, "remember_ms": 500, "max_datagram": 1024, "reply_ms": 120, "attempts": 3}
    policy.update(changes)
    (work / "directory.json").write_text(json.dumps(policy))
    (work / "clock.json").write_text("1000000")
    return {
        "DIR_MODE": "serve",
        "DIR_PORT": "0",
        "DIR_CONFIG": str(work / "directory.json"),
        "DIR_CLOCK": str(work / "clock.json"),
        "DIR_REGISTRY": str(work / "registry.json"),
        "DIR_STOP": str(work / "stop"),
    }


def clock(work: Path, value: int) -> None:
    # Publish clock changes atomically while the directory's expiry loop reads it.
    (work / "clock.new").write_text(str(value))
    (work / "clock.new").replace(work / "clock.json")
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def peer(host: str = "127.0.0.1") -> socket.socket:
    channel = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    channel.bind((host, 0))
    channel.settimeout(3)
    return channel


def exchange(channel: socket.socket, port: int, request: dict | bytes) -> dict:
    payload = (
        json.dumps(request, ensure_ascii=False, separators=(",", ":")).encode()
        if isinstance(request, dict)
        else request
    )
    channel.sendto(payload, ("127.0.0.1", port))
    data, origin = channel.recvfrom(8192)
    assert origin == ("127.0.0.1", port)
    assert len(data) <= 1024
    response = json.loads(data)
    if isinstance(request, dict) and isinstance(request.get("request"), str):
        assert response["request"] == request["request"]
    return response


def discovery(channel: socket.socket, port: int, **options: object) -> dict:
    return exchange(channel, port, dict(op="discover", request="query", **options))


def registry(work: Path) -> dict:
    return json.loads((work / "registry.json").read_text())


def await_registry(work: Path, active: int, expired: int) -> dict:
    until = time.monotonic() + 2
    while time.monotonic() < until:
        current = registry(work)
        if len(current["services"]) == active and current["expired"] == expired:
            return current
        time.sleep(0.01)
    raise AssertionError(registry(work))


def stop(server: Server, settings: dict[str, str]) -> None:
    Path(settings["DIR_STOP"]).touch()
    assert server.process.wait(timeout=3) == 0
    Path(settings["DIR_STOP"]).unlink()
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def ordering_and_expiry(app: Application, work: Path) -> dict:
    settings = fixture(work, max_services=2)
    with app.server(work, settings) as server, peer() as channel, peer("127.0.0.2") as other_host:
        first = exchange(channel, server.port, announce("team", 2))
        assert first["ok"] and not first["duplicate"] and first["active"]
        service = first["service"]
        assert service["expires_ms"] == 1001000 and service["host"] == "127.0.0.1"
        assert service["tags"] == ["desktop", "web"] and service["name"] == "Комната 🌍"
        clock(work, 1000500)
        duplicate = exchange(channel, server.port, announce("team", 2, request="retry", tags=["desktop", "web"]))
        assert duplicate["duplicate"] and duplicate["service"] == service
        assert exchange(channel, server.port, announce("team", 1))["error"] == "stale_sequence"
        assert exchange(channel, server.port, announce("team", 2, port=8766))["error"] == "sequence_conflict"
        assert exchange(other_host, server.port, announce("team", 2))["error"] == "sequence_conflict"
        assert discovery(channel, server.port)["services"] == [service]
        clock(work, 1000999)
        assert len(discovery(channel, server.port)["services"]) == 1
        clock(work, 1001000)
        assert discovery(channel, server.port)["services"] == []
        assert await_registry(work, 0, 1)["retained"] == 1
        expired_duplicate = exchange(channel, server.port, announce("team", 2))
        assert expired_duplicate["duplicate"] and not expired_duplicate["active"]
        clock(work, 1000000)
        assert discovery(channel, server.port)["services"] == []
        renewed = exchange(channel, server.port, announce("team", 3, port=8766))
        assert renewed["active"] and renewed["service"]["expires_ms"] == 1002000
        assert exchange(other_host, server.port, announce("files", 1, service="files", ttl_ms=50))["ok"]
        assert registry(work)["services"][0]["host"] == "127.0.0.2"
        assert exchange(channel, server.port, announce("third"))["error"] == "retained_capacity"
        clock(work, 1001050)
        assert await_registry(work, 1, 1)["retained"] == 2
        assert exchange(channel, server.port, announce("third"))["error"] == "retained_capacity"
        clock(work, 1001550)
        assert await_registry(work, 1, 0)["retained"] == 1
        assert exchange(channel, server.port, announce("third"))["ok"]
        assert len(discovery(channel, server.port, service="files")["services"]) == 0
        stop(server, settings)
    with app.server(work, settings) as server, peer() as channel:
        assert discovery(channel, server.port)["services"] == []
        assert registry(work) == {"services": [], "retained": 0, "expired": 0}
        stop(server, settings)
    return {
        "duplicate_no_refresh": True,
        "stale_conflict_isolation": True,
        "exact_expiry": True,
        "rollback": True,
        "retained_capacity": True,
        "restart_is_empty": True,
    }


def pagination(app: Application, work: Path) -> dict:
    settings = fixture(work)
    expected = []
    with app.server(work, settings) as server, peer() as channel:
        for index in range(15):
            name = "service-" + str(index).zfill(2)
            request = announce(name, name="界" * 26 + "ab", tags=[str(n).zfill(16) for n in range(8)], ttl_ms=30000)
            response = exchange(channel, server.port, request)
            assert response["ok"]
            expected.append(response["service"])
        collected = []
        after = ""
        pages = 0
        while True:
            response = discovery(channel, server.port, after=after, limit=20)
            assert response["ok"] and response["services"]
            collected.extend(response["services"])
            assert response["next"] > after
            after = response["next"]
            pages += 1
            if not response["more"]:
                break
            assert pages <= 15
        assert collected == expected and pages > 1
        assert len(discovery(channel, server.port, limit=1)["services"]) == 1
        assert discovery(channel, server.port, after="zzzz")["services"] == []
        assert discovery(channel, server.port, service="absent")["services"] == []
        assert registry(work)["services"] == expected
        stop(server, settings)
    return {"services": 15, "size_bounded_pages": pages, "ordered_complete_scan": True}


def malformed(app: Application, work: Path) -> dict:
    settings = fixture(work)
    variants = [
        {"port": 0},
        {"port": True},
        {"seq": 0},
        {"seq": 1.5},
        {"ttl_ms": 49},
        {"ttl_ms": 30001},
        {"tags": ["a", "a"]},
        {"tags": ["A"]},
        {"tags": [str(i) for i in range(9)]},
        {"name": "bad\x00name"},
        {"name": "界" * 27},
        {"service": "Bad Type"},
        {"id": "../bad"},
        {"extra": "unexpected"},
    ]
    with app.server(work, settings) as server, peer() as channel:
        assert exchange(channel, server.port, announce("kept"))["ok"]
        before = registry(work)
        for changes in variants:
            request = announce("broken")
            request.update(changes)
            assert not exchange(channel, server.port, request)["ok"]
            assert registry(work) == before
        for raw in [b"", b"\xff", b"{", b"[]", b"true", b"{}", b'{"request":"truncated"}' + b" " * 1500]:
            assert not exchange(channel, server.port, raw)["ok"]
            assert registry(work) == before
        for options in [{"limit": 0}, {"limit": 21}, {"limit": True}, {"after": "../bad"}, {"extra": 1}]:
            assert not discovery(channel, server.port, **options)["ok"]
        assert exchange(channel, server.port, {"op": "other", "request": "unknown"})["error"] == "unknown_operation"
        stop(server, settings)
    return {"announcement_rejections": len(variants), "malformed_datagrams": 7, "discovery_rejections": 5}


def live_expiry(app: Application, work: Path) -> dict:
    settings = fixture(work)
    settings["DIR_CLOCK"] = ""
    with app.server(work, settings) as server, peer() as channel:
        assert exchange(channel, server.port, announce("brief", ttl_ms=100))["active"]
        await_registry(work, 0, 1)
        await_registry(work, 0, 0)
        assert discovery(channel, server.port)["services"] == []
        stop(server, settings)
    return {"expiry_without_queries": True, "retirement_without_queries": True}


def client_settings(work: Path, server_settings: dict[str, str], port: int, requests: list[dict]) -> dict[str, str]:
    work.mkdir(parents=True, exist_ok=True)
    (work / "requests.json").write_text(json.dumps(requests, ensure_ascii=False))
    return dict(
        server_settings,
        DIR_MODE="client",
        DIR_PORT=str(port),
        DIR_REQUESTS=str(work / "requests.json"),
        DIR_REPORT=str(work / "client-report.json"),
    )


def client_faults(app: Application, work: Path) -> dict:
    settings = fixture(work)
    request = {"op": "discover", "request": "lookup", "limit": 20}
    observed = []
    errors = []
    with peer() as remote, peer() as rogue:
        remote.settimeout(2)
        port = remote.getsockname()[1]

        def respond() -> None:
            try:
                for index in range(2):
                    raw, source = remote.recvfrom(4096)
                    observed.append(raw)
                    assert json.loads(raw) == request
                    response = {"ok": True, "request": "lookup", "services": [], "next": "", "more": False}
                    if index == 0:
                        rogue.sendto(json.dumps(response).encode(), source)
                        remote.sendto(json.dumps(dict(response, request="old")).encode(), source)
                        remote.sendto(b'{"request":"lookup","ok":1}', source)
                        remote.sendto(b"not-json", source)
                        remote.sendto(json.dumps(response).encode() + b" " * 1100, source)
                    else:
                        remote.sendto(json.dumps(response).encode(), source)
            except Exception as error:  # noqa: BLE001 - forward fixture-thread failures
                errors.append(error)
            return  # noqa: PLR1711 - explicit return required by repository guidelines

        worker = threading.Thread(target=respond)
        worker.start()
        client = client_settings(work / "retry", settings, port, [request])
        completed = app.run(work / "retry", client)
        worker.join(timeout=3)
        assert not worker.is_alive() and not errors, errors
        assert completed.returncode == 0, completed.stderr
        report = json.loads(Path(client["DIR_REPORT"]).read_text())
        assert report["complete"] and report["errors"] == 0
        assert report["results"][0]["attempts"] == 2 and len(observed) == 2 and observed[0] == observed[1]
    with peer() as silent:
        client = client_settings(work / "silent", settings, silent.getsockname()[1], [request])
        began = time.monotonic()
        completed = app.run(work / "silent", client)
        elapsed = time.monotonic() - began
        assert completed.returncode == 1 and elapsed >= 0.3 and elapsed < 3
        report = json.loads(Path(client["DIR_REPORT"]).read_text())
        assert report["complete"] and report["errors"] == 1
        assert report["results"][0]["attempts"] == 3 and report["results"][0]["reply"] is None
    return {"retry_identical_payload": True, "wrong_source_nonce_type_truncation_rejected": True, "exhaustion": 3}


def client_server(server_app: Application, client_app: Application, work: Path) -> dict:
    settings = fixture(work)
    requests = [
        announce("team", 2),
        announce("team", 2, request="duplicate", tags=["desktop", "web"]),
        announce("team", 1),
        announce("team", 3, port=9000),
        {"op": "discover", "request": "find"},
    ]
    with server_app.server(work, settings) as server:
        client = client_settings(work / "client", settings, server.port, requests)
        completed = client_app.run(work / "client", client)
        assert completed.returncode == 1, completed.stderr
        report = json.loads(Path(client["DIR_REPORT"]).read_text())
        assert report["complete"] and report["errors"] == 1 and len(report["results"]) == 5
        replies = [item["reply"] for item in report["results"]]
        assert replies[0]["ok"] and not replies[0]["duplicate"]
        assert replies[1]["duplicate"] and replies[1]["service"] == replies[0]["service"]
        assert replies[2]["error"] == "stale_sequence"
        assert replies[3]["service"]["seq"] == 3 and replies[3]["service"]["port"] == 9000
        assert replies[4]["services"] == [replies[3]["service"]]
        assert registry(work)["services"] == replies[4]["services"]
        stop(server, settings)
    return {"requests": 5, "accepted": 4, "rejected": 1, "final_sequence": 3, "duplicate_lease_unchanged": True}


def lost_acknowledgement(server_app: Application, client_app: Application, work: Path) -> dict:
    """Drop an actual accepted announcement's reply, then relay the client's retry."""
    settings = fixture(work, reply_ms=250)
    request = announce("lost-ack", 2)
    observed = []
    replies = []
    errors = []
    with server_app.server(work, settings) as server, peer() as proxy, peer() as upstream:

        def relay() -> None:
            try:
                for index in range(2):
                    raw, source = proxy.recvfrom(4096)
                    observed.append(raw)
                    assert json.loads(raw) == request
                    upstream.sendto(raw, ("127.0.0.1", server.port))
                    response, origin = upstream.recvfrom(4096)
                    assert origin == ("127.0.0.1", server.port)
                    replies.append(json.loads(response))
                    if index == 0:
                        # The first lease was accepted but its acknowledgement is lost.
                        clock(work, 1000050)
                    else:
                        proxy.sendto(response, source)
            except Exception as error:  # noqa: BLE001 - forward fixture-thread failures
                errors.append(error)
            return  # noqa: PLR1711 - explicit return required by repository guidelines

        worker = threading.Thread(target=relay)
        worker.start()
        settings_client = client_settings(work / "client", settings, proxy.getsockname()[1], [request])
        completed = client_app.run(work / "client", settings_client)
        worker.join(timeout=4)
        assert not worker.is_alive() and not errors, errors
        assert completed.returncode == 0, completed.stderr
        report = json.loads(Path(settings_client["DIR_REPORT"]).read_text())
        assert report["complete"] and report["errors"] == 0 and len(report["results"]) == 1
        result = report["results"][0]
        assert len(observed) == 2 and observed[0] == observed[1]
        assert result["attempts"] == 2 and result["accepted"] and result["reply"] == replies[1]
        assert not replies[0]["duplicate"] and replies[1]["duplicate"]
        assert replies[0]["service"] == replies[1]["service"]
        assert replies[1]["service"]["expires_ms"] == 1001000
        assert registry(work)["services"] == [replies[0]["service"]]
        stop(server, settings)
    return {"accepted_before_lost_ack": True, "retry_attempts": 2, "duplicate_no_refresh": True}


def invalid_configuration(app: Application, work: Path) -> int:
    changes = [
        {"max_services": 0},
        {"max_services": 101},
        {"remember_ms": 99},
        {"remember_ms": 3600001},
        {"max_datagram": 1023},
        {"max_datagram": 4097},
        {"reply_ms": 19},
        {"attempts": 0},
        {"attempts": True},
        {"max_services": 1.5},
        {"unknown": 1},
    ]
    for index, change in enumerate(changes):
        folder = work / str(index)
        settings = fixture(folder, **change)
        assert app.run(folder, settings).returncode != 0
    folder = work / "paths"
    settings = fixture(folder)
    original = Path(settings["DIR_CONFIG"]).read_bytes()
    assert app.run(folder, dict(settings, DIR_REGISTRY=settings["DIR_CONFIG"])).returncode != 0
    assert Path(settings["DIR_CONFIG"]).read_bytes() == original
    output = Path(settings["DIR_REGISTRY"])
    output.symlink_to(settings["DIR_CONFIG"])
    assert app.run(folder, settings).returncode != 0 and Path(settings["DIR_CONFIG"]).read_bytes() == original
    output.unlink()
    clock(folder, -1)
    assert app.run(folder, settings).returncode != 0
    client = client_settings(folder / "bad-client", settings, 8790, [{"op": "discover", "request": "x"}] * 2)
    report = Path(client["DIR_REPORT"])
    report.write_text("keep")
    assert app.run(folder / "bad-client", client).returncode != 0 and report.read_text() == "keep"
    return len(changes) + 4


def check(app: Application, work: Path) -> dict:
    return {
        "ordering": ordering_and_expiry(app, work / "ordering"),
        "pagination": pagination(app, work / "pagination"),
        "malformed": malformed(app, work / "malformed"),
        "live_expiry": live_expiry(app, work / "live"),
        "client_faults": client_faults(app, work / "faults"),
        "paired": client_server(app, app, work / "paired"),
        "lost_ack": lost_acknowledgement(app, app, work / "lost-ack"),
        "invalid_configuration": invalid_configuration(app, work / "invalid"),
    }
