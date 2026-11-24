"""Publish machine-readable outcomes, raw captures and a compact human-readable summary."""

# ruff: noqa: PLC0206 - typed subset dictionary iteration
from py2rust.stdlib import (
    Json,
    json_canonical,
    json_int,
    json_is_null,
    json_string,
    sha256_digest,
    sha256_new,
    sha256_update,
)


def summarize(records: list[Json], interrupted: int) -> Json:
    passed: int = 0
    failed: int = 0
    skipped: int = 0
    captured: int = 0
    for record in records:
        status: str = json_string(record["status"])
        if status == "passed":
            passed = passed + 1
        elif status == "failed":
            failed = failed + 1
        else:
            skipped = skipped + 1
        if not json_is_null(record["stdout"]):
            captured = captured + json_int(record["stdout"]["bytes"]) + json_int(record["stderr"]["bytes"])
    return {
        "total": len(records),
        "executed": passed + failed,
        "passed": passed,
        "failed": failed,
        "skipped": skipped,
        "captured_bytes": captured,
        "interrupt_signal": interrupted,
    }


def render(records: list[Json], summary: Json, captures: dict[str, bytes]) -> dict[str, bytes]:
    status: str = "passed" if json_int(summary["failed"]) == 0 else "failed"
    if json_int(summary["interrupt_signal"]) != 0:
        status = "interrupted"
    report: Json = {"version": 1, "status": status, "summary": summary, "tests": records}
    files: dict[str, bytes] = captures.copy()
    files["report.json"] = (json_canonical(report) + "\n").encode()
    lines: list[str] = ["Process test runner: " + status, json_canonical(summary)]
    for record in records:
        lines.append(
            json_string(record["id"])
            + ": "
            + json_string(record["status"])
            + " "
            + json_canonical(record["failed_checks"])
        )
    files["report.txt"] = ("\n".join(lines) + "\n").encode()
    manifest: Json = {}
    for name in files:
        data: bytes = files[name]
        manifest[name] = {"bytes": len(data), "sha256": sha256_digest(sha256_update(sha256_new(), data))}
    files["manifest.json"] = (json_canonical(manifest) + "\n").encode()
    return files
