"""Independent SMTP clients, exact byte oracles and durable-publication boundaries."""

from __future__ import annotations

import hashlib
import json
import smtplib
import socket
import time
from email import policy as email_policy
from email.message import EmailMessage
from email.parser import BytesParser
from pathlib import Path

from .common import Application, Server


class Peer:
    def __init__(self, port: int) -> None:
        self.socket = socket.create_connection(("127.0.0.1", port), timeout=3)
        self.reader = self.socket.makefile("rb")
        assert self.response()[0] == 220

    def close(self) -> None:
        self.reader.close()
        self.socket.close()
        return  # noqa: PLR1711 - explicit return required by repository guidelines

    def response(self) -> tuple[int, bytes]:
        lines = []
        while True:
            line = self.reader.readline(4096)
            assert len(line) >= 5 and line.endswith(b"\r\n"), line
            code = int(line[:3])
            if lines:
                assert code == int(lines[0][:3]), lines
            lines.append(line)
            if line[3:4] == b" ":
                return code, b"".join(lines)
            assert line[3:4] == b"-", line

    def command(self, command: bytes, expected: int) -> bytes:
        self.socket.sendall(command + b"\r\n")
        code, text = self.response()
        assert code == expected, (command, code, text)
        return text

    def start(self, options: bytes = b"") -> None:
        self.command(b"EHLO fixture.local", 250)
        self.command(b"MAIL FROM:<Sender@Example.TEST>" + options, 250)
        self.command(b"RCPT TO:<recipient@example.test>", 250)
        self.command(b"DATA", 354)
        return  # noqa: PLR1711 - explicit return required by repository guidelines


def fixture(work: Path, **changes: int) -> dict[str, str]:
    work.mkdir(parents=True, exist_ok=True)
    policy = {
        "max_bytes": 8192,
        "max_messages": 20,
        "max_recipients": 3,
        "command_ms": 1500,
        "data_ms": 1500,
        "max_commands": 100,
    }
    policy.update(changes)
    config = work / "smtp.json"
    config.write_text(json.dumps(policy))
    return {
        "SMTP_CONFIG": str(config),
        "SMTP_DATA": str(work / "messages"),
        "SMTP_PORT": "0",
        "SMTP_SHUTDOWN": str(work / "shutdown"),
        "SMTP_FAULT": "",
    }


def records(work: Path) -> list[dict]:
    path = work / "messages/index.json"
    if not path.exists():
        return []
    value = json.loads(path.read_text())
    assert value["format"] == 1
    result = value["messages"]
    assert len({row["id"] for row in result}) == len(result)
    for row in result:
        content = (work / "messages" / (row["id"] + ".eml")).read_bytes()
        assert row["size"] == len(content)
        assert row["sha256"] == hashlib.sha256(content).hexdigest()
        assert row["received"].endswith("+00:00")
    return result


def content(work: Path, index: int) -> bytes:
    return (work / "messages" / (records(work)[index]["id"] + ".eml")).read_bytes()


def stop(server: Server, settings: dict[str, str]) -> None:
    Path(settings["SMTP_SHUTDOWN"]).touch()
    assert server.process.wait(timeout=3) == 0
    Path(settings["SMTP_SHUTDOWN"]).unlink()
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def delivery(app: Application, work: Path) -> dict:
    settings = fixture(work)
    attachment = bytes(range(256))
    message = EmailMessage(policy=email_policy.SMTP)
    message["From"] = "sender@example.test"
    message["To"] = "first@example.test"
    message["Subject"] = "Captured attachment"
    message.set_content("Hello\n.leading dot\n..two dots\n.\n")
    message.add_attachment(attachment, maintype="application", subtype="octet-stream", filename="fixture.bin")
    message.set_boundary("independent-fixture-boundary")
    mime = message.as_bytes()
    unicode_body = "Subject: Eight bit\r\n\r\nПривет 🌍\r\n.dot\r\n..two\r\n.\r\n".encode()
    with app.server(work, settings) as server:
        with smtplib.SMTP("127.0.0.1", server.port, timeout=3) as client:
            assert client.ehlo("fixture.local")[0] == 250
            assert client.esmtp_features == {"size": "8192", "8bitmime": ""}
            assert client.sendmail("Sender@Example.TEST", ["first@example.test", "second@example.test"], mime) == {}
            assert client.sendmail("", ["first@example.test"], unicode_body, mail_options=["BODY=8BITMIME"]) == {}
            assert client.noop()[0] == 250
        saved = records(work)
        assert len(saved) == 2 and content(work, 0) == mime and content(work, 1) == unicode_body
        assert saved[0]["from"] == "Sender@example.test"
        assert saved[0]["recipients"] == ["first@example.test", "second@example.test"]
        assert saved[1]["from"] == "" and saved[1]["body"] == "8BITMIME"
        parsed = BytesParser(policy=email_policy.default).parsebytes(content(work, 0))
        assert next(parsed.iter_attachments()).get_payload(decode=True) == attachment
        before = (work / "messages/index.json").read_bytes()
        stop(server, settings)
    with app.server(work, settings) as server:
        assert (work / "messages/index.json").read_bytes() == before
        with smtplib.SMTP("127.0.0.1", server.port, timeout=3) as client:
            assert client.helo("legacy.local")[0] == 250
            assert (
                client.sendmail("legacy@example.test", ["third@example.test"], b"Subject: Legacy\r\n\r\nOK\r\n") == {}
            )
        stop(server, settings)
    assert len(records(work)) == 3
    return {
        "messages": 3,
        "exact_mime": True,
        "exact_8bit": True,
        "attachment_sha256": hashlib.sha256(attachment).hexdigest(),
    }


def commands(app: Application, work: Path) -> dict:
    settings = fixture(work, max_recipients=2)
    with app.server(work, settings) as server:
        peer = Peer(server.port)
        cases = [
            (b"MAIL FROM:<a@example.test>", 503),
            (b"RSET", 250),
            (b"RCPT TO:<b@example.test>", 503),
            (b"DATA", 503),
            (b"EHLO", 501),
            (b"EHLO valid.local", 250),
            (b"DATA x", 501),
            (b"AUTH PLAIN", 502),
            (b"STARTTLS", 502),
            (b"NOOP any argument", 250),
            (b"MAIL FROM:<bad..dots@example.test>", 501),
            (b"MAIL FROM:<a@-bad.test>", 501),
            (b"MAIL FROM:<a@example.test> SIZE=8193", 552),
            (b"MAIL FROM:<a@example.test> SIZE=-1", 501),
            (b"MAIL FROM:<a@example.test> SIZE=1 SIZE=2", 501),
            (b"MAIL FROM:<a@example.test> BODY=BINARYMIME", 501),
            (b"MAIL FROM:<a@example.test> SMTPUTF8", 501),
            (b"MAIL FROM:<a@example.test> UNKNOWN=1", 555),
            (b"MAIL FROM:<a@example.test>SIZE=1", 501),
            (b"MAIL FROM:<a@example.test> ", 501),
            (b"MAIL FROM:<a@example.test> SIZE=0001", 250),
            (b"MAIL FROM:<other@example.test>", 503),
            (b"RCPT TO:<>", 501),
            (b"RCPT TO:<b@example.test> NOTIFY=SUCCESS", 555),
            (b"RCPT TO:<b@Example.TEST>", 250),
            (b"RCPT TO:<b@example.test>", 250),
            (b"RCPT TO:<c@example.test>", 250),
            (b"RCPT TO:<d@example.test>", 452),
            (b"EHLO replacement.local", 250),
            (b"DATA", 503),
            (b"HELO legacy.local", 250),
            (b"MAIL FROM:<a@example.test> BODY=7BIT", 555),
            (b"MAIL FROM:<>", 250),
            (b"RSET", 250),
            (b"RCPT TO:<b@example.test>", 503),
            (b"RSET extra", 501),
            (b"\xff", 500),
            (b"NOOP\tbad", 500),
            (b"QUIT extra", 501),
        ]
        for command, code in cases:
            peer.command(command, code)
        peer.socket.sendall(b"eHlO fixture.local\r\nmail FROM:<a@example.test>\r\nRCPT TO:<b@example.test>\r\nDATA\r\n")
        for code in [250, 250, 250, 354]:
            assert peer.response()[0] == code
        peer.socket.sendall(b"Subject: Split\r")
        time.sleep(0.015)
        peer.socket.sendall(b"\n\r\n..dot\r\n.\r\nNOOP\r\nQUIT\r\n")
        for code in [250, 250, 221]:
            assert peer.response()[0] == code
        assert peer.reader.read(1) == b""
        peer.close()
        assert content(work, 0) == b"Subject: Split\r\n\r\n.dot\r\n"
        assert len(records(work)) == 1
        stop(server, settings)
    return {"command_cases": len(cases), "coalesced_and_fragmented": True, "state_reset": True}


def boundaries(app: Application, work: Path) -> dict:
    settings = fixture(work, max_bytes=64, max_messages=2)
    with app.server(work, settings) as server:
        peer = Peer(server.port)
        peer.start()
        peer.socket.sendall(b"x" * 64 + b"\r\n.\r\n")
        assert peer.response()[0] == 552
        for bad in [b"high\xff\r\n", b"null\x00byte\r\n"]:
            peer.start()
            peer.socket.sendall(bad + b".\r\n")
            assert peer.response()[0] == 554
        peer.start()
        peer.socket.sendall(b"x" * 62 + b"\r\n.\r\n")
        assert peer.response()[0] == 250
        peer.start(b" BODY=8BITMIME")
        peer.socket.sendall(b"\xff\xfe\r\n.\r\n")
        assert peer.response()[0] == 250
        peer.command(b"MAIL FROM:<>", 250)
        peer.command(b"RCPT TO:<a@example.test>", 250)
        peer.command(b"DATA", 452)
        peer.command(b"QUIT", 221)
        peer.close()
        assert len(records(work)) == 2 and content(work, 0) == b"x" * 62 + b"\r\n"
        assert content(work, 1) == b"\xff\xfe\r\n"
        stop(server, settings)
    long_work = work / "lines"
    settings = fixture(long_work)
    with app.server(long_work, settings) as server:
        peer = Peer(server.port)
        peer.start()
        peer.socket.sendall(b".." + b"x" * 997 + b"\r\n.\r\n")
        assert peer.response()[0] == 250
        peer.command(b"QUIT", 221)
        peer.close()
        assert content(long_work, 0) == b"." + b"x" * 997 + b"\r\n"
        for bad in [b"x" * 999 + b"\r\n", b"bare\n", b"bare\rreturn\r\n"]:
            peer = Peer(server.port)
            peer.start()
            peer.socket.sendall(bad)
            assert peer.response()[0] == 421
            peer.close()
        peer = Peer(server.port)
        peer.socket.sendall(b"x" * 554)
        assert peer.response()[0] == 421
        peer.close()
        peer = Peer(server.port)
        peer.start()
        peer.socket.sendall(b"unfinished\r\n")
        peer.socket.shutdown(socket.SHUT_WR)
        assert peer.response()[0] == 421
        peer.close()
        assert len(records(long_work)) == 1
        stop(server, settings)
    return {"message_limit": True, "capacity": True, "line_limit": True, "rejected_bodies": 3, "truncation": True}


def timeouts(app: Application, work: Path) -> dict:
    settings = fixture(work, command_ms=120, data_ms=180, max_commands=5)
    with app.server(work, settings) as server:
        for mode in ["command", "data"]:
            peer = Peer(server.port)
            if mode == "data":
                peer.start()
            began = time.monotonic()
            for index in range(10):
                try:
                    peer.socket.sendall(b"x")
                except OSError:
                    break
                time.sleep(0.03)
            assert peer.response()[0] == 421
            assert time.monotonic() - began < 0.8
            peer.close()
        peer = Peer(server.port)
        for index in range(5):
            peer.command(b"NOOP", 250)
        assert peer.response()[0] == 421
        peer.close()
        assert not records(work)
        stop(server, settings)
    return {"absolute_command_deadline": True, "absolute_data_deadline": True, "command_budget": True}


def interruptions(app: Application, work: Path) -> dict:
    body = b"Subject: Durable\r\n\r\nCapture me\r\n"
    for boundary in ["before_message", "after_message", "after_index", "after_reply"]:
        folder = work / boundary
        settings = fixture(folder)
        with app.server(folder, dict(settings, SMTP_FAULT=boundary)) as server:
            peer = Peer(server.port)
            peer.start()
            peer.socket.sendall(body + b".\r\n")
            if boundary == "after_reply":
                assert peer.response()[0] == 250
            else:
                assert peer.reader.read(1) == b""
            assert server.process.wait(timeout=3) == 75
            peer.close()
        committed = boundary in {"after_index", "after_reply"}
        assert len(records(folder)) == int(committed)
        if boundary == "after_message":
            assert len(list((folder / "messages").glob("*.eml"))) == 1
        with app.server(folder, settings) as server:
            assert len(list((folder / "messages").glob("*.eml"))) == int(committed)
            if committed:
                assert content(folder, 0) == body
            with smtplib.SMTP("127.0.0.1", server.port, timeout=3) as client:
                assert client.sendmail("a@example.test", ["b@example.test"], body) == {}
            assert len(records(folder)) == int(committed) + 1
            stop(server, settings)
    folder = work / "kill"
    settings = fixture(folder)
    with app.server(folder, settings) as server:
        peer = Peer(server.port)
        peer.start()
        peer.socket.sendall(body)
        server.process.kill()
        assert server.process.wait(timeout=3) != 0
        peer.close()
    with app.server(folder, settings) as server:
        assert not records(folder) and not list((folder / "messages").glob("*.eml"))
        stop(server, settings)
    return {"publication_boundaries": 4, "real_process_kill": True, "orphan_recovery": True}


def corruption(app: Application, work: Path) -> dict:
    settings = fixture(work)
    with app.server(work, settings) as server:
        with smtplib.SMTP("127.0.0.1", server.port, timeout=3) as client:
            assert client.sendmail("a@example.test", ["b@example.test"], b"OK\r\n") == {}
        stop(server, settings)
    index = work / "messages/index.json"
    original = index.read_bytes()
    row = records(work)[0]
    message = work / "messages" / (row["id"] + ".eml")
    message.write_bytes(b"NO\r\n")
    assert app.run(work, settings).returncode != 0
    assert index.read_bytes() == original and message.read_bytes() == b"NO\r\n"
    message.unlink()
    assert app.run(work, settings).returncode != 0
    outside = work / "outside.eml"
    outside.write_bytes(b"OK\r\n")
    message.symlink_to(outside)
    assert app.run(work, settings).returncode != 0 and outside.read_bytes() == b"OK\r\n"
    message.unlink()
    message.write_bytes(b"OK\r\n")
    extra = work / "messages/do-not-delete.txt"
    extra.write_text("preserve")
    assert app.run(work, settings).returncode != 0 and extra.read_text() == "preserve"
    extra.unlink()
    malformed = json.loads(original)
    malformed["messages"][0]["size"] = True
    index.write_text(json.dumps(malformed))
    assert app.run(work, settings).returncode != 0
    index.write_bytes(original)
    index.unlink()
    saved_index = work / "saved-index.json"
    saved_index.write_bytes(original)
    index.symlink_to(saved_index)
    assert app.run(work, settings).returncode != 0 and saved_index.read_bytes() == original
    return {"corruption_cases": 6, "preserved_external_files": True}


def invalid_configuration(app: Application, work: Path) -> int:
    bad = [
        {"max_bytes": 63},
        {"max_bytes": 1048577},
        {"max_messages": 0},
        {"max_recipients": 101},
        {"command_ms": 49},
        {"data_ms": 60001},
        {"max_commands": 4},
        {"max_bytes": True},
        {"max_messages": 1.5},
        {"unknown": 1},
    ]
    for index, changes in enumerate(bad):
        folder = work / str(index)
        settings = fixture(folder, **changes)
        assert app.run(folder, settings).returncode != 0
    return len(bad)


def check(app: Application, work: Path) -> dict:
    return {
        "delivery": delivery(app, work / "delivery"),
        "commands": commands(app, work / "commands"),
        "boundaries": boundaries(app, work / "bounds"),
        "timeouts": timeouts(app, work / "timeouts"),
        "interruptions": interruptions(app, work / "interruptions"),
        "corruption": corruption(app, work / "corruption"),
        "invalid_configuration": invalid_configuration(app, work / "invalid"),
    }
