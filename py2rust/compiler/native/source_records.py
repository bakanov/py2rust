"""Record graph checks before choosing owned Rust layouts."""

from py2rust.stdlib import Json, json_array, json_keys, json_string

from .declarations import source_label
from .source_types import contains_runtime_handle


def check_record_cycles(records: dict[str, Json]) -> None:
    for root in records:
        pending: list[str] = [root]
        visited: list[str] = []
        while len(pending) > 0:
            name: str = pending.pop()
            if name in visited:
                continue
            visited.append(name)
            for field in json_array(records[name]["fields"]):
                assert not contains_runtime_handle(field["type"]), (
                    source_label(json_string(records[name]["path"]), field["syntax"])
                    + ": opaque resource record fields are unsupported"
                )
                types: list[Json] = [field["type"]]
                while len(types) > 0:
                    typ: Json = types.pop()
                    target: str = json_string(typ["name"])
                    assert target != root, (
                        source_label(json_string(records[name]["path"]), field["syntax"])
                        + ": recursive records require an explicit indirection policy"
                    )
                    if target in records:
                        pending.append(target)
                    types.extend(json_array(typ["arguments"]))
    return


def record_equality_safe(name: str, records: Json) -> bool:
    types: list[Json] = [{"name": name, "arguments": []}]
    while len(types) > 0:
        typ: Json = types.pop()
        current: str = json_string(typ["name"])
        if current == "py2rust.stdlib.Json":
            return False
        if current in json_keys(records):
            for field in json_array(records[current]["fields"]):
                types.append(field["type"])
        types.extend(json_array(typ["arguments"]))
    return True


def structural_equality_safe(typ: Json, records: Json) -> bool:
    if contains_runtime_handle(typ):
        return False
    pending: list[Json] = [typ]
    while len(pending) > 0:
        current: Json = pending.pop()
        name: str = json_string(current["name"])
        if name == "py2rust.stdlib.Json":
            return False
        if name in json_keys(records) and not record_equality_safe(name, records):
            return False
        pending.extend(json_array(current["arguments"]))
    return True
