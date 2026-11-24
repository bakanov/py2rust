"""ZIP byte names, Unicode path extras and conservative portable-path diagnostics."""

# ruff: noqa: BLE001, PIE810 - normalized encoding errors; scalar subset suffix checks
from binary import number

from py2rust.stdlib import crc32, unicode_normalize


def decode_name(raw: bytes, flags: int, extra: bytes) -> tuple[str, str, list[str]]:
    codes: list[str] = []
    name: str = ""
    try:
        name = raw.decode() if flags & 2048 != 0 else raw.decode("cp437")
    except Exception:
        codes.append("name_encoding")
    cursor: int = 0
    tags: set[int] = set()
    while cursor < len(extra):
        if len(extra) - cursor < 4 or len(tags) >= 256:
            codes.append("extra_structure")
            break
        tag: int = number(extra, cursor, 2)
        size: int = number(extra, cursor + 2, 2)
        cursor = cursor + 4
        if size > len(extra) - cursor:
            codes.append("extra_structure")
            break
        if tag in tags:
            codes.append("duplicate_extra")
        tags.add(tag)
        value: bytes = extra[cursor : cursor + size]
        cursor = cursor + size
        if tag == 1:
            codes.append("zip64")
        if tag == 28789:
            try:
                assert size >= 5 and value[0] == 1 and number(value, 1, 4) == crc32(raw), "Unicode path extra"
                decoded: str = value[5:].decode()
                assert flags & 2048 == 0 or decoded == name, "conflicting Unicode path"
                name = decoded
            except Exception:
                codes.append("unicode_path_extra")
    components: list[str] = name.rstrip("/").split("/")
    unsafe_path: bool = name == "" or name.startswith("/") or "\\" in name or ":" in name or name.endswith("//")
    for part in components:
        if part in ["", ".", ".."] or part.endswith(" ") or part.endswith("."):
            unsafe_path = True
        stem: str = part.split(".")[0].upper()
        if stem in ["CON", "PRN", "AUX", "NUL"] or (
            len(stem) == 4 and stem[:3] in ["COM", "LPT"] and stem[3] in "123456789"
        ):
            unsafe_path = True
    for character in name:
        value: int = ord(character)
        if (
            value < 32
            or 127 <= value <= 159
            or value in [1564, 8206, 8207, 8232, 8233]
            or 8234 <= value <= 8238
            or 8294 <= value <= 8297
        ):
            unsafe_path = True
    if unsafe_path:
        codes.append("unsafe_name")
    return (name, unicode_normalize("NFC", name.rstrip("/")).casefold(), codes)
