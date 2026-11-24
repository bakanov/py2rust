"""Find cross-document repeated phrases and atomically publish reproducible audit bundles."""

# ruff: noqa: PLR1711, BLE001, LOG015, PLC0206 - explicit returns and subset operations

import logging

from documents import Document, absolute, checkpoint, present, publish, read, unchanged
from matching import audit
from model import Source, document, exact, load

from py2rust.stdlib import (
    Json,
    env_get,
    json_array,
    json_canonical,
    json_int,
    json_loads,
    json_string,
    path_parent,
    path_resolve,
    pretty,
    process_exit,
    sha256_digest,
    sha256_new,
    sha256_update,
)


def digest(text: str) -> str:
    return sha256_digest(sha256_update(sha256_new(), text.encode()))


def run() -> int:
    mode: str = env_get("PHRASE_MODE", "preview")
    assert mode in ["preview", "write"], "invalid phrase mode"
    path: str = absolute(env_get("PHRASE_CONFIG", "phrase-job.json"), path_resolve("."))
    configuration: Document = read(path, 65536)
    config: Json = json_loads(configuration.data.decode())
    exact(config, ["documents", "ngram", "output"])
    size: int = json_int(config["ngram"])
    assert 1 <= size <= 16, "ngram size must be 1..16"
    base: str = path_parent(path)
    output: str = absolute(json_string(config["output"]), base)
    assert not present(output), "output directory already exists"
    source: Document = read(absolute(json_string(config["documents"]), base), 2097152)
    sources: list[Source] = load(json_loads(source.data.decode()))
    analysis: Json = audit(sources, size)
    exported: str = json_canonical(document(sources)) + "\n"
    report: Json = {
        "version": 1,
        "ngram": size,
        "tokenizer": "nfc-casefold-ranges-v1",
        "documents_sha256": digest(exported),
        "analysis": analysis,
    }
    rows: list[str] = []
    text: list[str] = ["Repeated phrases: " + json_canonical(analysis["counts"])]
    for phrase in json_array(analysis["matches"]):
        rows.append(json_canonical(phrase) + "\n")
        text.append(
            json_canonical(phrase["left"]["document"])
            + " ["
            + json_canonical(phrase["left"]["start_char"])
            + ","
            + json_canonical(phrase["left"]["end_char"])
            + ") and "
            + json_canonical(phrase["right"]["document"])
            + " ["
            + json_canonical(phrase["right"]["start_char"])
            + ","
            + json_canonical(phrase["right"]["end_char"])
            + "): "
            + json_canonical(phrase["tokens"])
        )
    files: dict[str, str] = {
        "documents.json": exported,
        "audit.json": json_canonical(report) + "\n",
        "matches.jsonl": "".join(rows),
        "audit.txt": "\n".join(text) + "\n",
    }
    checksums: Json = {}
    for name in files:
        assert len(files[name].encode()) <= 16777216, "output file exceeds 16 MiB"
        checksums[name] = {"bytes": len(files[name].encode()), "sha256": digest(files[name])}
    files["manifest.json"] = pretty({"version": 1, "files": checksums}) + "\n"
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
