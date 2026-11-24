"""Process a bounded JSONL snapshot atomically, never retaining raw rejected records in output."""

# ruff: noqa: I001 - compact grouped runtime imports
from fields import replace, select
from redaction import apply
from py2rust.stdlib import Json, json_array, json_canonical, json_int, json_kind, json_loads_unique, json_string


def process(config: Json, data: bytes) -> tuple[bytes, Json]:
    paths: list[Json] = json_array(config["targets"])
    rules: list[Json] = json_array(config["rules"])
    rule_counts: list[Json] = []
    target_counts: list[Json] = []
    for index in range(len(rules)):
        rule_counts.append({"index": index, "matches": 0, "matched_fields": 0, "changed_fields": 0})
    for index in range(len(paths)):
        target_counts.append({"index": index, "present": 0, "missing": 0, "changed": 0})
    audit: Json = {
        "version": 1,
        "records": 0,
        "changed_records": 0,
        "selected_fields": 0,
        "missing_fields": 0,
        "changed_fields": 0,
        "matches": 0,
        "input_bytes": len(data),
        "output_bytes": 0,
    }
    offset: int = 0
    output: bytes = b""
    while offset < len(data):
        assert json_int(audit["records"]) < 1024, "record count limit"
        window: bytes = data[offset : offset + 65537]
        newline: int = window.find(b"\n")
        size: int = newline + 1 if newline >= 0 else len(window)
        assert size <= 65536, "record byte limit"
        record: Json = json_loads_unique(window[:size].decode())
        assert json_kind(record) == "object", "expected object record"
        offset = offset + size
        changed: bool = False
        for index in range(len(paths)):
            path: list[Json] = json_array(paths[index])
            selected: tuple[bool, str] = select(record, path, 0)
            target: Json = target_counts[index]
            if not selected[0]:
                assert json_string(config["missing"]) == "skip", "missing required field"
                target["missing"] = json_int(target["missing"]) + 1
                audit["missing_fields"] = json_int(audit["missing_fields"]) + 1
            else:
                masked: tuple[str, list[Json], int] = apply(selected[1], rules, rule_counts)
                rule_counts = masked[1]
                matches: int = json_int(audit["matches"]) + masked[2]
                assert matches <= 1000000, "match count limit"
                audit["matches"] = matches
                target["present"] = json_int(target["present"]) + 1
                audit["selected_fields"] = json_int(audit["selected_fields"]) + 1
                if masked[0] != selected[1]:
                    record = replace(record, path, 0, masked[0])
                    changed = True
                    target["changed"] = json_int(target["changed"]) + 1
                    audit["changed_fields"] = json_int(audit["changed_fields"]) + 1
            target_counts[index] = target
        encoded: bytes = (json_canonical(record) + "\n").encode()
        assert len(encoded) <= 262144 and len(output) + len(encoded) <= 4194304, "output expansion limit"
        output = output + encoded
        audit["records"] = json_int(audit["records"]) + 1
        audit["changed_records"] = json_int(audit["changed_records"]) + (1 if changed else 0)
    audit["output_bytes"] = len(output)
    audit["rules"] = rule_counts
    audit["targets"] = target_counts
    return (output, audit)
