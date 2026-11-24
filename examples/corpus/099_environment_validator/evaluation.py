"""Read each setting once, keep values internal, and report value-free validation codes."""

# ruff: noqa: BLE001 - a deliberately value-free parsing boundary
from schema import problem

from py2rust.stdlib import (
    Json,
    env_get,
    json_array,
    json_bool,
    json_equal,
    json_loads_unique,
    json_string,
)


def local(field: Json, raw: str) -> Json:
    value: Json = None
    origin: str = "absent"
    status: str = "missing"
    code: str = ""
    if raw == "\x00":
        if json_bool(field["has_default"]):
            value = field["default"]
            origin = "default"
            status = "valid"
        elif json_bool(field["required"]):
            code = "required"
    else:
        origin = "environment"
        status = "invalid"
        code = "size"
        if len(raw.encode()) <= 4096:
            code = "json"
            try:
                value = json_loads_unique(raw)
                code = problem(value, field, True)
                if code == "":
                    status = "valid"
            except Exception:
                code = "json"
    errors: list[Json] = []
    if code != "":
        errors.append({"code": code, "dependency": None})
    return {"status": status, "origin": origin, "value": value, "errors": errors}


def evaluate(fields: Json, names: list[str]) -> Json:
    raw_values: dict[str, str] = {}
    total: int = 0
    for name in names:
        text: str = env_get(json_string(fields[name]["env"]), "\x00")
        if text != "\x00":
            total = total + len(text.encode())
        assert total <= 65536, "environment input budget exceeded"
        raw_values[name] = text
    states: Json = {}
    for name in names:
        row: Json = local(fields[name], raw_values[name])
        if json_string(row["status"]) == "valid":
            errors: list[Json] = []
            for rule in json_array(fields[name]["requires"]):
                target: str = json_string(rule["field"])
                dependency: Json = states[target]
                if json_string(dependency["status"]) != "valid" or not json_equal(dependency["value"], rule["equals"]):
                    errors.append({"code": "dependency", "dependency": target})
            if len(errors) > 0:
                row["status"] = "invalid"
                row["errors"] = errors
        states[name] = row
    return states
