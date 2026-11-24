"""Keep diagnostics independent of sensitive data, patterns, replacements and file paths."""

# ruff: noqa: I001, BLE001, LOG015 - explicit process boundaries and compact runtime imports
import logging
from configuration import load
from documents import Document, absolute, publish, read
from processing import process
from reports import render
from py2rust.stdlib import Json, env_get, json_canonical, json_string, path_resolve, process_exit


def run() -> int:
    # Every exception may contain sensitive source text. Only fixed phase names reach diagnostics.
    document: Document = Document("", {}, b"")
    config: Json = {}
    try:
        path: str = absolute(env_get("REDACTOR_CONFIG", "redactor-job.json"), path_resolve("."))
        document = read(path, 65536)
        config = load(document)
    except Exception:
        logging.error("Redactor configuration failed")
        return 2
    source: Document = Document("", {}, b"")
    result: tuple[bytes, Json] = (b"", {})
    try:
        source = read(json_string(config["input"]), 4194304)
        result = process(config, source.data)
    except Exception:
        logging.error("Redactor input processing failed")
        return 2
    try:
        files: dict[str, bytes] = render(result[0], result[1])
        publish(json_string(config["output"]), files, [document, source])
    except Exception:
        logging.error("Redactor publication failed")
        return 2
    print(json_canonical(result[1]))
    return 0


if __name__ == "__main__":
    process_exit(run())
