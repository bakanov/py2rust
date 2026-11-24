"""Create readable reductions, canonical audit archives and portable solve/replay requests."""

# ruff: noqa: PLC0206 - subset dictionary iteration

from model import text

from py2rust.stdlib import (
    Json,
    json_array,
    json_canonical,
    json_int,
    sha256_digest,
    sha256_new,
    sha256_update,
)


def encoded(value: Json) -> bytes:
    return (json_canonical(value) + "\n").encode()


def digest(data: bytes) -> str:
    return sha256_digest(sha256_update(sha256_new(), data))


def summary(results: list[Json]) -> Json:
    counts: Json = {"solved": 0, "rejected": 0, "finite": 0, "open": 0, "short": 0}
    for result in results:
        status: str = text(result["status"])
        counts[status] = json_int(counts[status]) + 1
        if status == "solved":
            state: str = text(result["equivalent"]["state"])
            counts[state] = json_int(counts[state]) + 1
    return counts


def resistance_label(value: Json) -> str:
    state: str = text(value["state"])
    if state == "open":
        return "open circuit"
    if state == "short":
        return "short circuit (0 ohms)"
    return json_canonical(value["ohms"]) + " ohms"


def bundle(mode: str, rows: list[Json], results: list[Json]) -> dict[str, bytes]:
    counts: Json = summary(results)
    archive: bytes = encoded({"version": 1, "cases": rows, "results": results})
    lines: list[str] = ["Ideal DC series/parallel circuits", json_canonical(counts)]
    for result in results:
        name: str = text(result["id"])
        if text(result["status"]) == "rejected":
            lines.append(name + ": rejected: " + text(result["reason"]))
        else:
            lines.append(name + ": " + resistance_label(result["equivalent"]))
            for step in json_array(result["steps"]):
                lines.append(
                    "  "
                    + text(step["id"])
                    + " ("
                    + text(step["kind"])
                    + "): "
                    + resistance_label(step["equivalent"])
                    + "; "
                    + text(step["rule"])
                )
    files: dict[str, bytes] = {
        "archive.json": archive,
        "networks.json": encoded({"version": 1, "cases": rows}),
        "report.json": encoded({"version": 1, "mode": mode, "summary": counts, "archive_sha256": digest(archive)}),
        "report.txt": ("\n".join(lines) + "\n").encode(),
        "replay.json": encoded({"version": 1, "mode": "verify", "input": "archive.json", "output": "replayed"}),
        "solve.json": encoded({"version": 1, "mode": "solve", "input": "networks.json", "output": "solved"}),
    }
    manifest: Json = {}
    for name in files:
        assert len(files[name]) <= 4194304, "export byte limit"
        manifest[name] = {"bytes": len(files[name]), "sha256": digest(files[name])}
    files["manifest.json"] = encoded(manifest)
    return files
