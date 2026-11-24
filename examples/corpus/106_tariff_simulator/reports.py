"""Portable exact bills, comparison summaries and actual replay/simulation requests."""

# ruff: noqa: PLC0206 - subset dictionary iteration
from model import text

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
        "tariffs": len(json_array(results["bills"])),
        "ranking": results["ranking"],
        "cheapest": results["cheapest"],
    }


def bundle(mode: str, source: Json, results: Json) -> dict[str, bytes]:
    archive: bytes = encoded({"version": 1, "source": source, "results": results})
    counts: Json = summary(results)
    lines: list[str] = [
        "Fictional electricity tariffs; UTC bands; uniform interval consumption",
        "Exact charges; final total rounded once to two places, ties to even",
        json_canonical(counts),
    ]
    for bill in json_array(results["bills"]):
        lines.append(
            text(bill["id"])
            + ": "
            + text(bill["rounded_total"])
            + " currency units; exact "
            + text(bill["total"]["numerator"])
            + "/"
            + text(bill["total"]["denominator"])
        )
    files: dict[str, bytes] = {
        "archive.json": archive,
        "usage.json": encoded(source),
        "report.json": encoded({"version": 1, "mode": mode, "summary": counts, "archive_sha256": digest(archive)}),
        "report.txt": ("\n".join(lines) + "\n").encode(),
        "replay.json": encoded({"version": 1, "mode": "verify", "input": "archive.json", "output": "replayed"}),
        "simulate.json": encoded({"version": 1, "mode": "simulate", "input": "usage.json", "output": "simulated"}),
    }
    manifest: Json = {}
    for name in files:
        assert len(files[name]) <= 16777216, "export byte limit"
        manifest[name] = {"bytes": len(files[name]), "sha256": digest(files[name])}
    files["manifest.json"] = encoded(manifest)
    return files
