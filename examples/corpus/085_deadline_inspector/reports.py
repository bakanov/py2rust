"""Render deterministic reports and normalized inputs that can be inspected again."""

# ruff: noqa: PLC0206 - supported subset dictionary iteration
from schedule import Inspection

from py2rust.stdlib import (
    Json,
    datetime_iso,
    json_array,
    json_canonical,
    json_int,
    json_is_null,
    json_string,
    sha256_digest,
    sha256_new,
    sha256_update,
)


def cell(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def render(inspection: Inspection, result: Json) -> dict[str, bytes]:
    columns: list[str] = [
        "id",
        "label",
        "status",
        "deadline",
        "grace_seconds",
        "cutoff",
        "completed_at",
        "lateness_us",
        "observed_events",
        "future_events",
        "duplicate_events",
    ]
    csv: list[str] = [",".join(columns)]
    lines: list[str] = [
        "Job deadline inspection",
        "Observed at: " + datetime_iso(inspection.observed),
        "Counts: " + json_canonical(result["counts"]),
    ]
    explanations: dict[str, str] = {
        "on_time": "Earliest observed completion is at or before the grace cutoff.",
        "late": "Earliest observed completion is after the grace cutoff.",
        "missing": "Grace cutoff reached; no completion has been observed.",
        "pending": "Grace cutoff has not been reached; no completion has been observed.",
    }
    for row in json_array(result["jobs"]):
        fields: list[str] = []
        for column in columns:
            value: Json = row[column]
            text: str = ""
            if not json_is_null(value):
                if column in ["grace_seconds", "lateness_us", "observed_events", "future_events", "duplicate_events"]:
                    text = str(json_int(value))
                else:
                    text = json_string(value)
            fields.append(cell(text))
        csv.append(",".join(fields))
        lines.append(
            "\n" + json_string(row["id"]) + " " + json_canonical(row["label"]) + ": " + json_string(row["status"])
        )
        lines.append("  " + explanations[json_string(row["status"])])
        lines.append(
            "  Cutoff: " + json_string(row["cutoff"]) + "; lateness: " + str(json_int(row["lateness_us"])) + " us"
        )
    jobs: list[Json] = []
    for source in inspection.jobs:
        jobs.append(
            {
                "id": source["id"],
                "label": source["label"],
                "deadline": source["deadline"],
                "grace_seconds": source["grace_seconds"],
            }
        )
    replay: Json = {
        "version": 1,
        "observed_at": datetime_iso(inspection.observed),
        "jobs": "jobs.json",
        "events": "events.json",
        "output": "replayed",
    }
    files: dict[str, bytes] = {
        "report.json": (json_canonical(result) + "\n").encode(),
        "report.txt": ("\n".join(lines) + "\n").encode(),
        "jobs.csv": ("\r\n".join(csv) + "\r\n").encode(),
        "jobs.json": (json_canonical(jobs) + "\n").encode(),
        "events.json": (json_canonical(inspection.events) + "\n").encode(),
        "deadline-job.json": (json_canonical(replay) + "\n").encode(),
    }
    manifest: Json = {}
    total: int = 0
    for name in files:
        total = total + len(files[name])
        assert total <= 4194304, "report bundle exceeds 4 MiB"
        manifest[name] = {"bytes": len(files[name]), "sha256": sha256_digest(sha256_update(sha256_new(), files[name]))}
    files["manifest.json"] = (json_canonical({"version": 1, "files": manifest}) + "\n").encode()
    return files
