"""DNS headers, questions, all three record sections and in-packet CNAME chains."""

from names import encode_name, read_name

from py2rust.stdlib import (
    Json,
    int_from_bytes,
    int_to_bytes,
    json_int,
    json_string,
)


def number(data: bytes, offset: int, width: int) -> int:
    assert offset >= 0 and offset + width <= len(data), "integer field outside packet"
    return int_from_bytes(data[offset : offset + width], "big")


def query(identifier: int, name: str, kind: int) -> bytes:
    return (
        int_to_bytes(identifier, 2, "big")
        + b"\x01\x00\x00\x01\x00\x00\x00\x00\x00\x00"
        + encode_name(name)
        + int_to_bytes(kind, 2, "big")
        + b"\x00\x01"
    )


def record(data: bytes, start: int, section: str) -> tuple[Json, int]:
    owner: tuple[str, int] = read_name(data, start)
    cursor: int = owner[1]
    kind: int = number(data, cursor, 2)
    category: int = number(data, cursor + 2, 2)
    ttl: int = number(data, cursor + 4, 4)
    size: int = number(data, cursor + 8, 2)
    cursor = cursor + 10
    end: int = cursor + size
    assert end <= len(data), "RDATA outside packet"
    value: str = data[cursor:end].hex()
    if category == 1 and kind == 1:
        assert size == 4, "A record needs four bytes"
        parts: list[str] = []
        for index in range(cursor, end):
            parts.append(str(data[index]))
        value = ".".join(parts)
    elif category == 1 and kind == 28:
        assert size == 16, "AAAA record needs sixteen bytes"
        groups: list[str] = []
        for index in range(8):
            group: str = data[cursor + index * 2 : cursor + index * 2 + 2].hex()
            while len(group) > 1 and group.startswith("0"):
                group = group[1:]
            groups.append(group)
        value = ":".join(groups)
    elif category == 1 and kind in [2, 5, 12]:
        target: tuple[str, int] = read_name(data, cursor)
        assert target[1] == end, "name RDATA length mismatch"
        value = target[0]
    return ({"name": owner[0], "type": kind, "class": category, "ttl": ttl, "value": value, "section": section}, end)


def addresses(records: list[Json], name: str, kind: int) -> tuple[str, list[str], list[Json]]:
    current: str = name
    aliases: list[str] = []
    visited: set[str] = set()
    for hop in range(17):
        assert current not in visited, "CNAME cycle"
        visited.add(current)
        targets: set[str] = set()
        found: list[Json] = []
        for item in records:
            if (
                json_string(item["section"]) == "answer"
                and json_int(item["class"]) == 1
                and json_string(item["name"]) == current
            ):
                if json_int(item["type"]) == 5:
                    targets.add(json_string(item["value"]))
                elif json_int(item["type"]) == kind:
                    found.append({"name": current, "address": item["value"], "ttl": item["ttl"]})
        assert len(targets) <= 1, "conflicting CNAME targets"
        if len(targets) == 0:
            return (current, aliases, found)
        assert len(found) == 0 and hop < 16, "invalid or excessive CNAME chain"
        for target in targets:
            current = target
            aliases.append(target)
    assert False, "CNAME traversal exhausted"
    return (current, aliases, [])


def response(data: bytes, identifier: int, name: str, kind: int) -> Json:
    assert len(data) >= 12 and len(data) <= 512, "invalid DNS packet size"
    assert number(data, 0, 2) == identifier, "response ID mismatch"
    flags: int = number(data, 2, 2)
    assert flags & 0x8000 != 0 and (flags >> 11) & 15 == 0 and flags & 0x0040 == 0, "invalid response flags"
    assert number(data, 4, 2) == 1, "response needs one question"
    question: tuple[str, int] = read_name(data, 12)
    assert (
        question[0] == name and number(data, question[1], 2) == kind and number(data, question[1] + 2, 2) == 1
    ), "response question mismatch"
    code: int = flags & 15
    result: Json = {
        "status": "truncated",
        "rcode": code,
        "authoritative": flags & 0x0400 != 0,
        "recursion_available": flags & 0x0080 != 0,
        "truncated": flags & 0x0200 != 0,
        "canonical": name,
        "aliases": [],
        "answers": [],
        "records": [],
    }
    if flags & 0x0200 != 0:
        return result
    counts: list[int] = [number(data, 6, 2), number(data, 8, 2), number(data, 10, 2)]
    assert counts[0] + counts[1] + counts[2] <= 64, "record count exceeds 64"
    sections: list[str] = ["answer", "authority", "additional"]
    cursor: int = question[1] + 4
    records: list[Json] = []
    for section in range(3):
        for index in range(counts[section]):
            parsed: tuple[Json, int] = record(data, cursor, sections[section])
            records.append(parsed[0])
            cursor = parsed[1]
    assert cursor == len(data), "trailing bytes after DNS records"
    result["records"] = records
    result["status"] = "dns_error"
    if code == 3:
        result["status"] = "nxdomain"
    elif code == 0:
        selected: tuple[str, list[str], list[Json]] = addresses(records, name, kind)
        result["canonical"] = selected[0]
        result["aliases"] = selected[1]
        result["answers"] = selected[2]
        result["status"] = "nodata"
        if len(selected[2]) > 0:
            result["status"] = "ok"
    return result
