"""Publish replayable plans and independently reusable scaled-recipe sources and requests."""

# ruff: noqa: PLC0206 - subset dictionary iteration
from model import parse, text

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
    return {
        "week_start": results["week_start"],
        "selections": len(json_array(results["selections"])),
        "shopping_rows": len(json_array(results["shopping"])),
    }


def scaled_source(results: Json, entry: Json) -> Json:
    ingredients: list[Json] = []
    for item in json_array(entry["ingredients"]):
        ingredients.append({"name": item["name"], "quantity": item["quantity"], "unit": item["unit"]})
    recipe: Json = {
        "id": entry["recipe"],
        "title": entry["title"],
        "servings": entry["servings"],
        "ingredients": ingredients,
    }
    source: Json = {
        "version": 1,
        "week_start": results["week_start"],
        "recipes": [recipe],
        "plan": [{"day": entry["day"], "recipe": entry["recipe"], "portions": entry["servings"]}],
    }
    parse(source)
    return source


def bundle(mode: str, source: Json, results: Json) -> dict[str, bytes]:
    archive: bytes = encoded({"version": 1, "source": source, "results": results})
    counts: Json = summary(results)
    lines: list[str] = [
        "Weekly shopping: exact quantities, grouped only within compatible units",
        json_canonical(counts),
    ]
    for row in json_array(results["shopping"]):
        lines.append(text(row["name"]) + ": " + text(row["quantity"]) + " " + text(row["unit"]))
    files: dict[str, bytes] = {
        "archive.json": archive,
        "cookbook.json": encoded(source),
        "report.json": encoded({"version": 1, "mode": mode, "summary": counts, "archive_sha256": digest(archive)}),
        "shopping.txt": ("\n".join(lines) + "\n").encode(),
        "replay.json": encoded({"version": 1, "mode": "verify", "input": "archive.json", "output": "replayed"}),
        "plan.json": encoded({"version": 1, "mode": "plan", "input": "cookbook.json", "output": "planned"}),
    }
    entries: list[Json] = json_array(results["selections"])
    for index in range(len(entries)):
        stem: str = "scaled-" + str(index)
        files[stem + ".json"] = encoded(scaled_source(results, entries[index]))
        files[stem + "-job.json"] = encoded(
            {"version": 1, "mode": "plan", "input": stem + ".json", "output": stem + "-plan"}
        )
    manifest: Json = {}
    for name in files:
        assert len(files[name]) <= 16777216, "export byte limit"
        manifest[name] = {"bytes": len(files[name]), "sha256": digest(files[name])}
    files["manifest.json"] = encoded(manifest)
    return files
