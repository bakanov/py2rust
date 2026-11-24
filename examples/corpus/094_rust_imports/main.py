"""Dispatch a complete suite through real Rust imports, then publish its inspection bundle."""

# ruff: noqa: I001, BLE001, LOG015, PLR1711 - compact imports and application boundary
import logging
from bridge import observed
from configuration import load
from documents import Document, absolute, publish, read
from reference import expected
from reports import matches, render
from py2rust.stdlib import Json, env_get, json_array, json_string, path_resolve, process_exit


def main() -> None:
    try:
        path: str = absolute(env_get("IMPORTS_CONFIG", "imports-job.json"), path_resolve("."))
        source: Document = read(path, 262144)
        config: Json = load(source)
        rows: list[Json] = []
        failures: int = 0
        for case in json_array(config["cases"]):
            operation: str = json_string(case["operation"])
            reference: Json = expected(operation, case["arguments"])
            actual: Json = observed(operation, case["arguments"])
            correct: bool = matches(actual, reference)
            asserted: bool = matches(actual, case["expect"])
            passed: bool = correct and asserted
            if not passed:
                failures = failures + 1
            rows.append(
                {
                    "id": case["id"],
                    "operation": operation,
                    "arguments": case["arguments"],
                    "expect": case["expect"],
                    "reference": reference,
                    "observed": actual,
                    "matches_reference": correct,
                    "matches_expectation": asserted,
                    "passed": passed,
                }
            )
        publish(json_string(config["output"]), render(rows, source.data), [source])
        process_exit(0 if failures == 0 else 1)
    except Exception as failure:
        logging.error(str(failure))
        process_exit(2)
    return


if __name__ == "__main__":
    main()
