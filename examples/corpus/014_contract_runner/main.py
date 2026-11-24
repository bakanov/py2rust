"""Run a bounded HTTP contract suite, retain named failures, and exit for CI."""

import sys

from checks import field_mismatches, snapshot_mismatches
from config import (
    base_url,
    load_config,
    maximum_body,
    snapshot_directory,
    text,
    timeout,
    validate_config,
)

from py2rust.stdlib import (
    HttpResponse,
    Json,
    env_get,
    http_request,
    json_array,
    json_bool,
    json_dumps,
    json_get,
    json_int,
    json_loads,
    mkdir_all,
    pretty,
    write_text_atomic,
)


def request_body(case: Json) -> str:
    if "text_body" in case:
        return text(case, "text_body", "")
    if "body" in case:
        return json_dumps(case["body"])
    return ""


def run_case(config: Json, case: Json) -> Json:
    failures: list[Json] = []
    name: str = text(case, "name", "")
    actual_status: int = 0
    try:
        response: HttpResponse = http_request(
            text(case, "method", "GET"),
            base_url(config) + text(case, "path", ""),
            request_body(case),
            timeout(config),
            maximum_body(config),
        )
        actual_status = response.status
        expected_status: int = json_int(case["status"])
        if response.status != expected_status:
            failures.append({"check": "status", "expected": expected_status, "actual": response.status})
        rules: list[Json] = json_array(json_get(case, "fields", []))
        snapshot: str = text(case, "snapshot", "")
        if len(rules) > 0 or snapshot != "":
            decoded: bool = True
            body: Json = None
            try:
                body = json_loads(response.body)
            except Exception:  # noqa: BLE001 - the profile exposes recoverable failures through Exception
                decoded = False
                failures.append({"check": "json", "reason": "response is not valid JSON"})
            if decoded:
                failures.extend(field_mismatches(body, rules))
                # Never bless a snapshot when a status or field assertion failed.
                updating: bool = json_bool(json_get(config, "update_snapshots", False)) and len(failures) == 0
                failures.extend(snapshot_mismatches(snapshot, body, snapshot_directory(), updating))
    except Exception:  # noqa: BLE001 - the profile exposes recoverable failures through Exception
        failures.append({"check": "transport", "reason": "request or response processing failed"})
    return {"name": name, "passed": len(failures) == 0, "status": actual_status, "failures": failures}


def run_suite(config: Json) -> Json:
    results: list[Json] = []
    passed: int = 0
    failed: int = 0
    failures: int = 0
    for case in json_array(config["cases"]):
        result: Json = run_case(config, case)
        results.append(result)
        failures = failures + len(json_array(result["failures"]))
        if json_bool(result["passed"]):
            passed = passed + 1
        else:
            failed = failed + 1
    summary: Json = {"total": len(results), "passed": passed, "failed": failed, "mismatches": failures}
    return {"summary": summary, "results": results}


def text_report(report: Json) -> str:
    summary: Json = report["summary"]
    lines: list[str] = ["HTTP contract results"]
    lines.append("Passed: " + str(json_int(summary["passed"])) + "/" + str(json_int(summary["total"])))
    lines.append("Mismatches: " + str(json_int(summary["mismatches"])))
    for result in json_array(report["results"]):
        label: str = "PASS"
        if not json_bool(result["passed"]):
            label = "FAIL"
        lines.append(label + " " + text(result, "name", ""))
        for failure in json_array(result["failures"]):
            lines.append("  " + json_dumps(failure))
    return "\n".join(lines) + "\n"


def main() -> None:
    configuration: Json = load_config()
    validate_config(configuration)
    mkdir_all(snapshot_directory())
    report: Json = run_suite(configuration)
    output: str = env_get("CONTRACT_REPORT", "contract-report.json")
    write_text_atomic(output, pretty(report))
    write_text_atomic(env_get("CONTRACT_TEXT_REPORT", "contract-report.txt"), text_report(report))
    print(pretty(report))
    if json_int(report["summary"]["failed"]) > 0:
        sys.exit(1)
    return  # noqa: PLR1711 - explicit return required by repository guidelines


if __name__ == "__main__":
    main()
