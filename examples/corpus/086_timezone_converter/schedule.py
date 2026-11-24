"""Validate an appointment batch and collect the rules needed for every source and target."""

# ruff: noqa: PLR1711 - explicit subset returns
from dataclasses import dataclass

from documents import Document, absolute, present
from zones import ZoneSnapshot, load_zones, zone_name

from py2rust.stdlib import (
    Json,
    json_array,
    json_int,
    json_keys,
    json_loads,
    json_string,
    path_parent,
    regex_fullmatch,
)


@dataclass
class Inspection:
    appointments: list[Json]
    targets: list[str]
    zones: dict[str, bytes]
    inputs: list[Document]
    output: str


def exact(value: Json, keys: list[str]) -> None:
    assert sorted(json_keys(value)) == sorted(keys), "unexpected fields"
    return


def load(config: Document) -> Inspection:
    value: Json = json_loads(config.data.decode())
    exact(value, ["version", "tzdata", "targets", "appointments", "output"])
    assert json_int(value["version"]) == 1, "unsupported configuration version"
    appointments: list[Json] = json_array(value["appointments"])
    target_values: list[Json] = json_array(value["targets"])
    assert 1 <= len(appointments) <= 256, "expected 1..256 appointments"
    assert 1 <= len(target_values) <= 8, "expected 1..8 targets"
    targets: list[str] = []
    names: set[str] = set()
    for item in target_values:
        name: str = zone_name(item)
        assert name not in names, "duplicate target zone"
        names.add(name)
        targets.append(name)
    identifiers: set[str] = set()
    for appointment in appointments:
        exact(appointment, ["id", "label", "local", "zone", "ambiguity", "gap"])
        key: str = json_string(appointment["id"])
        assert regex_fullmatch("[A-Za-z][A-Za-z0-9_-]{0,31}", key), "invalid appointment identifier"
        assert key not in identifiers, "duplicate appointment identifier"
        identifiers.add(key)
        label: str = json_string(appointment["label"])
        assert 1 <= len(label.encode()) <= 256 and "\x00" not in label, "invalid label"
        local: str = json_string(appointment["local"])
        assert len(local.encode()) <= 64 and "\x00" not in local, "invalid local timestamp field"
        names.add(zone_name(appointment["zone"]))
        assert json_string(appointment["ambiguity"]) in ["reject", "earlier", "later"], "unknown ambiguity policy"
        assert json_string(appointment["gap"]) in ["reject", "shift_forward", "shift_backward"], "unknown gap policy"
    assert len(names) <= 16, "expected at most 16 distinct zones"
    base: str = path_parent(config.path)
    output: str = absolute(json_string(value["output"]), base)
    assert not present(output), "output already exists"
    snapshot: ZoneSnapshot = load_zones(absolute(json_string(value["tzdata"]), base), names)
    inputs: list[Document] = [config] + snapshot.inputs
    return Inspection(appointments, targets, snapshot.zones, inputs, output)
