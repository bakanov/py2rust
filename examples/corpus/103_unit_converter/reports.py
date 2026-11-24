"""Export inspectable conversion results, unit definitions and portable replay/continuation requests."""

# ruff: noqa: PLC0206, C414 - explicit subset iteration
from conversion import describe, text
from notebook import digest, encoded
from units import Unit

from py2rust.stdlib import Json, json_canonical, json_int


def bundle(
    mode: str, before: int, entries: list[Json], outcomes: list[Json], available: dict[str, Unit]
) -> dict[str, bytes]:
    counts: Json = {"converted": 0, "duplicate": 0, "rejected": 0}
    for row in outcomes:
        status: str = text(row["status"])
        counts[status] = json_int(counts[status]) + 1
    data: bytes = encoded({"version": 1, "entries": entries})
    report: Json = {
        "version": 1,
        "mode": mode,
        "before_entries": before,
        "entries": len(entries),
        "summary": counts,
        "notebook_sha256": digest(data),
        "outcomes": outcomes,
    }
    lines: list[str] = ["Conversion notebook: " + str(len(entries)) + " entries; " + json_canonical(counts)]
    for stored in entries:
        request: Json = stored["request"]
        lines.append(
            text(request["id"])
            + ": "
            + text(request["quantity"])
            + " = "
            + json_canonical(stored["result"]["converted"])
            + " "
            + text(request["to"])
        )
    for row in outcomes:
        if text(row["status"]) == "rejected":
            lines.append("rejected " + str(json_int(row["index"])) + ": " + text(row["reason"]))
    definitions: Json = {}
    for name in sorted(list(available)):
        definitions[name] = describe(available[name])
    files: dict[str, bytes] = {
        "notebook.json": data,
        "report.json": encoded(report),
        "report.txt": ("\n".join(lines) + "\n").encode(),
        "units.json": encoded(definitions),
        "replay.json": encoded({"version": 1, "mode": "verify", "notebook": "notebook.json", "output": "replayed"}),
        "continue.json": encoded(
            {"version": 1, "mode": "convert", "notebook": "notebook.json", "output": "continued", "conversions": []}
        ),
    }
    manifest: Json = {}
    for name in files:
        assert len(files[name]) <= 1048576, "export byte limit"
        manifest[name] = {"bytes": len(files[name]), "sha256": digest(files[name])}
    files["manifest.json"] = encoded(manifest)
    return files
