"""Publish readable schedules and an exact portable rule bundle for later replay."""

# ruff: noqa: C414 - sorting requires an explicit list in the executable subset

# ruff: noqa: PLC0206 - supported subset dictionary iteration
from schedule import Inspection

from py2rust.stdlib import (
    Json,
    base64_encode,
    json_array,
    json_canonical,
    json_string,
    sha256_digest,
    sha256_new,
    sha256_update,
)


def cell(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def render(inspection: Inspection, result: Json) -> dict[str, bytes]:
    csv: list[str] = ["id,label,status,source_zone,requested_local,target_zone,local,utc,offset_seconds,abbreviation"]
    lines: list[str] = ["Cross-timezone appointments", "Counts: " + json_canonical(result["counts"])]
    for row in json_array(result["appointments"]):
        item: Json = row["appointment"]
        status: str = json_string(row["status"])
        prefix: list[str] = [
            json_string(item["id"]),
            json_string(item["label"]),
            status,
            json_string(item["zone"]),
            json_string(item["local"]),
        ]
        lines.append("\n" + prefix[0] + " " + json_canonical(item["label"]) + ": " + status)
        lines.append("  Requested: " + prefix[4] + " " + prefix[3] + "; " + json_string(row["reason"]))
        destinations: list[Json] = json_array(row["destinations"])
        if len(destinations) == 0:
            fields: list[str] = []
            for text in prefix + ["", "", "", "", ""]:
                fields.append(cell(text))
            csv.append(",".join(fields))
        for destination in destinations:
            time: Json = destination["time"]
            name: str = json_string(destination["zone"])
            fields: list[str] = []
            for text in prefix + [
                name,
                json_string(time["local"]),
                json_string(time["utc"]),
                json_canonical(time["offset_seconds"]),
                json_string(time["abbreviation"]),
            ]:
                fields.append(cell(text))
            csv.append(",".join(fields))
            lines.append("  " + name + ": " + json_string(time["local"]) + " " + json_string(time["abbreviation"]))
    zones: Json = {}
    for name in sorted(list(inspection.zones)):
        zones[name] = base64_encode(inspection.zones[name])
    replay: Json = {
        "version": 1,
        "tzdata": "zones.json",
        "targets": inspection.targets,
        "appointments": inspection.appointments,
        "output": "replayed",
    }
    files: dict[str, bytes] = {
        "report.json": (json_canonical(result) + "\n").encode(),
        "report.txt": ("\n".join(lines) + "\n").encode(),
        "schedule.csv": ("\r\n".join(csv) + "\r\n").encode(),
        "zones.json": (json_canonical(zones) + "\n").encode(),
        "timezone-job.json": (json_canonical(replay) + "\n").encode(),
    }
    manifest: Json = {}
    total: int = 0
    for name in files:
        total = total + len(files[name])
        assert total <= 4194304, "report bundle exceeds 4 MiB"
        manifest[name] = {"bytes": len(files[name]), "sha256": sha256_digest(sha256_update(sha256_new(), files[name]))}
    files["manifest.json"] = (json_canonical({"version": 1, "files": manifest}) + "\n").encode()
    return files
