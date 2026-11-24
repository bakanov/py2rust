"""Publish readable schedules, field explanations, diagnostics and a portable replay job."""

# ruff: noqa: BLE001, LOG015, PLR1711, PLC0206 - recoverable boundary and explicit subset operations
import logging

from config import Job, load, replay
from documents import Document, absolute, publish, read, stamp
from grammar import Expression, describe, parse
from schedule import Search, explore

from py2rust.stdlib import (
    Json,
    datetime_iso,
    env_get,
    json_array,
    json_canonical,
    json_equal,
    json_string,
    path_resolve,
    process_exit,
    sha256_digest,
    sha256_new,
    sha256_update,
)


def run() -> int:
    document: Document = read(absolute(env_get("CRON_CONFIG", "cron-job.json"), path_resolve(".")), 65536)
    job: Job = load(document)
    entries: list[Json] = []
    lines: list[str] = [
        "UTC cron schedules",
        "Window: [" + datetime_iso(job.start) + ", " + datetime_iso(job.end) + ")",
    ]
    csv: list[str] = ["id,utc,weekday"]
    errors: int = 0
    for entry in job.schedules:
        identifier: str = json_string(entry["id"])
        source: str = json_string(entry["expression"])
        expression: Expression = parse(source)
        explanation: Json = describe(expression)
        row: Json = {
            "id": identifier,
            "expression": source,
            "explanation": explanation,
            "status": "invalid",
            "runs": [],
            "more": False,
            "next_omitted": "",
            "inspected_days": 0,
        }
        lines.append("\n" + identifier + ": " + json_canonical(source))
        if expression.error != "":
            errors = errors + 1
            lines.append(
                "  Field " + str(expression.field) + ", column " + str(expression.column) + ": " + expression.error
            )
        else:
            found: Search = explore(expression, job)
            row["status"] = "valid"
            row["runs"] = found.runs
            row["more"] = found.more
            row["next_omitted"] = found.next_omitted
            row["inspected_days"] = found.inspected_days
            lines.append("  Day-of-month / day-of-week: " + json_string(explanation["day_rule"]))
            for field in json_array(explanation["fields"]):
                lines.append("  " + json_string(field["name"]) + " = " + json_canonical(field["values"]))
            for occurrence in found.runs:
                text: str = json_string(occurrence["utc"])
                lines.append("  " + text)
                csv.append(identifier + "," + text + "," + json_canonical(occurrence["weekday"]))
            if found.more:
                lines.append("  Result limit reached; next omitted run: " + found.next_omitted)
            elif len(found.runs) == 0:
                lines.append("  No runs in the requested window.")
            else:
                lines.append("  All runs in the requested window are listed.")
        entries.append(row)
    result: Json = {
        "version": 1,
        "start": datetime_iso(job.start),
        "end": datetime_iso(job.end),
        "days": job.days,
        "limit": job.limit,
        "errors": errors,
        "schedules": entries,
    }
    files: dict[str, bytes] = {
        "report.json": (json_canonical(result) + "\n").encode(),
        "report.txt": ("\n".join(lines) + "\n").encode(),
        "schedule.csv": ("\n".join(csv) + "\n").encode(),
        "cron-job.json": (json_canonical(replay(job)) + "\n").encode(),
    }
    manifest: Json = {}
    total: int = 0
    for name in files:
        total = total + len(files[name])
        assert total <= 8388608, "schedule bundle exceeds 8 MiB"
        manifest[name] = {"bytes": len(files[name]), "sha256": sha256_digest(sha256_update(sha256_new(), files[name]))}
    files["manifest.json"] = (json_canonical({"version": 1, "files": manifest}) + "\n").encode()
    assert json_equal(document.stamp, stamp(document.path)), "configuration changed"
    publish(job.output, files)
    print(json_canonical(result))
    return 1 if errors > 0 else 0


def main() -> None:
    code: int = 2
    try:
        code = run()
    except Exception as error:
        logging.error(str(error))
    process_exit(code)
    return


if __name__ == "__main__":
    main()
