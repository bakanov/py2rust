"""Versioned loopback protocol with exact data validation and bounded fragmented reads/writes."""
# ruff: noqa: I001, PLR1711 - compact imports and explicit returns
from model import digest, exact, integer, payload, workload
from py2rust.stdlib import (
    Json, TcpStream, env_get, floor, json_canonical, json_int, json_loads_unique, json_string, monotonic,
    tcp_accept_timeout, tcp_connect, tcp_listen, tcp_port, tcp_recv, tcp_sendall, tcp_shutdown_write,
)


def elapsed(start: float) -> int:
    return max(1, floor((monotonic() - start) * 1000000.0))


def receive(stream: TcpStream, size: int, chunk: int) -> bytes:
    result: bytes = b""
    while len(result) < size:
        part: bytes = tcp_recv(stream, min(chunk, size - len(result)))
        assert len(part) > 0, "truncated protocol frame"
        result = result + part
    return result


def send(stream: TcpStream, data: bytes, chunk: int) -> None:
    offset: int = 0
    while offset < len(data):
        tcp_sendall(stream, data[offset:offset + chunk])
        offset = offset + chunk
    return


def result(role: str, size: int, hashed: str, started: float) -> Json:
    return {"version": 1, "role": role, "bytes": size, "sha256": hashed, "elapsed_us": elapsed(started)}


def validate(value: Json, role: str, case: Json, ceiling: int) -> None:
    exact(value, ["version", "role", "bytes", "sha256", "elapsed_us"])
    assert json_int(value["version"]) == 1 and json_string(value["role"]) == role, "worker identity mismatch"
    assert json_int(value["bytes"]) == json_int(case["size"]), "worker byte count mismatch"
    expected: str = digest(payload(json_int(case["size"]), json_int(case["seed"])))
    assert json_string(value["sha256"]) == expected, "digest mismatch"
    integer(value["elapsed_us"], 1, ceiling)
    return


def worker(role: str) -> None:
    case: Json = json_loads_unique(env_get("TRANSFER_CASE", ""))
    workload(case)
    data: bytes = payload(json_int(case["size"]), json_int(case["seed"]))
    hashed: bytes = digest(data).encode()
    header: bytes = b"P2RB1" + len(data).to_bytes(8, "big") + hashed
    write_chunk: int = json_int(case["send_chunk"])
    read_chunk: int = json_int(case["receive_chunk"])
    timeout: int = json_int(case["timeout_ms"])
    if role == "receiver":
        with tcp_listen("127.0.0.1", 0) as listener:
            print("READY " + str(tcp_port(listener)))
            with tcp_accept_timeout(listener, timeout, timeout) as stream:
                started: float = monotonic()
                assert receive(stream, 77, read_chunk) == header, "wire header mismatch"
                offset: int = 0
                while offset < len(data):
                    part: bytes = tcp_recv(stream, min(read_chunk, len(data) - offset))
                    assert len(part) > 0, "truncated payload"
                    assert part == data[offset:offset + len(part)], "payload mismatch"
                    offset = offset + len(part)
                assert tcp_recv(stream, 1) == b"", "trailing payload"
                send(stream, b"OK" + hashed, write_chunk)
                tcp_shutdown_write(stream)
                print(json_canonical(result(role, len(data), hashed.decode(), started)))
    else:
        port: int = int(env_get("TRANSFER_PORT", ""))
        assert 1 <= port <= 65535, "invalid receiver port"
        started: float = monotonic()
        with tcp_connect("127.0.0.1", port, timeout) as stream:
            send(stream, header, write_chunk)
            send(stream, data, write_chunk)
            tcp_shutdown_write(stream)
            assert receive(stream, 66, read_chunk) == b"OK" + hashed, "acknowledgment mismatch"
            assert tcp_recv(stream, 1) == b"", "trailing acknowledgment"
            print(json_canonical(result(role, len(data), hashed.decode(), started)))
    return
