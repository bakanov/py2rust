"""An INI subset with JSON-quoted strings, ordered sections and retained comment lines."""

# ruff: noqa: BLE001, PIE810 - report backend-independent source locations
from dataclasses import dataclass

from py2rust.stdlib import json_canonical, json_loads, json_string


@dataclass
class Line:
    kind: str
    section: str
    key: str
    value: str
    comment: str


def identifier(value: str) -> bool:
    letters: str = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ_"
    if value == "" or len(value) > 64 or value[0] not in letters:
        return False
    for character in value:
        if character not in letters + "0123456789-":
            return False
    return True


def trim(value: str) -> str:
    first: int = len(value)
    last: int = 0
    position: int = 0
    for character in value:
        if character not in " \t":
            first = min(first, position)
            last = position + 1
        position = position + 1
    return value[first:last]


def comment(value: str, location: str) -> str:
    value = trim(value)
    assert value == "" or value.startswith("#") or value.startswith(";"), location + "expected comment or end of line"
    return value


def quoted(text: str, location: str) -> tuple[str, str]:
    assert text.startswith('"'), location + "value must be a quoted string"
    escaped: bool = False
    position: int = 0
    for character in text:
        if position == 0:
            position = position + 1
            continue
        if character == '"' and not escaped:
            value: str = ""
            try:
                value = json_string(json_loads(text[: position + 1]))
            except Exception:
                assert False, location + "invalid quoted string"
            assert len(value.encode()) <= 8192, location + "value exceeds 8192 bytes"
            return (value, comment(text[position + 1 :], location))
        escaped = character == "\\" and not escaped
        position = position + 1
    assert False, location + "unclosed quoted string"
    return ("", "")


def parse(text: str) -> list[Line]:
    assert len(text.encode()) <= 1048576, "INI exceeds 1 MiB"
    text = text.replace("\r\n", "\n")
    for (
        control
    ) in "\x00\x01\x02\x03\x04\x05\x06\x07\x08\x0b\x0c\x0d\x0e\x0f\x10\x11\x12\x13\x14\x15\x16\x17\x18\x19\x1a\x1b\x1c\x1d\x1e\x1f\x7f":
        assert control not in text, "invalid raw control in INI"
    rows: list[str] = [] if text == "" else text.split("\n")
    if text.endswith("\n"):
        rows = rows[:-1]
    assert len(rows) <= 2048, "INI exceeds 2048 lines"
    lines: list[Line] = []
    section: str = ""
    sections: set[str] = set()
    keys: set[str] = set()
    for index in range(len(rows)):
        raw: str = rows[index]
        location: str = "line " + str(index + 1) + ": "
        assert len(raw.encode()) <= 65536, location + "line exceeds 65536 bytes"
        value: str = trim(raw)
        if value == "" or value.startswith("#") or value.startswith(";"):
            lines.append(Line("comment", section, "", "", raw))
        elif value.startswith("["):
            end: int = value.find("]")
            assert end > 1, location + "invalid section header"
            section = trim(value[1:end])
            assert identifier(section), location + "invalid section name"
            assert section not in sections, location + "duplicate section: " + section
            sections.add(section)
            assert len(sections) <= 64, location + "more than 64 sections"
            lines.append(Line("section", section, "", "", comment(value[end + 1 :], location)))
        else:
            equal: int = value.find("=")
            assert equal > 0, location + "expected key = quoted string"
            key: str = trim(value[:equal])
            assert identifier(key), location + "invalid key name"
            name: str = section + "." + key
            assert name not in keys, location + "duplicate key: " + name
            keys.add(name)
            assert len(keys) <= 256, location + "more than 256 keys"
            parsed: tuple[str, str] = quoted(trim(value[equal + 1 :]), location)
            lines.append(Line("value", section, key, parsed[0], parsed[1]))
    return lines


def write(lines: list[Line]) -> str:
    output: list[str] = []
    for line in lines:
        if line.kind == "comment":
            output.append(line.comment)
        else:
            text: str = (
                "[" + line.section + "]" if line.kind == "section" else line.key + " = " + json_canonical(line.value)
            )
            output.append(text + (" " + line.comment if line.comment != "" else ""))
    return "\n".join(output) + ("\n" if len(output) > 0 else "")


def values(lines: list[Line]) -> dict[str, str]:
    result: dict[str, str] = {}
    for line in lines:
        if line.kind == "value":
            result[line.section + "." + line.key] = line.value
    return result
