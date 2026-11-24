"""A bounded HTTP/1.1 upgrade with loopback hosts and same-origin browser access."""

from peers import Peer, enqueue

from py2rust.stdlib import (
    base64_decode,
    base64_encode,
    monotonic,
    regex_fullmatch,
    sha1_digest,
)


def http_reply(peer: Peer, status: str, body: bytes, policy: dict[str, int], extra: str) -> Peer:
    header: str = (
        "HTTP/1.1 " + status + "\r\nConnection: close\r\nContent-Length: " + str(len(body)) + "\r\n" + extra + "\r\n"
    )
    peer = enqueue(peer, header.encode() + body, policy)
    if peer.phase != "dead":
        peer.phase = "closing"
        peer.ack = True
        peer.deadline = monotonic() + float(policy["close_ms"]) * 0.001
    return peer


def upgrade(peer: Peer, peers: dict[str, Peer], home: bytes, policy: dict[str, int]) -> Peer:
    end: int = peer.incoming.find(b"\r\n\r\n")
    if (end < 0 and len(peer.incoming) > 8192) or end + 4 > 8192:
        return http_reply(peer, "431 Headers Too Large", b"Header limit\n", policy, "")
    if end < 0:
        return peer
    lines: list[str] = peer.incoming[:end].decode().split("\r\n")
    assert len(lines) <= 65, "too many HTTP headers"
    request: list[str] = lines[0].split(" ")
    assert len(request) == 3 and request[0] == "GET" and request[2] == "HTTP/1.1", "expected HTTP/1.1 GET"
    headers: dict[str, str] = {}
    for line in lines[1:]:
        colon: int = line.find(":")
        assert colon > 0 and regex_fullmatch("[A-Za-z0-9-]+", line[:colon]), "invalid header name"
        assert regex_fullmatch("[\\x20-\\x7e\\t]*", line[colon + 1 :]), "invalid header value"
        name: str = line[:colon].lower()
        assert name not in headers, "duplicate HTTP header"
        headers[name] = line[colon + 1 :].strip()
    host: str = headers.get("host", "").lower()
    allowed: list[str] = ["127.0.0.1:" + str(policy["port"]), "localhost:" + str(policy["port"])]
    if policy["port"] == 80:
        allowed.extend(["127.0.0.1", "localhost"])
    assert (
        host in allowed and "transfer-encoding" not in headers and headers.get("content-length", "0") == "0"
    ), "invalid host or body framing"
    peer.incoming = peer.incoming[end + 4 :]
    if request[1] == "/":
        return http_reply(peer, "200 OK", home, policy, "Content-Type: text/html; charset=utf-8\r\n")
    if not regex_fullmatch("/room/[A-Za-z0-9_-]{1,32}/[A-Za-z0-9_-]{1,24}", request[1]):
        return http_reply(peer, "404 Not Found", b"Use /room/room/name\n", policy, "")
    if "origin" in headers and headers["origin"].lower() != "http://" + host:
        return http_reply(peer, "403 Forbidden", b"Origin rejected\n", policy, "")
    assert headers.get("upgrade", "").lower() == "websocket", "missing WebSocket upgrade"
    connection: bool = False
    for token in headers.get("connection", "").lower().split(","):
        if token.strip() == "upgrade":
            connection = True
    assert connection, "missing Connection upgrade token"
    if headers.get("sec-websocket-version", "") != "13":
        return http_reply(
            peer, "426 Upgrade Required", b"Version 13 required\n", policy, "Sec-WebSocket-Version: 13\r\n"
        )
    nonce: str = headers.get("sec-websocket-key", "")
    assert len(base64_decode(nonce)) == 16, "invalid WebSocket key"
    path: list[str] = request[1].split("/")
    for key in peers:  # noqa: PLC0206 - supported dictionary-key iteration
        other: Peer = peers[key]
        if other.phase == "open" and other.room == path[2] and other.nick == path[3]:
            return http_reply(peer, "409 Conflict", b"Name already in room\n", policy, "")
    accept: str = base64_encode(sha1_digest((nonce + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode()))
    peer = enqueue(
        peer,
        (
            "HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Accept: "
            + accept
            + "\r\n\r\n"
        ).encode(),
        policy,
    )
    if peer.phase != "dead":
        peer.phase = "open"
        peer.websocket = True
        peer.room = path[2]
        peer.nick = path[3]
    return peer
