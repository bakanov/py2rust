"""Publish the exact binary with readable, escaped diagnostics and reusable requests."""

# ruff: noqa: PLC0206 - subset dictionary iteration

from binary import digest, encoded

from py2rust.stdlib import Json, json_array, json_canonical, pretty


def escaped(value: str) -> str:
    return value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def html(results: Json) -> bytes:
    rows: list[str] = [
        '<!doctype html><html lang="en"><meta charset="utf-8"><title>PNG structure report</title>',
        (
            "<style>body{font:15px system-ui;margin:40px;color:#233047;background:#f8fafc}table{border-"
            "collapse:collapse;width:100%}td,th{padding:8px;border:1px solid #ccd5df;text-align:left}pr"
            "e{white-space:pre-wrap;overflow-wrap:anywhere}summary{cursor:pointer}h1{color:#17578e}</st"
            "yle>"
        ),
        (
            "<h1>PNG structure report</h1><p>Structural inspection only. Image data and compressed meta"
            "data are not decompressed.</p>"
        ),
        "<h2>Summary</h2><pre>" + escaped(pretty(results["summary"])) + "</pre>",
        "<h2>Image header</h2><pre>" + escaped(pretty(results["header"])) + "</pre>",
        "<h2>Findings</h2><pre>" + escaped(pretty(results["errors"])) + "</pre>",
        "<h2>Uninspected content</h2><pre>" + escaped(pretty(results["unchecked"])) + "</pre>",
        (
            "<h2>Chunks</h2><table><tr><th>Index</th><th>Offset</th><th>Type</th><th>Bytes</th><th>CRC<"
            "/th><th>Metadata</th></tr>"
        ),
    ]
    for chunk in json_array(results["chunks"]):
        cells: list[str] = []
        for key in ["index", "offset", "type", "length", "crc_ok"]:
            cells.append("<td>" + escaped(json_canonical(chunk[key])) + "</td>")
        cells.append("<td><details><summary>Inspect</summary><pre>" + escaped(pretty(chunk)) + "</pre></details></td>")
        rows.append("<tr>" + "".join(cells) + "</tr>")
    rows.append("</table></html>")
    return ("\n".join(rows) + "\n").encode()


def bundle(mode: str, source: bytes, results: Json) -> dict[str, bytes]:
    archive: bytes = encoded({"version": 1, "source_hex": source.hex(), "results": results})
    files: dict[str, bytes] = {
        "image.png": source,
        "archive.json": archive,
        "chunks.json": encoded(results["chunks"]),
        "report.json": encoded({"version": 1, "mode": mode, "results": results, "archive_sha256": digest(archive)}),
        "report.html": html(results),
        "inspect.json": encoded({"version": 1, "mode": "inspect", "input": "image.png", "output": "inspected"}),
        "replay.json": encoded({"version": 1, "mode": "verify", "input": "archive.json", "output": "replayed"}),
    }
    manifest: Json = {}
    for name in files:
        assert len(files[name]) <= 67108864, "export byte limit"
        manifest[name] = {"bytes": len(files[name]), "sha256": digest(files[name])}
    files["manifest.json"] = encoded(manifest)
    return files
