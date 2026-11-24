"""Strict job configuration and table schemas; CSV cells remain literal strings."""

from dataclasses import dataclass

from csvcodec import parse
from documents import Document

from py2rust.stdlib import Json, json_array, json_int, json_keys, json_kind, json_string


@dataclass
class Table:
    header: list[str]
    rows: list[list[str]]
    keys: list[int]


def fields(value: Json, names: list[str]) -> None:
    assert json_kind(value) == "object" and json_keys(value) == sorted(names), "unexpected configuration fields"
    return  # noqa: PLR1711 - explicit returns follow repository guidelines


def names(value: Json) -> list[str]:
    result: list[str] = []
    for item in json_array(value):
        name: str = json_string(item)
        assert name != "" and len(name.encode()) <= 256 and "\0" not in name, "invalid column name"
        assert name not in result, "duplicate column name"
        result.append(name)
    assert 1 <= len(result) <= 64, "require 1..64 columns"
    return result


def validate(config: Json) -> None:
    fields(
        config,
        [
            "left",
            "right",
            "output",
            "kind",
            "select",
            "delimiter",
            "duplicates",
            "order",
            "max_rows",
            "max_field_bytes",
            "max_input_bytes",
            "max_output_rows",
        ],
    )
    assert json_string(config["kind"]) in ["inner", "left"], "invalid join kind"
    assert json_string(config["duplicates"]) in ["all", "error"], "invalid duplicate policy"
    assert json_string(config["order"]) in ["left", "key"], "invalid output order"
    for side in ["left", "right"]:
        specification: Json = config[side]
        fields(specification, ["path", "keys", "delimiter"])
        names(specification["keys"])
        assert json_string(specification["delimiter"]) in [",", ";", "\t", "|"], "invalid input delimiter"
    assert len(json_array(config["left"]["keys"])) == len(json_array(config["right"]["keys"])), "key arity differs"
    assert json_string(config["delimiter"]) in [",", ";", "\t", "|"], "invalid output delimiter"
    assert 1 <= json_int(config["max_rows"]) <= 10000, "row limit must be 1..10000"
    assert 1 <= json_int(config["max_field_bytes"]) <= 65536, "field limit must be 1..65536"
    assert 1 <= json_int(config["max_input_bytes"]) <= 4194304, "input limit must be 1..4 MiB"
    assert 1 <= json_int(config["max_output_rows"]) <= 100000, "output row limit must be 1..100000"
    return  # noqa: PLR1711 - explicit returns follow repository guidelines


def table(document: Document, specification: Json, config: Json) -> Table:
    rows: list[list[str]] = parse(
        document.data,
        json_string(specification["delimiter"]),
        json_int(config["max_rows"]) + 1,
        64,
        json_int(config["max_field_bytes"]),
    )
    assert len(rows) > 0, "CSV header is required"
    header: list[str] = names(rows[0])
    indices: dict[str, int] = {}
    for index in range(len(header)):
        indices[header[index]] = index
    keys: list[int] = []
    for name in names(specification["keys"]):
        assert name in indices, "join key is missing from header"
        keys.append(indices[name])
    for number in range(1, len(rows)):
        assert len(rows[number]) == len(header), "CSV row width differs from header at record " + str(number)
    return Table(header, rows[1:], keys)


def selection(config: Json, left: Table, right: Table) -> list[tuple[str, int, str]]:
    result: list[tuple[str, int, str]] = []
    aliases: list[str] = []
    for item in json_array(config["select"]):
        fields(item, ["side", "column", "as"])
        side: str = json_string(item["side"])
        assert side in ["left", "right"], "invalid projection side"
        header: list[str] = left.header if side == "left" else right.header
        column: str = json_string(item["column"])
        assert column in header, "selected column is missing"
        position: int = 0
        for index in range(len(header)):
            if header[index] == column:
                position = index
        alias: str = json_string(item["as"])
        aliases.append(alias)
        result.append((side, position, alias))
    names(aliases)
    return result
