"""Portable frame archive, readable transcript and an actual replay request."""

# ruff: noqa: PLC0206 - subset dictionary iteration
from model import empty, text

from py2rust.stdlib import (
    Json,
    json_array,
    json_canonical,
    json_is_null,
    pretty,
    sha256_digest,
    sha256_new,
    sha256_update,
)


def encoded(value: Json) -> bytes:
    return (json_canonical(value) + "\n").encode()


def bundle(config: Json, events: list[Json], state: Json, interrupted: int) -> dict[str, bytes]:
    transcript: list[str] = []
    errors: int = 0
    for record in events:
        if text(record["status"]) not in ["updated", "unchanged"]:
            errors = errors + 1
        for line in json_array(record["lines"]):
            transcript.append(text(line) + "\n")
        transcript.append("\n")
    files: dict[str, bytes] = {
        "archive.json": encoded({"version": 1, "settings": config, "events": events, "signal": interrupted}),
        "transcript.txt": "".join(transcript).encode(),
        "snapshot.json": encoded(empty() if json_is_null(state) else state),
        "watch.json": encoded(
            {
                "version": 1,
                "mode": "watch",
                "input": "snapshot.json",
                "output": "watched",
                "columns": config["columns"],
                "refreshes": config["refreshes"],
                "interval_ms": config["interval_ms"],
            }
        ),
        "report.json": (
            pretty({"version": 1, "frames": len(events), "errors": errors, "signal": interrupted, "last": state}) + "\n"
        ).encode(),
        "replay.json": encoded({"version": 1, "mode": "replay", "input": "archive.json", "output": "replayed"}),
    }
    manifest: Json = {}
    for name in files:
        assert len(files[name]) <= 16777216, "export byte limit"
        manifest[name] = {"bytes": len(files[name]), "sha256": sha256_digest(sha256_update(sha256_new(), files[name]))}
    files["manifest.json"] = encoded(manifest)
    return files
