"""Export reusable fixtures, exact standings and a compact text table in one verifiable bundle."""

# ruff: noqa: PLC0206 - subset dictionary iteration
from model import display, text

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


def summary(results: Json) -> Json:
    return {
        "teams": results["teams"],
        "played": results["played"],
        "scheduled": results["scheduled"],
        "leaders": results["leaders"],
    }


def bundle(mode: str, source: Json, results: Json) -> dict[str, bytes]:
    archive: bytes = encoded({"version": 1, "source": source, "results": results})
    lines: list[str] = [display(text(results["title"])), "Rank\tTeam\tP\tW\tD\tL\tGF\tGA\tGD\tPts"]
    for row in json_array(results["standings"]):
        fields: list[str] = [str(json_int(row["rank"])), display(text(row["name"]))]
        for key in ["played", "won", "drawn", "lost", "goals_for", "goals_against", "difference", "points"]:
            fields.append(str(json_int(row[key])))
        lines.append("\t".join(fields))
    files: dict[str, bytes] = {
        "archive.json": archive,
        "fixtures.json": encoded(source),
        "standings.json": encoded(results),
        "table.txt": ("\n".join(lines) + "\n").encode(),
        "report.json": encoded(
            {"version": 1, "mode": mode, "summary": summary(results), "archive_sha256": digest(archive)}
        ),
        "replay.json": encoded({"version": 1, "mode": "verify", "input": "archive.json", "output": "replayed"}),
        "rank.json": encoded({"version": 1, "mode": "rank", "input": "fixtures.json", "output": "ranked"}),
    }
    manifest: Json = {}
    for name in files:
        assert len(files[name]) <= 16777216, "export byte limit"
        manifest[name] = {"bytes": len(files[name]), "sha256": digest(files[name])}
    files["manifest.json"] = encoded(manifest)
    return files
