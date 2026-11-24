"""Publish portable telemetry input, recomputable statistics and a concise text summary."""

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
    counts: Json = {"analyzed": 0, "rejected": 0, "samples": 0, "gaps": 0, "outliers": 0}
    for result in results:
        state: str = text(result["status"])
        counts[state] = json_int(counts[state]) + 1
        if state == "analyzed":
            counts["samples"] = json_int(counts["samples"]) + json_int(result["samples"])
            counts["gaps"] = json_int(counts["gaps"]) + len(json_array(result["gaps"]))
            counts["outliers"] = json_int(counts["outliers"]) + json_int(result["outliers"])
    return counts


def bundle(mode: str, source: Json, results: list[Json]) -> dict[str, bytes]:
    counts: Json = summary(results)
    archive: bytes = encoded({"version": 1, "source": source, "results": results})
    lines: list[str] = ["Telemetry trends: trailing count windows; population variance", json_canonical(counts)]
    for result in results:
        name: str = text(result["id"])
        if text(result["status"]) == "rejected":
            lines.append(name + ": rejected: " + text(result["reason"]))
        else:
            lines.append(
                name
                + ": "
                + str(json_int(result["samples"]))
                + " samples; "
                + str(json_int(result["outliers"]))
                + " outliers; "
                + str(len(json_array(result["gaps"])))
                + " gaps; mean "
                + json_canonical(result["statistics"]["mean"])
                + "; variance "
                + json_canonical(result["statistics"]["population_variance"])
            )
    files: dict[str, bytes] = {
        "archive.json": archive,
        "telemetry.json": encoded(source),
        "report.json": encoded({"version": 1, "mode": mode, "summary": counts, "archive_sha256": digest(archive)}),
        "report.txt": ("\n".join(lines) + "\n").encode(),
        "replay.json": encoded({"version": 1, "mode": "verify", "input": "archive.json", "output": "replayed"}),
        "analyze.json": encoded({"version": 1, "mode": "analyze", "input": "telemetry.json", "output": "analyzed"}),
    }
    manifest: Json = {}
    for name in files:
        assert len(files[name]) <= 16777216, "export byte limit"
        manifest[name] = {"bytes": len(files[name]), "sha256": digest(files[name])}
    files["manifest.json"] = encoded(manifest)
    return files
