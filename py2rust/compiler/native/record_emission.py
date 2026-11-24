"""Native record declarations using the shared owned type representations."""

from py2rust.stdlib import Json, json_array, json_int, json_string

from ..rules.literals import quote_scalar_text
from .names import symbol
from .types import rust_type


def render_record(nodes: list[Json], index: int, definitions: dict[str, int]) -> str:
    record: Json = nodes[index]
    fields: list[str] = []
    for reference in json_array(record["fields"]):
        field: Json = nodes[json_int(reference)]
        fields.append(
            "#[serde(rename = "
            + quote_scalar_text(json_string(field["name"]))
            + ")] "
            + symbol(json_string(field["name"]))
            + ": "
            + rust_type(nodes, json_int(field["type"]), definitions)
        )
    return (
        "#[derive(Clone, PartialEq, serde::Serialize)]\nstruct "
        + symbol(json_string(record["name"]))
        + " {\n"
        + ",\n".join(fields)
        + "\n}\n"
    )
