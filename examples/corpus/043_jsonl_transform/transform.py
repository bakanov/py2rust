"""Object filtering and projection; malformed records remain available verbatim."""

from dataclasses import dataclass

from py2rust.stdlib import (
    Json,
    json_array,
    json_canonical,
    json_equal,
    json_keys,
    json_kind,
    json_loads,
    json_string,
)


@dataclass
class Row:
    kind: str
    data: bytes
    reason: str


def classify(data: bytes, config: Json) -> Row:
    value: Json = None
    try:
        value = json_loads(data.decode())
    except Exception:  # noqa: BLE001 - stable quarantine reason across parsers
        return Row("rejected", b"", "invalid JSON or UTF-8")
    if json_kind(value) != "object":
        return Row("rejected", b"", "expected JSON object")
    for name in json_keys(config["where"]):
        if name not in value or not json_equal(value[name], config["where"][name]):
            return Row("filtered", b"", "")
    selected: Json = {}
    for item in json_array(config["select"]):
        name: str = json_string(item)
        if name not in value:
            return Row("rejected", b"", "missing selected field: " + name)
        selected[name] = value[name]
    return Row("accepted", (json_canonical(selected) + "\n").encode(), "")
