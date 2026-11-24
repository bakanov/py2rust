"""Apply validated set/delete operations while retaining unrelated comments and section order."""

from syntax import Line, identifier

from py2rust.stdlib import Json, json_array, json_keys, json_string


def apply(lines: list[Line], edits: Json) -> list[Line]:
    operations: list[Json] = json_array(edits)
    assert len(operations) <= 256, "more than 256 edits"
    result: list[Line] = lines.copy()
    for operation in operations:
        kind: str = json_string(operation["op"])
        fields: list[str] = ["key", "op", "section", "value"] if kind == "set" else ["key", "op", "section"]
        assert kind in ["set", "delete"] and json_keys(operation) == fields, "invalid edit fields or operation"
        section: str = json_string(operation["section"])
        key: str = json_string(operation["key"])
        assert (section == "" or identifier(section)) and identifier(key), "invalid edit section/key"
        position: int = -1
        insertion: int = 0
        found: bool = section == ""
        for index in range(len(result)):
            line: Line = result[index]
            if line.section == section:
                found = True
                insertion = index + 1
                if line.kind == "value" and line.key == key:
                    position = index
        if kind == "delete":
            assert position >= 0, "cannot delete missing key: " + section + "." + key
            result.pop(position)
        else:
            value: str = json_string(operation["value"])
            assert len(value.encode()) <= 8192, "edit value exceeds 8192 bytes"
            if position >= 0:
                result[position] = Line("value", section, key, value, result[position].comment)
            else:
                if not found:
                    if len(result) > 0:
                        result.append(Line("comment", result[-1].section, "", "", ""))
                    result.append(Line("section", section, "", "", ""))
                    insertion = len(result)
                result.insert(insertion, Line("value", section, key, value, ""))
    return result
