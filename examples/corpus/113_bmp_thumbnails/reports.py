"""Publish original images, usable thumbnails, the contact sheet and editable rebuild requests."""

# ruff: noqa: PLC0206 - subset dictionary iteration

from layout import Sheet
from model import Source, digest, encoded

from py2rust.stdlib import Json, pretty


def escaped(value: str) -> str:
    return value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def bundle(mode: str, sources: list[Source], settings: Json, sheet: Sheet) -> dict[str, bytes]:
    files: dict[str, bytes] = {"sheet.bmp": sheet.bitmap}
    originals: list[Json] = []
    thumbnails: list[Json] = []
    archived: list[Json] = []
    html: list[str] = [
        '<!doctype html><html lang="en"><meta charset="utf-8"><title>BMP contact sheet</title>',
        "<style>body{font:16px system-ui;margin:32px;background:#f8fafc;color:#263449}",
        "img{max-width:100%;image-rendering:pixelated}figure{display:inline-block;vertical-align:top;margin:16px}",
        "figcaption{max-width:256px;overflow-wrap:anywhere}pre{white-space:pre-wrap}</style>",
        "<h1>BMP contact sheet</h1><p>Nearest-neighbor thumbnails. RGB values preserved without color management.</p>",
        '<a href="sheet.bmp"><img src="sheet.bmp" alt="Combined contact sheet"></a><h2>Individual thumbnails</h2>',
    ]
    for index in range(len(sources)):
        source: Source = sources[index]
        original_name: str = "source-" + str(index) + ".bmp"
        thumbnail_name: str = "thumbnail-" + str(index) + ".bmp"
        files[original_name] = source.data
        files[thumbnail_name] = sheet.thumbnails[index]
        originals.append({"name": source.name, "path": original_name})
        thumbnails.append({"name": source.name, "path": thumbnail_name})
        archived.append({"name": source.name, "source_hex": source.data.hex()})
        html.append(
            '<figure><a href="'
            + thumbnail_name
            + '"><img src="'
            + thumbnail_name
            + '" alt="'
            + escaped(source.name)
            + '"></a><figcaption>'
            + escaped(source.name)
            + "</figcaption></figure>"
        )
    html.append("<h2>Layout</h2><pre>" + escaped(pretty(settings)) + "</pre></html>")
    files["index.html"] = ("\n".join(html) + "\n").encode()
    files["project.json"] = encoded({"version": 1, "settings": settings, "images": originals})
    files["thumbnails.json"] = encoded({"version": 1, "settings": settings, "images": thumbnails})
    files["archive.json"] = encoded({"version": 1, "settings": settings, "images": archived, "results": sheet.results})
    files["report.json"] = (pretty({"version": 1, "mode": mode, "results": sheet.results}) + "\n").encode()
    files["rebuild.json"] = encoded({"version": 1, "mode": "build", "input": "project.json", "output": "rebuilt"})
    files["retile.json"] = encoded({"version": 1, "mode": "build", "input": "thumbnails.json", "output": "retiled"})
    files["replay.json"] = encoded({"version": 1, "mode": "verify", "input": "archive.json", "output": "replayed"})
    manifest: Json = {}
    for name in files:
        assert len(files[name]) <= 33554432, "export byte limit"
        manifest[name] = {"bytes": len(files[name]), "sha256": digest(files[name])}
    files["manifest.json"] = encoded(manifest)
    return files
