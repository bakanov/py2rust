"""Partition input records without losing their original positions or values."""

from fields import clean_field, text

from py2rust.stdlib import (
    Json,
    json_array,
    json_bool,
    json_get,
    json_keys,
    json_kind,
    json_string,
)


def clean_record(record: Json, schema: Json) -> Json:
    errors: list[Json] = []
    output: Json = {}
    if json_kind(record) != "object":
        return {"ok": False, "errors": [{"field": "$", "reason": "record must be an object"}]}
    names: set[str] = set()
    for rule in json_array(schema["fields"]):
        name: str = text(rule, "name", "")
        names.add(name)
        value: Json = None
        available: bool = True
        if name in record:
            value = record[name]
        elif "default" in rule:
            value = rule["default"]
        elif json_bool(json_get(rule, "required", True)):
            errors.append({"field": name, "reason": "required field is missing"})
            available = False
        else:
            available = False
        if available:
            result: Json = clean_field(value, rule)
            if json_bool(result["ok"]):
                output[name] = result["value"]
            else:
                errors.append({"field": name, "reason": json_string(result["reason"])})
    unknown: str = text(schema, "unknown", "reject")
    for name in json_keys(record):
        if name not in names:
            if unknown == "reject":
                errors.append({"field": name, "reason": "unknown field"})
            if unknown == "preserve":
                output[name] = record[name]
    return {"ok": len(errors) == 0, "record": output, "errors": errors}


def process(records: list[Json], schema: Json) -> Json:
    accepted: list[Json] = []
    rejected: list[Json] = []
    index: int = 0
    field_errors: int = 0
    for record in records:
        result: Json = clean_record(record, schema)
        if json_bool(result["ok"]):
            accepted.append({"index": index, "record": result["record"]})
        else:
            errors: list[Json] = json_array(result["errors"])
            field_errors = field_errors + len(errors)
            rejected.append({"index": index, "record": record, "errors": errors})
        index = index + 1
    summary: Json = {"input": index, "accepted": len(accepted), "rejected": len(rejected), "field_errors": field_errors}
    assert len(accepted) + len(rejected) == index, "record partition lost data"
    return {"summary": summary, "accepted": accepted, "rejected": rejected}
