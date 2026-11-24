"""Run one command with an isolated environment; collect outcomes without stopping on test failures."""

# ruff: noqa: I001, BLE001 - explicit per-command failure boundary
from assertions import matches, preview
from configuration import environment, input_bytes
from py2rust.stdlib import (
    Json,
    json_array,
    json_int,
    json_is_null,
    json_string,
    process_run,
    sha256_digest,
    sha256_new,
    sha256_update,
)


def capture(name: str, data: bytes) -> Json:
    return {
        "file": name,
        "bytes": len(data),
        "sha256": sha256_digest(sha256_update(sha256_new(), data)),
        "utf8_preview": preview(data),
    }


def execute(case: Json) -> tuple[Json, bytes, bytes]:
    arguments: list[str] = []
    for value in json_array(case["arguments"]):
        arguments.append(json_string(value))
    variables: dict[str, str] = environment(case["variables"])
    result: tuple[Json, bytes, bytes] = ({"kind": "runtime_error", "returncode": None, "interrupt_signal": 0}, b"", b"")
    error_text: str = ""
    try:
        result = process_run(
            arguments,
            variables,
            json_string(case["directory"]),
            input_bytes(case["stdin"]),
            json_int(case["timeout_ms"]),
            json_int(case["max_output"]),
        )
    except Exception as error:
        error_text = str(error)
    outcome: Json = result[0]
    failed: list[str] = []
    kind: str = json_string(outcome["kind"])
    if kind != "exited":
        failed.append(kind)
    expected: Json = case["expect"]
    if json_is_null(outcome["returncode"]) or json_int(outcome["returncode"]) != json_int(expected["exit_code"]):
        failed.append("exit_code")
    if not matches(result[1], expected["stdout"]):
        failed.append("stdout")
    if not matches(result[2], expected["stderr"]):
        failed.append("stderr")
    name: str = json_string(case["id"])
    record: Json = {
        "id": name,
        "status": "passed" if len(failed) == 0 else "failed",
        "outcome": outcome,
        "failed_checks": failed,
        "error": error_text,
        "argv": case["argv"],
        "cwd": case["cwd"],
        "stdout": capture(name + ".stdout", result[1]),
        "stderr": capture(name + ".stderr", result[2]),
    }
    return (record, result[1], result[2])


def skipped(case: Json) -> Json:
    return {
        "id": case["id"],
        "status": "skipped",
        "outcome": None,
        "failed_checks": [],
        "error": "suite interrupted",
        "argv": case["argv"],
        "cwd": case["cwd"],
        "stdout": None,
        "stderr": None,
    }
