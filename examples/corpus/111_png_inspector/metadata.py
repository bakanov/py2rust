"""Interpret selected bounded PNG metadata; compressed payloads remain explicitly uninspected."""

from binary import keyword, unsigned, utf8

from py2rust.stdlib import Json, json_int, json_kind


def describe(name: str, data: bytes, header: Json, palette: int) -> Json:
    if name == "IHDR":
        assert len(data) == 13, "IHDR length"
        width: int = unsigned(data[:4])
        height: int = unsigned(data[4:8])
        depth: int = data[8]
        color: int = data[9]
        assert 1 <= width <= 2147483647 and 1 <= height <= 2147483647, "image dimensions"
        allowed: dict[int, list[int]] = {0: [1, 2, 4, 8, 16], 2: [8, 16], 3: [1, 2, 4, 8], 4: [8, 16], 6: [8, 16]}
        assert color in allowed and depth in allowed[color], "color and bit depth combination"
        assert data[10] == 0 and data[11] == 0 and data[12] in [0, 1], "header methods"
        return {
            "width": width,
            "height": height,
            "bit_depth": depth,
            "color_type": color,
            "compression": data[10],
            "filter": data[11],
            "interlace": data[12],
        }
    if name == "PLTE":
        assert 3 <= len(data) <= 768 and len(data) % 3 == 0, "palette length"
        entries: int = len(data) // 3
        if json_kind(header) == "object":
            color: int = json_int(header["color_type"])
            assert color not in [0, 4], "palette forbidden for grayscale"
            assert color != 3 or entries <= (1 << json_int(header["bit_depth"])), "palette exceeds bit depth"
        return {"entries": entries}
    if name == "IEND":
        assert len(data) == 0, "IEND length"
        return {}
    if name == "tRNS":
        assert json_kind(header) == "object", "header unavailable for transparency"
        color: int = json_int(header["color_type"])
        assert color in [0, 2, 3], "transparency forbidden with alpha"
        if color == 3:
            assert 1 <= len(data) <= palette, "palette transparency length"
            return {"alpha": list(data)}
        assert len(data) == (2 if color == 0 else 6), "transparent sample length"
        samples: list[int] = []
        for index in range(0, len(data), 2):
            samples.append(unsigned(data[index : index + 2]))
        return {"samples": samples}
    if name == "gAMA":
        assert len(data) == 4 and 1 <= unsigned(data) <= 2147483647, "gamma value"
        return {"gamma_times_100000": unsigned(data)}
    if name == "sRGB":
        assert len(data) == 1 and 0 <= data[0] <= 3, "rendering intent"
        return {"intent": data[0]}
    if name == "pHYs":
        assert len(data) == 9 and data[8] in [0, 1], "physical dimensions"
        assert unsigned(data[:4]) <= 2147483647 and unsigned(data[4:8]) <= 2147483647, "physical density range"
        return {"x": unsigned(data[:4]), "y": unsigned(data[4:8]), "unit": data[8]}
    if name == "tIME":
        assert len(data) == 7, "timestamp length"
        year: int = unsigned(data[:2])
        month: int = data[2]
        day: int = data[3]
        days: list[int] = [
            31,
            29 if year % 400 == 0 or (year % 4 == 0 and year % 100 != 0) else 28,
            31,
            30,
            31,
            30,
            31,
            31,
            30,
            31,
            30,
            31,
        ]
        assert 1 <= month <= 12 and 1 <= day <= days[month - 1], "calendar date"
        assert data[4] <= 23 and data[5] <= 59 and data[6] <= 60, "timestamp clock"
        return {"year": year, "month": month, "day": day, "hour": data[4], "minute": data[5], "second": data[6]}
    if name in ["tEXt", "zTXt", "iTXt", "iCCP"]:
        separator: int = data.find(b"\x00")
        assert separator >= 0, "missing keyword separator"
        key: str = keyword(data[:separator])
        tail: bytes = data[separator + 1 :]
        if name == "tEXt":
            assert b"\x00" not in tail, "null in text"
            return {"keyword": key, "text": tail.decode("latin-1")}
        if name in ["zTXt", "iCCP"]:
            assert len(tail) >= 1 and tail[0] == 0, "compression method"
            return {"keyword": key, "compressed_bytes": len(tail) - 1, "decoded": False}
        assert len(tail) >= 2 and tail[0] in [0, 1], "international text flags"
        compressed: bool = tail[0] == 1
        assert not compressed or tail[1] == 0, "compression method"
        language_end: int = tail[2:].find(b"\x00") + 2
        assert language_end >= 2, "missing language separator"
        language: bytes = tail[2:language_end]
        for value in language:
            assert value < 128, "non-ASCII language tag"
        rest: bytes = tail[language_end + 1 :]
        translated_end: int = rest.find(b"\x00")
        assert translated_end >= 0, "missing translated keyword separator"
        translated: str = utf8(rest[:translated_end])
        body: bytes = rest[translated_end + 1 :]
        if compressed:
            return {
                "keyword": key,
                "language": language.decode(),
                "translated": translated,
                "compressed_bytes": len(body),
                "decoded": False,
            }
        assert b"\x00" not in body, "null in international text"
        return {"keyword": key, "language": language.decode(), "translated": translated, "text": utf8(body)}
    return {"decoded": False}
