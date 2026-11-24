"""Independent struct-based DNS fixtures; no imports from application protocol code."""

from __future__ import annotations

import contextlib
import ipaddress
import json
import socket
import struct
import subprocess
import threading
from collections import Counter
from collections.abc import Callable, Iterator
from pathlib import Path

from .common import Application


def name_wire(name: str) -> bytes:
    return b"".join(bytes([len(label)]) + label.encode() for label in name.rstrip(".").split(".") if label) + b"\0"


def pointer(offset: int) -> bytes:
    return struct.pack("!H", 0xC000 | offset)


def query_fields(data: bytes) -> tuple[int, str, int]:
    identifier, flags, questions, answers, authority, additional = struct.unpack_from("!6H", data)
    assert (flags, questions, answers, authority, additional) == (0x100, 1, 0, 0, 0)
    offset = 12
    labels = []
    while data[offset]:
        length = data[offset]
        assert 1 <= length <= 63
        labels.append(data[offset + 1 : offset + 1 + length].decode("ascii"))
        offset += length + 1
    kind, category = struct.unpack_from("!HH", data, offset + 1)
    assert category == 1 and kind in {1, 28} and offset + 5 == len(data)
    name = ".".join(labels) + "."
    assert name == name.lower()
    return identifier, name, kind


def rr(owner: bytes, kind: int, value: bytes, ttl: int = 60, category: int = 1) -> bytes:
    return owner + struct.pack("!HHIH", kind, category, ttl, len(value)) + value


def response(
    query: bytes,
    answers: list[bytes] | None = None,
    *,
    flags: int = 0x8180,
    authority: list[bytes] | None = None,
    additional: list[bytes] | None = None,
) -> bytes:
    answers, authority, additional = answers or [], authority or [], additional or []
    return (
        struct.pack("!6H", int.from_bytes(query[:2]), flags, 1, len(answers), len(authority), len(additional))
        + query[12:]
        + b"".join(answers + authority + additional)
    )


def success(query: bytes) -> bytes:
    _, _, kind = query_fields(query)
    value = ipaddress.ip_address("192.0.2.7" if kind == 1 else "2001:db8::7").packed
    return response(query, [rr(pointer(12), kind, value)])


def replace_u16(data: bytes, offset: int, value: int) -> bytes:
    return data[:offset] + struct.pack("!H", value) + data[offset + 2 :]


@contextlib.contextmanager
def endpoint(handler: Callable) -> Iterator[tuple[int, list]]:
    records = []
    errors = []
    halted = threading.Event()
    with (
        socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as channel,
        socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as rogue,
        socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as other_host,
    ):
        channel.bind(("127.0.0.1", 0))
        rogue.bind(("127.0.0.1", 0))
        # Match the server's port so this packet isolates the source-IP check.
        other_host.bind(("127.0.0.2", channel.getsockname()[1]))
        channel.settimeout(0.05)
        counts = Counter()

        def serve() -> None:
            try:
                while not halted.is_set():
                    try:
                        data, source = channel.recvfrom(4096)
                    except TimeoutError:
                        continue
                    identifier, name, kind = query_fields(data)
                    counts[(name, kind)] += 1
                    records.append((name, kind, identifier, data, source))
                    handler(data, source, counts[(name, kind)], channel, rogue, other_host)
            except Exception as error:  # noqa: BLE001 - relay fixture-thread failures to the owning check
                errors.append(error)
            return  # noqa: PLR1711 - explicit return required by repository guidelines

        thread = threading.Thread(target=serve)
        thread.start()
        try:
            yield channel.getsockname()[1], records
        finally:
            halted.set()
            thread.join(timeout=3)
            assert not thread.is_alive() and not errors, errors
    return


def configuration(work: Path, server_port: int, batch: list[dict], **changes: object) -> dict[str, str]:
    work.mkdir(parents=True, exist_ok=True)
    policy = {"host": "127.0.0.1", "port": server_port, "timeout_ms": 100, "attempts": 3, "queries": batch}
    policy.update(changes)
    (work / "dns.json").write_text(json.dumps(policy))
    return {
        "DNS_CONFIG": str(work / "dns.json"),
        "DNS_REPORT": str(work / "report.json"),
        "DNS_TEXT": str(work / "report.txt"),
    }


def read_report(work: Path) -> dict:
    return json.loads((work / "report.json").read_text())


def aliases_reply(query: bytes) -> bytes:
    # Two aliases; subsequent owners point to earlier compressed RDATA or owners.
    suffix = 12 + 1 + len("alias")
    first_data = len(query) + 12
    first = rr(pointer(12), 5, b"\x04real" + pointer(suffix))
    second_owner = len(query) + len(first)
    second_data = second_owner + 12
    second = rr(pointer(first_data), 5, b"\x05final" + pointer(suffix))
    third_owner = len(query) + len(first) + len(second)
    third = rr(pointer(second_data), 1, ipaddress.IPv4Address("192.0.2.9").packed, 11)
    fourth = rr(pointer(third_owner), 1, ipaddress.IPv4Address("198.51.100.9").packed, 12)
    unrelated = rr(name_wire("unrelated.test."), 1, b"\x01\x02\x03\x04")
    return response(query, [first, second, third, fourth, unrelated], flags=0x8580)


def valid_cases(app: Application, work: Path) -> dict:
    longest = ".".join(["a" * 63, "b" * 63, "c" * 63, "d" * 61]) + "."
    queries = [
        {"name": name, "type": kind}
        for name, kind in [
            ("Direct.Test", "a"),
            ("direct.test.", "AAAA"),
            ("alias.test", "A"),
            ("case.test", "A"),
            ("escaped.test", "A"),
            ("empty.test", "A"),
            ("missing.test", "AAAA"),
            ("refused.test", "A"),
            ("truncated.test", "A"),
            ("alias-only.test", "A"),
            ("retry.test", "A"),
            (".", "A"),
            (longest, "A"),
        ]
    ]

    def answer(data: bytes, source: tuple, attempt: int, channel: socket.socket, *_: object) -> None:
        _, name, kind = query_fields(data)
        reply = success(data)
        if name == "direct.test.":
            values = ["192.0.2.1", "198.51.100.20"] if kind == 1 else ["2001:db8::1", "::1"]
            answers = [
                rr(pointer(12), kind, ipaddress.ip_address(value).packed, ttl)
                for value, ttl in zip(values, [60, 4294967295], strict=True)
            ]
            # Other classes and unknown types remain visible without becoming address answers.
            answers.append(rr(pointer(12), 1, b"\x00\xff", category=3))
            answers.append(rr(pointer(12), 65280, b"\x00\xff"))
            authority = [rr(pointer(12), 2, name_wire("ns.test."))]
            additional = [rr(name_wire("ns.test."), 1, b"\xcb\x00\x71\x01")]
            reply = response(data, answers, authority=authority, additional=additional)
        elif name == "alias.test.":
            reply = aliases_reply(data)
        elif name == "case.test.":
            reply = reply[:12] + data[12:-4].upper() + reply[len(data) - 4 :]
        elif name == "escaped.test.":
            reply = response(data, [rr(pointer(12), 1, b"\xc0\x00\x02\x07"), rr(b"\x03a.\xff\0", 16, b"\x02hi")])
        elif name == "empty.test.":
            reply = response(data)
        elif name == "missing.test.":
            soa = name_wire("ns.test.") + name_wire("admin.test.") + struct.pack("!5I", 1, 60, 60, 3600, 60)
            reply = response(data, flags=0x8183, authority=[rr(pointer(12), 6, soa)])
        elif name == "refused.test.":
            reply = response(data, flags=0x8185)
        elif name == "truncated.test.":
            reply = replace_u16(response(data, flags=0x8380), 6, 1) + b"\xc0"
        elif name == "alias-only.test.":
            reply = response(data, [rr(pointer(12), 5, name_wire("elsewhere.test."))])
        elif name == "retry.test." and attempt == 1:
            return
        channel.sendto(reply, source)
        return

    with endpoint(answer) as (port, observed):
        settings = configuration(work, port, queries)
        completed = app.run(work, settings)
        assert completed.returncode == 1, completed.stderr
    report = read_report(work)
    assert json.loads(completed.stdout) == report
    assert report["complete"] and report["planned"] == len(queries) and report["errors"] == 5
    rows = {(row["name"], row["type"]): row for row in report["results"]}
    for kind, expected in [("A", ["192.0.2.1", "198.51.100.20"]), ("AAAA", ["2001:db8::1", "::1"])]:
        row = rows[("direct.test.", kind)]
        assert [str(ipaddress.ip_address(item["address"])) for item in row["answers"]] == expected
        assert [item["ttl"] for item in row["answers"]] == [60, 4294967295]
        assert [item["section"] for item in row["records"]] == ["answer"] * 4 + ["authority", "additional"]
        assert row["records"][2]["value"] == row["records"][3]["value"] == "00ff"
        assert row["records"][4]["value"] == "ns.test."
    alias = rows[("alias.test.", "A")]
    assert alias["aliases"] == ["real.test.", "final.test."] and alias["canonical"] == "final.test."
    assert alias["authoritative"] and [r["address"] for r in alias["answers"]] == ["192.0.2.9", "198.51.100.9"]
    assert rows[("escaped.test.", "A")]["records"][1]["name"] == "a\\046\\255."
    for name, kind, status in [
        ("empty.test.", "A", "nodata"),
        ("missing.test.", "AAAA", "nxdomain"),
        ("refused.test.", "A", "dns_error"),
        ("truncated.test.", "A", "truncated"),
        ("alias-only.test.", "A", "nodata"),
    ]:
        assert rows[(name, kind)]["status"] == status and rows[(name, kind)]["answers"] == []
    for name in ["case.test.", "retry.test.", ".", longest]:
        assert rows[(name, "A")]["status"] == "ok"
    assert rows[("retry.test.", "A")]["attempts"] == 2
    assert all(row["ignored"] == {"source": 0, "id": 0, "malformed": 0} for row in rows.values())
    retries = [row for row in observed if row[0] == "retry.test."]
    assert len(retries) == 2 and retries[0][3:] == retries[1][3:]
    text = (work / "report.txt").read_text()
    assert "192.0.2.1 ttl=60" in text and "truncated.test. A: truncated" in text and "Errors: 5; complete" in text
    return {
        "queries": len(queries),
        "a_aaaa": True,
        "compressed_aliases": 2,
        "all_record_sections": True,
        "escaped_labels": True,
        "wire_name_limit": 255,
        "retry_attempts": 2,
        "negative_statuses": 5,
    }


def malformed_packet(query: bytes, case: str) -> bytes:
    valid = success(query)
    offset = len(query)
    header_changes = {
        "qr": (2, 0x0180),
        "opcode": (2, 0x8980),
        "reserved": (2, 0x81C0),
        "qd0": (4, 0),
        "qd2": (4, 2),
        "count": (6, 65),
        "missing-record": (6, 2),
    }
    if case in header_changes:
        position, value = header_changes[case]
        return replace_u16(valid, position, value)
    if case == "short":
        return query[:2] + b"\0" * 9
    if case == "name":
        other = query[:12] + name_wire("different.test.") + query[-4:]
        return success(other)
    if case == "type":
        return replace_u16(valid, offset - 4, 28)
    if case == "class":
        return replace_u16(valid, offset - 2, 3)
    if case == "rdata-long":
        return replace_u16(valid, offset + 10, 500)
    if case == "a-short":
        return response(query, [rr(pointer(12), 1, b"abc")])
    if case == "aaaa-short":
        return response(query, [rr(pointer(12), 28, b"a" * 15)])
    if case == "cname-length":
        return response(query, [rr(pointer(12), 5, pointer(12) + b"x")])
    if case == "trailing":
        return valid + b"x"
    if case == "oversized":
        return valid + b"\0" * 512
    if case == "label40":
        owner = b"\x40\0"
    elif case == "label80":
        owner = b"\x80\0"
    elif case == "label-short":
        owner = b"\x3fshort"
    elif case == "self":
        owner = pointer(offset)
    elif case == "forward":
        owner = pointer(offset + 2)
    elif case == "header":
        owner = pointer(0)
    elif case == "outside":
        owner = pointer(0x3FFF)
    elif case == "cycle":
        owner = b"\x01a" + pointer(offset)
    elif case == "expanded":
        owner = (b"\x3f" + b"a" * 63) * 4 + b"\0"
    elif case == "incomplete":
        return response(query)[:6] + struct.pack("!HHH", 1, 0, 0) + query[12:] + b"\xc0"
    elif case == "pointer-budget":
        records = []
        previous = 12
        for _ in range(33):
            part = rr(pointer(previous), 16, b"")
            previous = offset + sum(map(len, records))
            records.append(part)
        return response(query, records)
    elif case == "cname-cycle":
        return response(query, [rr(pointer(12), 5, name_wire("other.")), rr(name_wire("other."), 5, pointer(12))])
    elif case == "cname-conflict":
        return response(query, [rr(pointer(12), 5, name_wire("first.")), rr(pointer(12), 5, name_wire("second."))])
    elif case == "cname-address":
        return response(query, [rr(pointer(12), 5, name_wire("other.")), rr(pointer(12), 1, b"\x01\x02\x03\x04")])
    elif case == "cname-budget":
        records = []
        previous = 12
        for index in range(17):
            start = offset + sum(map(len, records))
            records.append(rr(pointer(previous), 5, name_wire(chr(97 + index) + ".")))
            previous = start + 12
        return response(query, records)
    else:
        raise AssertionError(case)
    return response(query, [rr(owner, 1, b"\x01\x02\x03\x04")])


def fault_cases(app: Application, work: Path) -> dict:
    cases = [
        "qr",
        "opcode",
        "reserved",
        "qd0",
        "qd2",
        "count",
        "missing-record",
        "short",
        "name",
        "type",
        "class",
        "rdata-long",
        "a-short",
        "aaaa-short",
        "cname-length",
        "trailing",
        "oversized",
        "label40",
        "label80",
        "label-short",
        "self",
        "forward",
        "header",
        "outside",
        "cycle",
        "expanded",
        "incomplete",
        "pointer-budget",
        "cname-cycle",
        "cname-conflict",
        "cname-address",
        "cname-budget",
    ]
    queries = [{"name": name + ".test.", "type": "A"} for name in cases + ["noise", "flood", "silent", "bad-only"]]

    def answer(
        data: bytes,
        source: tuple,
        attempt: int,
        channel: socket.socket,
        rogue: socket.socket,
        other_host: socket.socket,
    ) -> None:
        identifier, name, _ = query_fields(data)
        case = name.split(".")[0]
        if case == "silent":
            return
        if case == "bad-only":
            channel.sendto(malformed_packet(data, "cycle"), source)
            return
        if case == "noise":
            rogue.sendto(success(data), source)
            other_host.sendto(success(data), source)
            channel.sendto(replace_u16(success(data), 0, (identifier + 1) & 65535), source)
        elif case == "flood":
            if attempt == 1:
                for _ in range(64):
                    channel.sendto(replace_u16(success(data), 0, (identifier + 1) & 65535), source)
        else:
            channel.sendto(malformed_packet(data, case), source)
        channel.sendto(success(data), source)
        return

    with endpoint(answer) as (port, observed):
        settings = configuration(work, port, queries)
        completed = app.run(work, settings)
        assert completed.returncode == 1, completed.stderr
    report = read_report(work)
    assert report["complete"] and report["errors"] == 2 and len(report["results"]) == len(queries)
    rows = {row["name"].split(".")[0]: row for row in report["results"]}
    for case in cases:
        assert rows[case]["status"] == "ok" and rows[case]["attempts"] == 1, (case, rows[case])
        assert rows[case]["ignored"] == {"source": 0, "id": 0, "malformed": 1}, (case, rows[case])
    assert rows["noise"]["status"] == "ok" and rows["noise"]["ignored"] == {"source": 2, "id": 1, "malformed": 0}
    assert rows["flood"]["status"] == "ok" and rows["flood"]["attempts"] == 2 and rows["flood"]["ignored"]["id"] == 64
    for case in ["silent", "bad-only"]:
        assert rows[case]["status"] == "no_response" and rows[case]["attempts"] == 3
        attempts = [row for row in observed if row[0] == case + ".test."]
        assert len(attempts) == 3 and all(row[3:] == attempts[0][3:] for row in attempts)
    assert rows["bad-only"]["ignored"]["malformed"] == 3 and rows["bad-only"]["error"] == "compression pointer cycle"
    return {
        "malformed_packets_rejected": len(cases),
        "source_and_id_correlation": True,
        "per_attempt_packet_budget": 64,
        "exhaustion_attempts": 3,
        "batch_continues": True,
    }


def checkpoint(app: Application, work: Path) -> dict:
    second = threading.Event()

    def answer(data: bytes, source: tuple, _attempt: int, channel: socket.socket, *_: object) -> None:
        _, name, _ = query_fields(data)
        if name == "first.test.":
            channel.sendto(success(data), source)
        else:
            second.set()
        return  # noqa: PLR1711 - explicit return required by repository guidelines

    with endpoint(answer) as (port, _):
        settings = configuration(
            work, port, [{"name": "first.test", "type": "A"}, {"name": "second.test", "type": "AAAA"}], timeout_ms=5000
        )
        process = subprocess.Popen(
            app.command, cwd=work, env=app.environment(settings), stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        try:
            assert second.wait(4)
            report = read_report(work)
            assert not report["complete"] and report["planned"] == 2 and len(report["results"]) == 1
            assert report["results"][0]["status"] == "ok"
            process.kill()
            process.wait(timeout=3)
            assert read_report(work) == report and "partial" in (work / "report.txt").read_text()
        finally:
            if process.poll() is None:
                process.kill()
                process.wait(timeout=3)
            process.stdout.close()
            process.stderr.close()
    return {"completed_results_survive_termination": True, "partial_not_marked_complete": True}


def invalid_configuration(app: Application, work: Path) -> int:
    base = [{"name": "example.test", "type": "A"}]
    variants = [
        {"host": "localhost"},
        {"host": "::1"},
        {"host": "127.00.0.1"},
        {"host": "256.0.0.1"},
        {"port": 0},
        {"port": 65536},
        {"timeout_ms": 19},
        {"attempts": 0},
        {"attempts": True},
        {"port": 53.0},
        {"unknown": 1},
        {"queries": []},
        {"queries": base * 101},
        {"queries": [{"name": "EXAMPLE.test.", "type": "a"}] + base},
    ]
    for name in ["", "a..test", "a" * 64 + ".test", ".".join(["a" * 63] * 4), "é.test", "a\\b.test", "test.."]:
        variants.append({"queries": [{"name": name, "type": "A"}]})
    variants.extend(
        [
            {"queries": [{"name": "example.test", "type": "MX"}]},
            {"queries": [{"name": "example.test", "type": "A", "extra": 1}]},
        ]
    )
    for index, changes in enumerate(variants):
        folder = work / str(index)
        settings = configuration(folder, 53, base, **changes)
        for path in [Path(settings["DNS_REPORT"]), Path(settings["DNS_TEXT"])]:
            path.write_text("preserved")
        assert app.run(folder, settings).returncode != 0
        assert Path(settings["DNS_REPORT"]).read_text() == Path(settings["DNS_TEXT"]).read_text() == "preserved"
    settings = configuration(work / "paths", 53, base)
    original = Path(settings["DNS_CONFIG"]).read_bytes()
    assert app.run(work / "paths", dict(settings, DNS_REPORT=settings["DNS_CONFIG"])).returncode != 0
    output = Path(settings["DNS_REPORT"])
    output.symlink_to(settings["DNS_CONFIG"])
    assert app.run(work / "paths", settings).returncode != 0
    assert Path(settings["DNS_CONFIG"]).read_bytes() == original
    output.unlink()
    output.hardlink_to(settings["DNS_CONFIG"])
    assert app.run(work / "paths", settings).returncode != 0 and Path(settings["DNS_CONFIG"]).read_bytes() == original
    return len(variants) + 3


def check(app: Application, work: Path) -> dict:
    return {
        "valid": valid_cases(app, work / "valid"),
        "faults": fault_cases(app, work / "faults"),
        "checkpoint": checkpoint(app, work / "checkpoint"),
        "invalid_configuration": invalid_configuration(app, work / "invalid"),
    }
