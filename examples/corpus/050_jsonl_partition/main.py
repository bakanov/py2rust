"""Preview or atomically publish one bounded JSONL input as date/topic shards and a manifest."""

import logging

from documents import Document, absolute, checkpoint, present, publish, read, unchanged
from partitioning import Partition, partition

from py2rust.stdlib import (
    Json,
    env_get,
    json_int,
    json_keys,
    json_loads,
    json_string,
    path_parent,
    path_resolve,
    pretty,
    process_exit,
)


def validate(config: Json) -> None:
    names: list[str] = [
        "input",
        "output",
        "timestamp_field",
        "topic_field",
        "max_rows",
        "max_line_bytes",
        "max_input_bytes",
        "max_shards",
    ]
    assert json_keys(config) == sorted(names), "unexpected partition configuration fields"
    for name in ["timestamp_field", "topic_field"]:
        field: str = json_string(config[name])
        assert 1 <= len(field.encode()) <= 128, "field name must contain 1..128 UTF-8 bytes"
    assert json_string(config["timestamp_field"]) != json_string(config["topic_field"]), "field names must differ"
    assert 1 <= json_int(config["max_rows"]) <= 10000, "max_rows must be 1..10000"
    assert 1 <= json_int(config["max_line_bytes"]) <= 65536, "max_line_bytes must be 1..65536"
    assert 1 <= json_int(config["max_input_bytes"]) <= 4194304, "max_input_bytes must be 1..4194304"
    assert 1 <= json_int(config["max_shards"]) <= 256, "max_shards must be 1..256"
    return  # noqa: PLR1711 - explicit returns follow repository guidelines


def run() -> None:
    mode: str = env_get("PARTITION_MODE", "preview")
    assert mode in ["preview", "write"], "invalid partition mode"
    path: str = absolute(env_get("PARTITION_CONFIG", "partition-job.json"), path_resolve("."))
    configuration: Document = read(path, 65536)
    config: Json = json_loads(configuration.data.decode())
    validate(config)
    source: str = absolute(json_string(config["input"]), path_parent(path))
    output: str = absolute(json_string(config["output"]), path_parent(path))
    assert not present(output), "output directory already exists"
    document: Document = read(source, json_int(config["max_input_bytes"]))
    result: Partition = partition(document.data, config)
    manifest: str = pretty(result.manifest) + "\n"
    assert len(manifest.encode()) <= 1048576, "manifest exceeds 1 MiB"
    files: dict[str, str] = result.files
    files["manifest.json"] = manifest
    documents: list[Document] = [configuration, document]
    checkpoint("validated")
    unchanged(documents)
    if mode == "write":
        publish(output, files, documents)
    print(manifest[:-1])
    return  # noqa: PLR1711 - explicit returns follow repository guidelines


def main() -> None:
    try:
        run()
    except Exception as error:  # noqa: BLE001 - CLI errors have exit status 2
        logging.error(str(error))  # noqa: LOG015 - supported logging facade
        process_exit(2)
    return  # noqa: PLR1711 - explicit returns follow repository guidelines


if __name__ == "__main__":
    main()
