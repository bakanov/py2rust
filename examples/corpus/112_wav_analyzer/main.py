"""Analyze and normalize a complete mono PCM WAV, or verify its portable processing archive."""

# ruff: noqa: BLE001, LOG015, PLR1711 - fatal job boundary and explicit returns

import logging

from binary import encoded, exact, text
from documents import Document, absolute, present, publish, read
from pcm import Wave, decode
from processing import Processed, process
from reports import bundle

from py2rust.stdlib import (
    Json,
    env_get,
    json_canonical,
    json_int,
    json_loads_unique,
    path_parent,
    path_resolve,
    process_exit,
)


def run() -> None:
    request: Document = read(absolute(env_get("WAV_CONFIG", "wav-job.json"), path_resolve(".")), 65536)
    config: Json = json_loads_unique(request.data.decode())
    mode: str = text(config["mode"])
    exact(
        config,
        (
            ["version", "mode", "input", "output", "settings"]
            if mode == "process"
            else ["version", "mode", "input", "output"]
        ),
    )
    assert json_int(config["version"]) == 1 and mode in ["process", "verify"], "unsupported request version or mode"
    base: str = path_parent(request.path)
    output: str = absolute(text(config["output"]), base)
    assert not present(output), "output already exists"
    document: Document = read(absolute(text(config["input"]), base), 16777216 if mode == "verify" else 2097152)
    source: bytes = document.data
    archive: Json = None
    if mode == "verify":
        archive = json_loads_unique(source.decode())
        exact(archive, ["version", "source_hex", "settings", "results"])
        assert json_int(archive["version"]) == 1, "unsupported archive version"
        spelling: str = text(archive["source_hex"])
        assert len(spelling) <= 4194304, "source byte limit"
        source = bytes.fromhex(spelling)
        assert source.hex() == spelling, "expected canonical lowercase hex"
    settings: Json = archive["settings"] if mode == "verify" else config["settings"]
    wave: Wave = decode(source)
    processed: Processed = process(wave, settings, len(source))
    if mode == "verify":
        assert encoded(archive["results"]) == encoded(processed.results), "archive differs from recomputed processing"
    publish(output, bundle(mode, source, wave, settings, processed), [request, document])
    print(
        json_canonical(
            {
                "samples": len(wave.samples),
                "clipped_low": processed.results["clipped_low"],
                "clipped_high": processed.results["clipped_high"],
            }
        )
    )
    return


def main() -> None:
    try:
        run()
    except Exception as error:
        logging.error(str(error))
        process_exit(2)
    return


if __name__ == "__main__":
    main()
