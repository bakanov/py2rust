"""Convert CSV and JSON using declared types and publish a complete result bundle."""

from conversion import Converted, convert
from documents import Document, absolute, checkpoint, present, publish, read, stamp
from schema import fields, rules, selection

from py2rust.stdlib import (
    Json,
    env_get,
    json_equal,
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


def main() -> None:
    mode: str = env_get("CONVERT_MODE", "preview")
    assert mode in ["preview", "convert"], "invalid conversion mode"
    config_path: str = absolute(env_get("CONVERT_CONFIG", "convert.json"), path_resolve("."))
    config_document: Document = read(config_path, 65536)
    config: Json = json_loads(config_document.data.decode())
    fields(
        config,
        [
            "input",
            "output",
            "direction",
            "delimiter",
            "columns",
            "select",
            "max_rows",
            "max_field_bytes",
            "max_input_bytes",
        ],
    )
    direction: str = json_string(config["direction"])
    assert direction in ["csv-to-json", "json-to-csv"], "invalid conversion direction"
    assert json_string(config["delimiter"]) in [",", ";", "\t", "|"], "unsupported delimiter"
    assert 1 <= json_int(config["max_rows"]) <= 10000, "row limit must be 1..10000"
    assert 1 <= json_int(config["max_field_bytes"]) <= 65536, "field limit must be 1..65536"
    limit: int = json_int(config["max_input_bytes"])
    assert 1 <= limit <= 4194304, "input limit must be 1..4 MiB"
    columns: Json = rules(config)
    selected: list[str] = selection(config, columns)
    base: str = path_parent(config_path)
    input_path: str = absolute(json_string(config["input"]), base)
    output: str = absolute(json_string(config["output"]), base)
    assert not present(output), "output directory already exists"
    document: Document = read(input_path, limit)
    converted: Converted = convert(document.data, config, columns, selected)
    filename: str = "data.json" if direction == "csv-to-json" else "data.csv"
    report: Json = converted.report
    report["input_sha256"] = sha256_digest(sha256_update(sha256_new(), document.data))
    report["data_sha256"] = sha256_digest(sha256_update(sha256_new(), converted.data.encode()))
    report["data_file"] = filename
    text: str = pretty(report)
    assert len(text.encode()) <= 16777216, "report exceeds 16 MiB"
    checkpoint("validated")
    assert json_equal(config_document.stamp, stamp(config_path)) and json_equal(
        document.stamp, stamp(input_path)
    ), "input changed before publication"
    if mode == "convert":
        publish(output, filename, converted.data, text)
    print(text)
    if json_int(report["rejected"]) > 0:
        process_exit(1)


if __name__ == "__main__":
    main()
