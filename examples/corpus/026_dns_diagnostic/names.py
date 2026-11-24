"""ASCII query names and bounded decoding of compressed DNS wire names."""

from py2rust.stdlib import int_to_bytes, regex_fullmatch


def query_name(text: str) -> str:
    if text == ".":
        return text
    if text.endswith("."):  # noqa: FURB188 - explicit suffix handling in the supported string subset
        text = text[:-1]
    assert len(text.encode()) <= 253, "query name exceeds 255 wire bytes"
    for label in text.split("."):
        assert regex_fullmatch("[A-Za-z0-9_-]{1,63}", label), "invalid ASCII query label"
    return text.lower() + "."


def encode_name(name: str) -> bytes:
    encoded: bytes = b""
    if name != ".":
        for label in name[:-1].split("."):
            encoded = encoded + int_to_bytes(len(label), 1, "big") + label.encode()
    return encoded + b"\x00"


def label_text(data: bytes) -> str:
    result: str = ""
    for index in range(len(data)):
        value: int = data[index]
        if value >= 33 and value <= 126 and value != 46 and value != 92:
            result = result + data[index : index + 1].decode().lower()
        else:
            digits: str = str(value)
            while len(digits) < 3:
                digits = "0" + digits
            result = result + "\\" + digits
    return result


def read_name(data: bytes, start: int) -> tuple[str, int]:
    cursor: int = start
    consumed: int = 0
    expanded: int = 1
    pointers: int = 0
    labels: list[str] = []
    seen: set[int] = set()
    for step in range(160):
        assert cursor >= 12 and cursor < len(data), "name outside packet"
        assert cursor not in seen, "compression pointer cycle"
        seen.add(cursor)
        length: int = data[cursor]
        if length & 0xC0 == 0xC0:
            assert cursor + 1 < len(data), "incomplete compression pointer"
            target: int = ((length & 0x3F) << 8) | data[cursor + 1]
            assert target >= 12 and target < cursor, "compression pointer must refer backward"
            pointers = pointers + 1
            assert pointers <= 32, "compression pointer budget exceeded"
            if consumed == 0:
                consumed = cursor + 2
            cursor = target
        else:
            assert length & 0xC0 == 0, "reserved label encoding"
            cursor = cursor + 1
            if length == 0:
                if consumed == 0:
                    consumed = cursor
                return (".".join(labels) + ".", consumed)
            assert cursor + length <= len(data), "label outside packet"
            expanded = expanded + length + 1
            assert expanded <= 255, "expanded name exceeds 255 wire bytes"
            labels.append(label_text(data[cursor : cursor + length]))
            cursor = cursor + length
    assert False, "name traversal budget exceeded"
    return ("", 0)
