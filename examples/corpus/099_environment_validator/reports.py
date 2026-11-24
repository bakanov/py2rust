"""Build redacted public records without exporting raw environment values or secret predicates."""

# ruff: noqa: PLC0206 - explicit dictionary iteration
from py2rust.stdlib import (
    Json,
    json_array,
    json_bool,
    json_canonical,
    json_int,
    json_keys,
    json_string,
    sha256_digest,
    sha256_new,
    sha256_update,
)


def encoded(value: Json) -> bytes:
    return (json_canonical(value) + "\n").encode()


def describe(fields: Json) -> Json:
    rows: list[Json] = []
    for name in sorted(json_keys(fields)):
        field: Json = fields[name]
        dependencies: list[str] = []
        for rule in json_array(field["requires"]):
            dependencies.append(json_string(rule["field"]))
        rows.append(
            {
                "name": name,
                "env": field["env"],
                "type": field["type"],
                "required": field["required"],
                "secret": field["secret"],
                "nullable": field["nullable"],
                "has_default": field["has_default"],
                "depends_on": sorted(dependencies),
            }
        )
    return {"version": 1, "fields": rows}


def render(fields: Json, states: Json) -> Json:
    rows: list[Json] = []
    effective: Json = {}
    diagnostics: list[Json] = []
    counts: Json = {
        "fields": len(json_keys(fields)),
        "valid": 0,
        "missing": 0,
        "invalid": 0,
        "defaulted": 0,
        "errors": 0,
    }
    for name in sorted(json_keys(fields)):
        field: Json = fields[name]
        state: Json = states[name]
        status: str = json_string(state["status"])
        counts[status] = json_int(counts[status]) + 1
        if json_string(state["origin"]) == "default":
            counts["defaulted"] = json_int(counts["defaulted"]) + 1
        value: Json = None
        if status == "valid":
            value = state["value"]
        if json_bool(field["secret"]):
            value = "<redacted>"
        if status == "valid":
            effective[name] = value
        errors: list[Json] = json_array(state["errors"])
        for error in errors:
            diagnostics.append(
                {"field": name, "env": field["env"], "code": error["code"], "dependency": error["dependency"]}
            )
        rows.append(
            {
                "name": name,
                "env": field["env"],
                "type": field["type"],
                "secret": field["secret"],
                "status": status,
                "origin": state["origin"],
                "value": value,
                "errors": errors,
            }
        )
    counts["errors"] = len(diagnostics)
    return {
        "version": 1,
        "valid": len(diagnostics) == 0,
        "summary": counts,
        "fields": rows,
        "effective": effective,
        "diagnostics": diagnostics,
    }


def bundle(report: Json, description: Json, schema_path: str) -> dict[str, bytes]:
    files: dict[str, bytes] = {
        "report.json": encoded(report),
        "schema-summary.json": encoded(description),
        "recheck.json": encoded({"version": 1, "schema": schema_path, "output": "rechecked"}),
    }
    lines: list[str] = ["Environment configuration: " + ("valid" if json_bool(report["valid"]) else "invalid")]
    for row in json_array(report["fields"]):
        lines.append(
            json_string(row["name"])
            + " ("
            + json_string(row["env"])
            + "): "
            + json_string(row["status"])
            + ", "
            + json_string(row["origin"])
            + ", "
            + json_canonical(row["value"])
        )
    for diagnostic in json_array(report["diagnostics"]):
        lines.append(
            json_string(diagnostic["field"])
            + ": "
            + json_string(diagnostic["code"])
            + (" (" + json_string(diagnostic["dependency"]) + ")" if diagnostic["dependency"] is not None else "")
        )
    files["report.txt"] = ("\n".join(lines) + "\n").encode()
    manifest: Json = {}
    for name in files:
        assert len(files[name]) <= 262144, "output document budget exceeded"
        manifest[name] = {"bytes": len(files[name]), "sha256": sha256_digest(sha256_update(sha256_new(), files[name]))}
    files["manifest.json"] = encoded(manifest)
    return files
