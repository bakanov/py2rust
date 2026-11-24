"""Normalize schema-listed fields and save accepted/rejected records atomically."""

import sys

from records import process
from schema import load_schema, validate_schema

from py2rust.stdlib import (
    Json,
    env_get,
    json_array,
    json_int,
    json_loads,
    path_exists,
    path_resolve,
    pretty,
    read_bytes,
    write_text_atomic,
)


def main() -> None:
    schema: Json = load_schema()
    validate_schema(schema)
    input_path: str = env_get("CLEAN_INPUT", "records.json")
    output_path: str = env_get("CLEAN_OUTPUT", "cleaned.json")
    if path_exists(output_path):
        assert path_resolve(input_path) != path_resolve(output_path), "output must not replace input"
    content: bytes = read_bytes(input_path)
    assert len(content) <= 16777216, "input exceeds 16 MiB"
    source: list[Json] = json_array(json_loads(content.decode()))
    assert len(source) <= 10000, "input exceeds 10000 records"
    report: Json = process(source, schema)
    write_text_atomic(output_path, pretty(report))
    print(pretty(report["summary"]))
    if json_int(report["summary"]["rejected"]) > 0:
        sys.exit(1)
    return  # noqa: PLR1711 - explicit return required by repository guidelines


if __name__ == "__main__":
    main()
