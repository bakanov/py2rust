"""Portable original/settings replay plus normalized PCM, all samples and bounded preview."""

# ruff: noqa: PLC0206 - subset dictionary iteration

from binary import digest, encoded
from pcm import Wave
from plot import render
from processing import Processed

from py2rust.stdlib import Json, pretty


def bundle(mode: str, source: bytes, wave: Wave, settings: Json, processed: Processed) -> dict[str, bytes]:
    archive: bytes = encoded(
        {"version": 1, "source_hex": source.hex(), "settings": settings, "results": processed.results}
    )
    csv: list[str] = ["sample,input,output"]
    for index in range(len(wave.samples)):
        csv.append(str(index) + "," + str(wave.samples[index]) + "," + str(processed.samples[index]))
    files: dict[str, bytes] = {
        "original.wav": source,
        "normalized.wav": processed.audio,
        "archive.json": archive,
        "report.json": (pretty({"version": 1, "mode": mode, "results": processed.results}) + "\n").encode(),
        "waveform.svg": render(processed.results),
        "samples.csv": ("\n".join(csv) + "\n").encode(),
        "process.json": encoded(
            {"version": 1, "mode": "process", "input": "original.wav", "settings": settings, "output": "processed"}
        ),
        "replay.json": encoded({"version": 1, "mode": "verify", "input": "archive.json", "output": "replayed"}),
    }
    manifest: Json = {}
    for name in files:
        assert len(files[name]) <= 16777216, "export byte limit"
        manifest[name] = {"bytes": len(files[name]), "sha256": digest(files[name])}
    files["manifest.json"] = encoded(manifest)
    return files
