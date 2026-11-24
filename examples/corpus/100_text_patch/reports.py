"""Readable quoted-line hunks and portable requests bound to exact input snapshots."""

# ruff: noqa: PLC0206 - explicit dictionary iteration
from text_model import digest

from py2rust.stdlib import Json, json_array, json_canonical, json_int, json_string


def encoded(value: Json) -> bytes:
    return (json_canonical(value) + "\n").encode()


def request(mode: str, output: str, base: str, other: str, context: int) -> Json:
    config: Json = {"version": 1, "mode": mode, "output": output, "base": base}
    if mode == "diff":
        config["target"] = other
        config["context"] = context
    else:
        config["patch"] = other
    return config


def bundle(mode: str, before: bytes, after: bytes, patch: Json, patch_bytes: bytes) -> dict[str, bytes]:
    removed: int = 0
    added: int = 0
    review: list[str] = ["Line diff: quoted UTF-8 tokens; offsets are zero-based"]
    rows: list[Json] = json_array(patch["hunks"])
    for hunk in rows:
        review.append(
            "@@ old "
            + str(json_int(hunk["old_start"]))
            + ","
            + str(json_int(hunk["old_count"]))
            + " new "
            + str(json_int(hunk["new_start"]))
            + ","
            + str(json_int(hunk["new_count"]))
            + " @@"
        )
        for operation in json_array(hunk["ops"]):
            kind: str = json_string(operation["op"])
            removed = removed + (1 if kind == "-" else 0)
            added = added + (1 if kind == "+" else 0)
            review.append(kind + json_canonical(operation["text"]))
    old_lines: int = json_int(patch["before"]["lines"])
    new_lines: int = json_int(patch["after"]["lines"])
    report: Json = {
        "version": 1,
        "mode": mode,
        "changed": before != after,
        "before": patch["before"],
        "after": patch["after"],
        "patch_sha256": digest(patch_bytes),
        "statistics": {
            "removed": removed,
            "added": added,
            "common": old_lines - removed,
            "hunks": len(rows),
            "cells": (old_lines + 1) * (new_lines + 1),
        },
    }
    context: int = json_int(patch["context"])
    files: dict[str, bytes] = {
        "base.txt": before,
        "patch.json": patch_bytes,
        "report.json": encoded(report),
        "diff.txt": ("\n".join(review) + "\n").encode(),
    }
    if mode == "diff":
        files["target.txt"] = after
        files["apply.json"] = encoded(request("apply", "applied", "base.txt", "patch.json", context))
        files["replay.json"] = encoded(request("diff", "replayed", "base.txt", "target.txt", context))
        files["check-applied.json"] = encoded(request("diff", "checked", "applied/result.txt", "target.txt", context))
    else:
        files["result.txt"] = after
        files["replay.json"] = encoded(request("apply", "replayed", "base.txt", "patch.json", context))
        files["recheck.json"] = encoded(request("diff", "rechecked", "base.txt", "result.txt", context))
    manifest: Json = {}
    for name in files:
        assert len(files[name]) <= 1048576, "output file budget exceeded"
        manifest[name] = {"bytes": len(files[name]), "sha256": digest(files[name])}
    files["manifest.json"] = encoded(manifest)
    return files
