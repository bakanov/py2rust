"""A strict common-log profile: numbered fields, UTC timestamps and lossless line framing."""

# ruff: noqa: BLE001 - explicit returns and per-line rejection boundaries

from py2rust.stdlib import (
    Json,
    datetime_iso,
    datetime_parse,
    int_from_decimal,
    json_string,
    regex_capture,
)


def lines(data: bytes) -> list[bytes]:
    result: list[bytes] = []
    start: int = 0
    for end in range(len(data)):
        if data[end] == 10:
            row: bytes = data[start:end]
            if row.endswith(b"\r"):
                row = row[:-1]
            assert len(row) <= 8192, "log line exceeds 8192 bytes"
            result.append(row)
            assert len(result) <= 10000, "log line count exceeds 10000"
            start = end + 1
    if start < len(data):
        row: bytes = data[start:]
        assert len(row) <= 8192, "log line exceeds 8192 bytes"
        result.append(row)
    assert len(result) <= 10000, "log line count exceeds 10000"
    return result


def group(captured: Json, index: int) -> str:
    return json_string(captured["groups"][index])


def parse(raw: bytes) -> Json:
    text: str = ""
    try:
        text = raw.decode()
    except Exception:
        return {"ok": False, "reason": "utf8"}
    for value in raw:
        if value < 32 or value == 127:
            return {"ok": False, "reason": "control"}
    pattern: str = (
        r"""([^ "]+) ([^ "]+) ([^ "]+) \[([0-9]{2})/([A-Za-z]{3})/([0-9]{4}):"""
        r"""([0-9]{2}):([0-9]{2}):([0-9]{2}) ([+-][0-9]{4})\] """
        r""""([-!#$%&'*+.^_`|~0-9A-Za-z]+) ([^ "]+) (HTTP/[0-9]\.[0-9])" ([0-9]{3}) (-|[0-9]+)"""
    )
    captured: Json = regex_capture(pattern, text, True)
    if captured is None:
        return {"ok": False, "reason": "format"}
    months: dict[str, str] = {
        "Jan": "01",
        "Feb": "02",
        "Mar": "03",
        "Apr": "04",
        "May": "05",
        "Jun": "06",
        "Jul": "07",
        "Aug": "08",
        "Sep": "09",
        "Oct": "10",
        "Nov": "11",
        "Dec": "12",
    }
    month: str = group(captured, 5)
    if month not in months:
        return {"ok": False, "reason": "timestamp"}
    offset: str = group(captured, 10)
    timestamp: str = (
        group(captured, 6)
        + "-"
        + months[month]
        + "-"
        + group(captured, 4)
        + "T"
        + group(captured, 7)
        + ":"
        + group(captured, 8)
        + ":"
        + group(captured, 9)
        + offset[:3]
        + ":"
        + offset[3:]
    )
    try:
        timestamp = datetime_iso(datetime_parse(timestamp))
    except Exception:
        return {"ok": False, "reason": "timestamp"}
    status: int = int_from_decimal(group(captured, 14))
    if status < 100 or status > 599:
        return {"ok": False, "reason": "status"}
    size: int = 0
    if group(captured, 15) != "-":
        try:
            size = int_from_decimal(group(captured, 15))
        except Exception:
            return {"ok": False, "reason": "bytes"}
    target: str = group(captured, 12)
    return {
        "ok": True,
        "record": {
            "host": group(captured, 1),
            "ident": group(captured, 2),
            "user": group(captured, 3),
            "timestamp": timestamp,
            "method": group(captured, 11),
            "target": target,
            "path": target.split("?")[0],
            "protocol": group(captured, 13),
            "status": status,
            "bytes": size,
        },
    }
