"""Stable multi-column merge ordering and first-seen grouping with checked numeric sums."""

from evaluation import matches, required

from py2rust.stdlib import (
    Json,
    ceil,
    json_array,
    json_bool,
    json_canonical,
    json_equal,
    json_float,
    json_get,
    json_kind,
    json_number_add,
    json_scalar_compare,
    json_string,
)


def compare(left: list[Json], right: list[Json], fields: list[Json]) -> int:
    for index in range(len(fields)):
        comparison: int = json_scalar_compare(left[index], right[index])
        if comparison != 0:
            return -comparison if json_bool(fields[index]["descending"]) else comparison
    return 0


def ordered(rows: list[Json], fields: list[Json]) -> list[Json]:
    keys: list[list[Json]] = []
    positions: list[int] = []
    for index in range(len(rows)):
        values: list[Json] = []
        for field in fields:
            value: Json = required(rows[index], field)
            json_scalar_compare(value, value if len(keys) == 0 else keys[0][len(values)])
            values.append(value)
        keys.append(values)
        positions.append(index)
    width: int = 1
    while width < len(rows):
        merged: list[int] = []
        for start in range(0, len(rows), width * 2):
            middle: int = min(start + width, len(rows))
            end: int = min(start + width * 2, len(rows))
            left: int = start
            right: int = middle
            while left < middle or right < end:
                if right == end or (
                    left < middle and compare(keys[positions[left]], keys[positions[right]], fields) <= 0
                ):
                    merged.append(positions[left])
                    left = left + 1
                else:
                    merged.append(positions[right])
                    right = right + 1
        positions = merged
        width = width * 2
    result: list[Json] = []
    for position in positions:
        result.append(rows[position])
    return result


def canonical_scalar(value: Json) -> Json:
    assert json_kind(value) not in ["array", "object"], "group requires scalar keys"
    if json_kind(value) == "number":
        try:
            integer: int = ceil(json_float(value))
            if json_equal(value, integer):
                return integer
        except Exception:  # noqa: BLE001 - integral floats outside i64 remain floats
            return value
    return value


def grouped(rows: list[Json], fields: list[Json], sums: list[Json]) -> list[Json]:
    positions: dict[str, int] = {}
    result: list[Json] = []
    for row in rows:
        key: Json = {}
        for field in fields:
            key[json_string(field["name"])] = canonical_scalar(required(row, field))
        signature: str = json_canonical(key)
        if signature not in positions:
            positions[signature] = len(result)
            result.append({"key": key, "count": 0, "sums": {}})
        position: int = positions[signature]
        group: Json = result[position]
        group["count"] = json_number_add(group["count"], 1)
        totals: Json = group["sums"]
        for field in sums:
            name: str = json_string(field["name"])
            totals[name] = json_number_add(json_get(totals, name, 0), required(row, field))
        group["sums"] = totals
        result[position] = group
    return result


def execute(rows: list[Json], stages: list[Json]) -> list[Json]:
    result: list[Json] = rows
    for number in range(len(stages)):
        stage: Json = stages[number]
        kind: str = json_string(stage["kind"])
        try:
            if kind == "order":
                result = ordered(result, json_array(stage["fields"]))
            elif kind == "group":
                result = grouped(result, json_array(stage["fields"]), json_array(stage["sums"]))
            else:
                selected: list[Json] = []
                for row in result:
                    projected: Json = row
                    if kind == "select":
                        projected = {}
                        for field in json_array(stage["fields"]):
                            projected[json_string(field["name"])] = required(row, field)
                    elif not matches(row, json_array(stage["tests"])):
                        continue
                    selected.append(projected)
                result = selected
        except Exception as error:  # noqa: BLE001 - attach the pipeline stage to runtime failures
            assert False, "stage " + str(number + 1) + " (" + kind + "): " + str(error)
    return result
