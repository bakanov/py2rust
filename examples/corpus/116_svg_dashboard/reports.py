"""Portable data, recomputed geometry, standalone HTML/SVG and editable rendering requests."""

# ruff: noqa: PLC0206 - subset dictionary iteration

from model import digest, encoded, escaped, text
from render import render

from py2rust.stdlib import Json, pretty


def bundle(mode: str, source: bytes, columns: int, results: Json) -> dict[str, bytes]:
    svg: bytes = render(results)
    html: str = '<!doctype html><html lang="en"><meta charset="utf-8"><title>' + escaped(text(results["title"]))
    html = html + "</title><style>body{margin:0;background:#f1f5f9}main{overflow:auto}svg{display:block}</style><main>"
    html = html + svg.decode() + "</main></html>\n"
    files: dict[str, bytes] = {
        "dashboard.svg": svg,
        "index.html": html.encode(),
        "data.json": source,
        "archive.json": encoded({"version": 1, "source_hex": source.hex(), "columns": columns, "results": results}),
        "report.json": (pretty({"version": 1, "mode": mode, "results": results}) + "\n").encode(),
        "render.json": encoded(
            {"version": 1, "mode": "render", "input": "data.json", "output": "rendered", "columns": columns}
        ),
        "replay.json": encoded({"version": 1, "mode": "verify", "input": "archive.json", "output": "replayed"}),
    }
    manifest: Json = {}
    for name in files:
        assert len(files[name]) <= 16777216, "export byte limit"
        manifest[name] = {"bytes": len(files[name]), "sha256": digest(files[name])}
    files["manifest.json"] = encoded(manifest)
    return files
