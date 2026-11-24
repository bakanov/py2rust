"""Two owned child groups per attempt, bounded pipe capture, readiness and whole-attempt deadlines."""
# ruff: noqa: I001, BLE001 - compact imports and a recorded per-attempt failure boundary
from dataclasses import dataclass
from model import integer
from workers import elapsed, validate
from py2rust.stdlib import (
    Json, ProcessPool, json_array, json_bool, json_canonical, json_int, json_keys, json_loads_unique, json_string,
    monotonic, process_poll, process_pool, process_pool_signal, process_spawn, regex_fullmatch, sleep,
)


@dataclass
class Child:
    handle: int
    output: bytes
    errors: bytes
    done: bool
    code: Json


def start(pool: ProcessPool, command: Json, role: str, case: Json, port: int) -> Child:
    argv: list[str] = []
    for item in json_array(command["argv"]):
        argv.append(json_string(item))
    variables: dict[str, str] = {}
    for name in json_keys(command["environment"]):
        variables[name] = json_string(command["environment"][name])
    variables["TRANSFER_ROLE"] = role
    variables["TRANSFER_CASE"] = json_canonical(case)
    variables["TRANSFER_PORT"] = str(port)
    variables["PYTHONUNBUFFERED"] = "1"
    return Child(process_spawn(pool, argv, variables, json_string(command["cwd"])), b"", b"", False, None)


def poll(pool: ProcessPool, child: Child) -> Child:
    if child.done:
        return child
    event: tuple[Json, bytes, bytes] = process_poll(pool, child.handle, 4096)
    child.output = child.output + event[1]
    child.errors = child.errors + event[2]
    assert len(child.output) + len(child.errors) <= 8192, "worker output budget exceeded"
    child.done = json_bool(event[0]["complete"])
    child.code = event[0]["returncode"]
    assert child.code is None or json_int(child.code) == 0, "worker exited unsuccessfully"
    return child


def attempt(case: Json, trial: int, sender: Json, receiver: Json) -> Json:
    started: float = monotonic()
    phase: str = "spawn_receiver"
    interrupted: bool = False
    sent: Json = None
    received: Json = None
    error: str = ""
    status: str = "failed"
    try:
        with process_pool() as pool:
            receiver_child: Child = start(pool, receiver, "receiver", case, 0)
            sender_child: Child = Child(0, b"", b"", False, None)
            phase = "readiness"
            ready: int = -1
            while not sender_child.done or not receiver_child.done:
                interrupted = process_pool_signal(pool) != 0
                assert not interrupted, "benchmark interrupted"
                assert elapsed(started) < json_int(case["timeout_ms"]) * 1000, "attempt deadline exceeded"
                receiver_child = poll(pool, receiver_child)
                if sender_child.handle == 0:
                    ready = receiver_child.output.find(b"\n")
                    assert not receiver_child.done, "receiver exited before transfer"
                    if ready >= 0:
                        line: str = receiver_child.output[:ready].decode()
                        assert regex_fullmatch("READY [0-9]{1,5}", line), "invalid readiness line"
                        port: int = integer(int(line[6:]), 1, 65535)
                        phase = "spawn_sender"
                        sender_child = start(pool, sender, "sender", case, port)
                        phase = "transfer"
                if sender_child.handle > 0:
                    sender_child = poll(pool, sender_child)
                    if sender_child.done and receiver_child.done:
                        break
                sleep(0.002)
            phase = "reports"
            assert receiver_child.errors == b"" and sender_child.errors == b"", "unexpected worker stderr"
            sent = json_loads_unique(sender_child.output.decode())
            received = json_loads_unique(receiver_child.output[ready + 1:].decode())
            ceiling: int = elapsed(started)
            validate(sent, "sender", case, ceiling)
            validate(received, "receiver", case, ceiling)
            status = "ok"
    except Exception as failure:
        error = str(failure)
        status = "failed"
    return {"case": case["id"], "trial": trial, "status": "interrupted" if interrupted else status,
            "phase": phase, "error": error, "sender": sent, "receiver": received, "wall_us": elapsed(started)}
