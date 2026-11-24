"""Export full-precision series, reusable experiments, a shared-scale SVG and a verified manifest."""

# ruff: noqa: PLC0206 - subset dictionary iteration
from model import text
from plot import render

from py2rust.stdlib import (
    Json,
    json_array,
    json_canonical,
    sha256_digest,
    sha256_new,
    sha256_update,
)


def encoded(value: Json) -> bytes:
    return (json_canonical(value) + "\n").encode()


def digest(data: bytes) -> str:
    return sha256_digest(sha256_update(sha256_new(), data))


def summary(results: Json) -> Json:
    return results["summary"]


def csv_data(results: Json) -> bytes:
    lines: list[str] = ["id,step,time,population"]
    times: list[Json] = json_array(results["times"])
    for row in json_array(results["series"]):
        values: list[Json] = json_array(row["values"])
        for index in range(len(times)):
            lines.append(
                text(row["id"])
                + ","
                + str(index)
                + ","
                + json_canonical(times[index])
                + ","
                + json_canonical(values[index])
            )
    return ("\n".join(lines) + "\n").encode()


def bundle(mode: str, source: Json, results: Json) -> dict[str, bytes]:
    archive: bytes = encoded({"version": 1, "source": source, "results": results})
    files: dict[str, bytes] = {
        "archive.json": archive,
        "experiment.json": encoded(source),
        "series.json": encoded(results),
        "series.csv": csv_data(results),
        "plot.svg": render(text(source["title"]), results),
        "report.json": encoded(
            {"version": 1, "mode": mode, "summary": summary(results), "archive_sha256": digest(archive)}
        ),
        "replay.json": encoded({"version": 1, "mode": "verify", "input": "archive.json", "output": "replayed"}),
        "simulate.json": encoded({"version": 1, "mode": "simulate", "input": "experiment.json", "output": "simulated"}),
    }
    manifest: Json = {}
    for name in files:
        assert len(files[name]) <= 16777216, "export byte limit"
        manifest[name] = {"bytes": len(files[name]), "sha256": digest(files[name])}
    files["manifest.json"] = encoded(manifest)
    return files
