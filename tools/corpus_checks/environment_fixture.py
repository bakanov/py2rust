"""Independent scalar/dependency oracle and secret-bearing fixtures for application 099."""

from __future__ import annotations

import copy
import json
import math
from typing import Any

CANARY = "never-export-9a72d1-secret-世界"
OTHER = "never-export-b17c44-secret-🔐"


def canonical(value: Any) -> bytes:
    if type(value) is float:
        mantissa, exponent = format(value, ".16e").split("e")
        text = mantissa.rstrip("0").rstrip(".") + "e" + str(int(exponent))
    elif isinstance(value, dict):
        text = (
            "{"
            + ",".join(
                json.dumps(key, ensure_ascii=False) + ":" + canonical(value[key]).decode() for key in sorted(value)
            )
            + "}"
        )
    elif isinstance(value, list):
        text = "[" + ",".join(canonical(item).decode() for item in value) + "]"
    else:
        text = json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
    return text.encode()


def field(name: str, kind: str = "string", **options: Any) -> dict:
    return {"name": name, "env": "EV_" + name.upper(), "type": kind, **options}


def schema() -> dict:
    return {
        "version": 1,
        "fields": [
            field("port", "integer", default=8080, minimum=1, maximum=65535),
            field("host", default="127.0.0.1", min_length=1),
            field("tls", "bool", default=True),
            field(
                "token",
                secret=True,
                default=CANARY,
                choices=[CANARY, OTHER],
                requires=[{"field": "tls", "equals": True}],
            ),
            field("feature", "bool", default=True, requires=[{"field": "token", "equals": CANARY}]),
            field("ratio", "number", default=0.25, minimum=0, maximum=1),
            field("contact", nullable=True),
            field("required", required=True),
            field("optional_secret", secret=True),
            field("nullable", nullable=True, default=None),
            field("level", default="info", choices=["info", "debug"]),
        ],
    }


def strict_loads(raw: str) -> Any:
    def pairs(items: list[tuple[str, Any]]) -> dict:
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("duplicate")
            result[key] = value
        return result

    def check(value: Any, depth: int = 0) -> None:
        if depth > 64:
            raise ValueError("depth")
        if type(value) is int and not -(2**63) <= value < 2**63:
            raise ValueError("integer")
        if type(value) is float and not math.isfinite(value):
            raise ValueError("number")
        if isinstance(value, str):
            value.encode()
        if isinstance(value, list):
            for child in value:
                check(child, depth + 1)
        if isinstance(value, dict):
            for key, child in value.items():
                check(key, depth + 1)
                check(child, depth + 1)
        return  # noqa: PLR1711

    value = json.loads(raw, object_pairs_hook=pairs)
    check(value)
    return value


def scalar_equal(left: Any, right: Any) -> bool:
    if type(left) is bool or type(right) is bool:
        return type(left) is type(right) and left == right
    return left == right


def problem(value: Any, rule: dict) -> str:
    if value is None:
        if not rule.get("nullable", False):
            return "null"
    else:
        kinds = {"integer": (int,), "number": (int, float), "bool": (bool,), "string": (str,)}
        if type(value) not in kinds[rule["type"]]:
            return "type"
        if rule["type"] in ["integer", "number"] and (
            ("minimum" in rule and value < rule["minimum"]) or ("maximum" in rule and value > rule["maximum"])
        ):
            return "range"
        if rule["type"] == "string" and not rule.get("min_length", 0) <= len(value) <= rule.get("max_length", 1024):
            return "length"
    if "choices" in rule and not any(scalar_equal(value, choice) for choice in rule["choices"]):
        return "choice"
    return ""


def expected(document: dict, variables: dict[str, str]) -> dict:
    states = {}
    pending = {row["name"]: row for row in document["fields"]}
    while pending:
        progress = False
        for name, row in list(pending.items()):
            if any(rule["field"] not in states for rule in row.get("requires", [])):
                continue
            value, origin, status, code = None, "absent", "missing", ""
            if row["env"] in variables:
                origin, status = "environment", "invalid"
                raw = variables[row["env"]]
                if len(raw.encode()) > 4096:
                    code = "size"
                else:
                    try:
                        value = strict_loads(raw)
                        code = problem(value, row)
                        if not code:
                            status = "valid"
                    except (ValueError, UnicodeError, RecursionError):
                        code = "json"
            elif "default" in row:
                value, origin, status = row["default"], "default", "valid"
            elif row.get("required", False):
                code = "required"
            errors = [{"code": code, "dependency": None}] if code else []
            if status == "valid":
                for dependency in row.get("requires", []):
                    target = states[dependency["field"]]
                    if target["status"] != "valid" or not scalar_equal(target["value"], dependency["equals"]):
                        errors.append({"code": "dependency", "dependency": dependency["field"]})
                if errors:
                    status = "invalid"
            states[name] = {"status": status, "origin": origin, "value": value, "errors": errors}
            del pending[name]
            progress = True
        assert progress, "oracle requires an acyclic validated fixture"
    fields, diagnostics, effective = [], [], {}
    counts = {"fields": len(states), "valid": 0, "missing": 0, "invalid": 0, "defaulted": 0, "errors": 0}
    for rule in sorted(document["fields"], key=lambda row: row["name"]):
        name = rule["name"]
        state = states[name]
        counts[state["status"]] += 1
        counts["defaulted"] += state["origin"] == "default"
        public = "<redacted>" if rule.get("secret", False) else state["value"] if state["status"] == "valid" else None
        if state["status"] == "valid":
            effective[name] = public
        fields.append(
            {
                "name": name,
                "env": rule["env"],
                "type": rule["type"],
                "secret": rule.get("secret", False),
                "status": state["status"],
                "origin": state["origin"],
                "value": public,
                "errors": state["errors"],
            }
        )
        diagnostics.extend({"field": name, "env": rule["env"], **error} for error in state["errors"])
    counts["errors"] = len(diagnostics)
    return {
        "version": 1,
        "valid": not diagnostics,
        "summary": counts,
        "fields": fields,
        "effective": effective,
        "diagnostics": diagnostics,
    }


def description(document: dict) -> dict:
    rows = []
    for row in sorted(document["fields"], key=lambda field: field["name"]):
        rows.append(
            {
                "name": row["name"],
                "env": row["env"],
                "type": row["type"],
                "required": row.get("required", False),
                "secret": row.get("secret", False),
                "nullable": row.get("nullable", False),
                "has_default": "default" in row,
                "depends_on": sorted(rule["field"] for rule in row.get("requires", [])),
            }
        )
    return {"version": 1, "fields": rows}


def chain(length: int) -> dict:
    fields = [field("f" + str(index), "integer", default=index) for index in range(length)]
    for index in range(1, length):
        fields[index]["requires"] = [{"field": "f" + str(index - 1), "equals": index - 1}]
    return {"version": 1, "fields": list(reversed(fields))}


def changed(document: dict, name: str, **updates: Any) -> dict:
    result = copy.deepcopy(document)
    next(row for row in result["fields"] if row["name"] == name).update(updates)
    return result
