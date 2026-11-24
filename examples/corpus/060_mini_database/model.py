"""Typed database state, bounded keys/JSON values and checksummed logical snapshots."""

# ruff: noqa: PLR1711 - explicit subset returns

from dataclasses import dataclass

from py2rust.stdlib import (
    Json,
    json_array,
    json_canonical,
    json_int,
    json_keys,
    json_kind,
    json_loads,
    json_string,
    sha256_digest,
    sha256_new,
    sha256_update,
)


@dataclass
class State:
    capacity: int
    sequence: int
    values: dict[str, Json]


def exact(value: Json, names: list[str]) -> None:
    assert json_keys(value) == sorted(names), "unexpected object fields"
    return


def key(value: Json) -> str:
    name: str = json_string(value)
    assert 1 <= len(name) <= 128 and len(name.encode()) <= 512, "invalid key length"
    return name


def depth(value: Json, level: int) -> None:
    assert level <= 8, "value nesting exceeds eight"
    if json_kind(value) == "array":
        for item in json_array(value):
            depth(item, level + 1)
    elif json_kind(value) == "object":
        for name in json_keys(value):
            depth(value[name], level + 1)
    return


def value_check(value: Json) -> None:
    depth(value, 0)
    assert len(json_canonical(value).encode()) <= 4096, "value exceeds 4 KiB"
    return


def command(value: Json) -> str:
    operation: str = json_string(value["op"])
    assert operation in ["SET", "DELETE", "GET", "DUMP", "INFO", "COMPACT"], "unknown database operation"
    fields: list[str] = ["op"]
    if operation in ["SET", "DELETE", "GET"]:
        fields.append("key")
    if operation == "SET":
        fields.append("value")
    exact(value, fields)
    if operation in ["SET", "DELETE", "GET"]:
        key(value["key"])
    if operation == "SET":
        value_check(value["value"])
    return operation


def apply(state: State, record: Json) -> State:
    operation: str = command(record)
    assert operation in ["SET", "DELETE"], "journal contains a nonmutating operation"
    assert state.sequence < 1000000000, "sequence limit reached"
    name: str = key(record["key"])
    values: dict[str, Json] = state.values.copy()
    if operation == "SET":
        assert name in values or len(values) < state.capacity, "database capacity reached"
        values[name] = record["value"]
    elif name in values:
        del values[name]
    return State(state.capacity, state.sequence + 1, values)


def digest(data: bytes) -> bytes:
    return bytes.fromhex(sha256_digest(sha256_update(sha256_new(), data)))


def snapshot(state: State) -> bytes:
    value: Json = {"version": 1, "capacity": state.capacity, "sequence": state.sequence, "values": state.values}
    return (json_canonical({"state": value, "sha256": digest(json_canonical(value).encode()).hex()}) + "\n").encode()


def restore(raw: bytes, capacity: int) -> State:
    envelope: Json = json_loads(raw.decode())
    exact(envelope, ["state", "sha256"])
    value: Json = envelope["state"]
    assert digest(json_canonical(value).encode()).hex() == json_string(envelope["sha256"]), "snapshot checksum mismatch"
    exact(value, ["version", "capacity", "sequence", "values"])
    assert (
        json_int(value["version"]) == 1 and json_int(value["capacity"]) == capacity
    ), "snapshot format or capacity mismatch"
    sequence: int = json_int(value["sequence"])
    assert 0 <= sequence <= 1000000000, "invalid snapshot sequence"
    names: list[str] = json_keys(value["values"])
    assert len(names) <= min(capacity, sequence), "impossible snapshot key count"
    values: dict[str, Json] = {}
    for name in names:
        key(name)
        value_check(value["values"][name])
        values[name] = value["values"][name]
    return State(capacity, sequence, values)
