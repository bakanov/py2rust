"""Validate every declared field, retain rejected inputs and project accepted rows."""

from dataclasses import dataclass

from csvcodec import parse, render
from schema import decode, encode, typed

from py2rust.stdlib import (
    Json,
    json_array,
    json_canonical,
    json_int,
    json_keys,
    json_kind,
    json_loads,
    json_string,
    pretty,
)


@dataclass
class Converted:
    data: str
    report: Json


def convert(source: bytes, config: Json, columns: Json, selected: list[str]) -> Converted:
    direction: str = json_string(config["direction"])
    maximum: int = json_int(config["max_rows"])
    field_limit: int = json_int(config["max_field_bytes"])
    delimiter: str = json_string(config["delimiter"])
    header: list[str] = []
    records: list[Json] = []
    if direction == "csv-to-json":
        table: list[list[str]] = parse(source, delimiter, maximum + 1, 64, field_limit)
        assert len(table) > 0, "CSV header is missing"
        header = table[0]
        assert len(header) == len(set(header)) and sorted(header) == json_keys(
            columns
        ), "CSV header differs from schema"
        for index in range(1, len(table)):
            records.append(table[index])
    else:
        records = json_array(json_loads(source.decode()))
        assert len(records) <= maximum, "JSON row limit exceeded"
    accepted_rows: list[int] = []
    rejected: list[Json] = []
    encoded_rows: list[str] = []
    csv_header: str = "" if direction == "csv-to-json" else render([selected], delimiter, field_limit)
    output_bytes: int = 3 if direction == "csv-to-json" else len(csv_header.encode())
    rejection_bytes: int = 0
    for index in range(len(records)):
        raw: Json = records[index]
        candidate: Json = {}
        errors: list[Json] = []
        if direction == "csv-to-json":
            cells: list[Json] = json_array(raw)
            if len(cells) != len(header):
                errors.append({"column": "", "reason": "row width differs from header"})
            else:
                for cell_index in range(len(header)):
                    candidate[header[cell_index]] = cells[cell_index]
        elif json_kind(raw) != "object" or json_keys(raw) != json_keys(columns):
            errors.append({"column": "", "reason": "record fields differ from schema"})
        else:
            candidate = raw
        normalized: Json = {}
        if len(errors) == 0:
            for name in json_keys(columns):
                try:
                    value: Json = (
                        decode(json_string(candidate[name]), columns[name])
                        if direction == "csv-to-json"
                        else typed(candidate[name], columns[name])
                    )
                    cell: str = encode(value, columns[name])
                    assert len(cell.encode()) <= field_limit, "formatted field exceeds byte limit"
                    normalized[name] = value
                except Exception:  # noqa: BLE001 - stable field diagnostics across engines
                    errors.append(
                        {"column": name, "reason": "invalid " + json_string(columns[name]["type"]) + " value"}
                    )
        if len(errors) > 0:
            rejection: Json = {"row": index + 1, "input": raw, "errors": errors}
            rendered: str = pretty(rejection)
            rejection_bytes = rejection_bytes + len(rendered.encode()) + 4 * len(rendered.split("\n")) + 2
            assert rejection_bytes <= 15728640, "rejection report exceeds 15 MiB budget"
            rejected.append(rejection)
        else:
            projected: Json = {}
            csv_row: list[str] = []
            for name in selected:
                projected[name] = normalized[name]
                csv_row.append(encode(normalized[name], columns[name]))
            encoded: str = (
                json_canonical(projected) if direction == "csv-to-json" else render([csv_row], delimiter, field_limit)
            )
            output_bytes = output_bytes + len(encoded.encode())
            if direction == "csv-to-json" and len(accepted_rows) > 0:
                output_bytes = output_bytes + 1
            assert output_bytes <= 8388608, "converted data exceeds 8 MiB"
            accepted_rows.append(index + 1)
            encoded_rows.append(encoded)
    data: str = (
        "[" + ",".join(encoded_rows) + "]\n" if direction == "csv-to-json" else csv_header + "".join(encoded_rows)
    )
    assert len(data.encode()) <= 8388608, "converted data exceeds 8 MiB"
    report: Json = {
        "direction": direction,
        "columns": selected,
        "rows": len(records),
        "accepted": len(accepted_rows),
        "rejected": len(rejected),
        "accepted_rows": accepted_rows,
        "errors": rejected,
    }
    return Converted(data, report)
