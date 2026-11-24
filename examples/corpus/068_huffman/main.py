"""Compress or decompress a binary file and atomically export bytes and codebook statistics."""

# ruff: noqa: PLR1711, BLE001, LOG015, PLC0206 - explicit returns and subset operations

import logging

from codebook import frequencies, spelling
from codec import Block, decode, digest, encode, parse
from documents import Document, absolute, checkpoint, present, publish, read, unchanged

from py2rust.stdlib import (
    Json,
    env_get,
    json_canonical,
    json_keys,
    json_loads,
    json_string,
    path_parent,
    path_resolve,
    pretty,
    process_exit,
)


def statistics(operation: str, original: bytes, container: bytes, block: Block) -> Json:
    counts: list[int] = frequencies(original)
    rows: list[Json] = []
    maximum: int = 0
    for symbol in range(256):
        if symbol in block.codes:
            entry: tuple[int, int] = block.codes[symbol]
            maximum = max(maximum, entry[1])
            rows.append(
                {
                    "symbol": symbol,
                    "frequency": counts[symbol],
                    "length": entry[1],
                    "bits": spelling(entry[0], entry[1]),
                }
            )
    ratio: Json = None
    if len(original) > 0:
        ratio = len(container) * 1000000 // len(original)
    return {
        "version": 1,
        "operation": operation,
        "original_bytes": len(original),
        "container_bytes": len(container),
        "payload_bits": block.bit_count,
        "payload_bytes": len(block.payload),
        "padding_bits": len(block.payload) * 8 - block.bit_count,
        "overhead_bytes": 82 + 2 * len(block.codes),
        "saved_bytes": len(original) - len(container),
        "container_ratio_ppm": ratio,
        "original_sha256": digest(original).hex(),
        "container_sha256": digest(container).hex(),
        "symbols": len(rows),
        "maximum_code_length": maximum,
        "codebook": rows,
    }


def run() -> int:
    mode: str = env_get("HUFFMAN_MODE", "preview")
    assert mode in ["preview", "write"], "invalid Huffman mode"
    path: str = absolute(env_get("HUFFMAN_CONFIG", "huffman-job.json"), path_resolve("."))
    configuration: Document = read(path, 65536)
    config: Json = json_loads(configuration.data.decode())
    assert json_keys(config) == ["input", "operation", "output"], "unexpected configuration fields"
    operation: str = json_string(config["operation"])
    assert operation in ["compress", "decompress"], "invalid Huffman operation"
    base: str = path_parent(path)
    output: str = absolute(json_string(config["output"]), base)
    assert not present(output), "output directory already exists"
    source: Document = read(
        absolute(json_string(config["input"]), base), 1048576 if operation == "compress" else 4194898
    )
    container: bytes = source.data
    original: bytes = source.data
    if operation == "compress":
        container = encode(original)
    block: Block = parse(container)
    if operation == "decompress":
        original = decode(block)
    report: Json = statistics(operation, original, container, block)
    filename: str = "archive.phf" if operation == "compress" else "decoded.bin"
    files: dict[str, bytes] = {
        filename: container if operation == "compress" else original,
        "report.json": (json_canonical(report) + "\n").encode(),
        "codebook.json": (pretty(report["codebook"]) + "\n").encode(),
    }
    checksums: Json = {}
    for name in files:
        checksums[name] = {"bytes": len(files[name]), "sha256": digest(files[name]).hex()}
    files["manifest.json"] = (pretty({"version": 1, "files": checksums}) + "\n").encode()
    documents: list[Document] = [configuration, source]
    checkpoint("validated")
    unchanged(documents)
    if mode == "write":
        publish(output, files, documents)
    print(json_canonical(report))
    return 0


def main() -> None:
    try:
        process_exit(run())
    except Exception as error:
        logging.error(str(error))
        process_exit(2)
    return


if __name__ == "__main__":
    main()
