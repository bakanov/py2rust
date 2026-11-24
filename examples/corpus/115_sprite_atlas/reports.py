"""Publish originals, actual atlas extractions, coordinates and directly usable packing requests."""

# ruff: noqa: PLC0206 - subset dictionary iteration

from model import Sprite, digest, encoded
from packing import Atlas, extract
from ppm import encode
from preview import preview

from py2rust.stdlib import Json, pretty


def bundle(mode: str, sprites: list[Sprite], settings: Json, atlas: Atlas) -> dict[str, bytes]:
    files: dict[str, bytes] = {
        "atlas.ppm": encode(atlas.image),
        "coordinates.json": encoded(atlas.results),
        "preview.svg": preview(atlas),
    }
    originals: list[Json] = []
    extracted: list[Json] = []
    archived: list[Json] = []
    for sprite in sprites:
        name: str = "original-" + str(sprite.index) + ".ppm"
        files[name] = sprite.data
        originals.append({"name": sprite.name, "path": name})
        extracted.append({"name": sprite.name, "path": "extracted-" + str(sprite.index) + ".ppm"})
        archived.append({"name": sprite.name, "source_hex": sprite.data.hex()})
    for placement in atlas.placements:
        files["extracted-" + str(placement.sprite.index) + ".ppm"] = encode(extract(atlas.image, placement))
    files["sprites.json"] = encoded({"version": 1, "settings": settings, "sprites": originals})
    files["extracted.json"] = encoded({"version": 1, "settings": settings, "sprites": extracted})
    files["archive.json"] = encoded({"version": 1, "settings": settings, "sprites": archived, "results": atlas.results})
    files["report.json"] = (pretty({"version": 1, "mode": mode, "results": atlas.results}) + "\n").encode()
    files["repack.json"] = encoded({"version": 1, "mode": "pack", "input": "sprites.json", "output": "repacked"})
    files["pack-extracted.json"] = encoded(
        {"version": 1, "mode": "pack", "input": "extracted.json", "output": "extracted"}
    )
    files["replay.json"] = encoded({"version": 1, "mode": "verify", "input": "archive.json", "output": "replayed"})
    manifest: Json = {}
    for name in files:
        assert len(files[name]) <= 33554432, "export byte limit"
        manifest[name] = {"bytes": len(files[name]), "sha256": digest(files[name])}
    files["manifest.json"] = encoded(manifest)
    return files
