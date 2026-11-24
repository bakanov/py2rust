"""Compare semantic envelopes and create reproducible, hash-bound inspection reports."""

# ruff: noqa: PLC0206 - compact imports and typed dictionary iteration
from py2rust.stdlib import (
    Json,
    json_bool,
    json_canonical,
    json_equal,
    json_get,
    json_int,
    json_is_null,
    json_string,
    sha256_digest,
    sha256_new,
    sha256_update,
)


def matches(actual: Json, wanted: Json) -> bool:
    if json_is_null(wanted):
        return True
    if json_string(actual["kind"]) != json_string(wanted["kind"]):
        return False
    if json_string(wanted["kind"]) == "error":
        return json_string(actual["code"]) == json_string(wanted["code"])
    return json_equal(actual["value"], wanted["value"])


def digest(data: bytes) -> str:
    return sha256_digest(sha256_update(sha256_new(), data))


def render(rows: list[Json], source: bytes) -> dict[str, bytes]:
    passed: int = 0
    errors: int = 0
    operations: Json = {}
    codes: Json = {}
    replay: list[Json] = []
    lines: list[str] = ["Native Rust import inspection"]
    for row in rows:
        if json_bool(row["passed"]):
            passed = passed + 1
        operation: str = json_string(row["operation"])
        operations[operation] = json_int(json_get(operations, operation, 0)) + 1
        if json_string(row["observed"]["kind"]) == "error":
            errors = errors + 1
            code: str = json_string(row["observed"]["code"])
            codes[code] = json_int(json_get(codes, code, 0)) + 1
        replay.append(
            {"id": row["id"], "operation": operation, "arguments": row["arguments"], "expect": row["reference"]}
        )
        status: str = "passed" if json_bool(row["passed"]) else "FAILED"
        lines.append(json_string(row["id"]) + " " + operation + ": " + status + " " + json_canonical(row["observed"]))
    summary: Json = {"total": len(rows), "passed": passed, "failed": len(rows) - passed, "native_errors": errors}
    report: Json = {
        "version": 1,
        "source_sha256": digest(source),
        "summary": summary,
        "operations": operations,
        "error_codes": codes,
        "cases": rows,
    }
    files: dict[str, bytes] = {
        "report.json": (json_canonical(report) + "\n").encode(),
        "report.txt": ("\n".join(lines) + "\n").encode(),
        "replay.json": (json_canonical({"version": 1, "output": "replayed", "cases": replay}) + "\n").encode(),
    }
    assert len(files["replay.json"]) <= 262144, "replay exceeds configuration byte limit"
    manifest: Json = {}
    total: int = 0
    for name in files:
        data: bytes = files[name]
        total = total + len(data)
        manifest[name] = {"bytes": len(data), "sha256": digest(data)}
    assert total <= 2097152, "report bundle exceeds 2 MiB"
    files["manifest.json"] = (json_canonical(manifest) + "\n").encode()
    return files
