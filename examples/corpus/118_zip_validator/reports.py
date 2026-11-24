"""Readable manifests and exact archive bytes, with reusable inspection and replay requests."""

# ruff: noqa: PLC0206 - subset dictionary iteration
from binary import digest, encoded

from py2rust.stdlib import Json, pretty


def bundle(mode: str, source: bytes, settings: Json, results: Json) -> dict[str, bytes]:
    archive: bytes = encoded({"version": 1, "source_hex": source.hex(), "limits": settings, "results": results})
    files: dict[str, bytes] = {
        "source.zip": source,
        "archive.json": archive,
        "entries.json": encoded(results["entries"]),
        "report.json": encoded({"version": 1, "mode": mode, "results": results, "archive_sha256": digest(archive)}),
        "report.txt": (pretty(results) + "\n").encode(),
        "inspect.json": encoded(
            {"version": 1, "mode": "inspect", "input": "source.zip", "output": "inspected", "limits": settings}
        ),
        "replay.json": encoded({"version": 1, "mode": "verify", "input": "archive.json", "output": "replayed"}),
    }
    manifest: Json = {}
    for name in files:
        assert len(files[name]) <= 67108864, "export byte limit"
        manifest[name] = {"bytes": len(files[name]), "sha256": digest(files[name])}
    files["manifest.json"] = encoded(manifest)
    return files
