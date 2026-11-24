"""Strict request and index records; archive IDs never become arbitrary paths."""

# ruff: noqa: PLR1711 - explicit returns

from py2rust.stdlib import Json, json_int, json_keys, json_string, regex_fullmatch


def keys(value: Json, expected: list[str]) -> None:
    assert sorted(json_keys(value)) == sorted(expected), "unexpected record fields"
    return


def integer(value: Json, minimum: int, maximum: int) -> int:
    result: int = json_int(value)
    assert minimum <= result <= maximum, "integer outside allowed range"
    return result


def identifier(value: Json) -> str:
    result: str = json_string(value)
    assert regex_fullmatch("[A-Za-z0-9][A-Za-z0-9_-]{0,63}", result), "invalid archive ID"
    return result


def pathname(value: Json) -> str:
    result: str = json_string(value)
    assert 0 < len(result) <= 4096 and "\x00" not in result, "invalid source path"
    return result


def limits(value: Json) -> Json:
    keys(value, ["source_bytes", "compressed_bytes", "total_bytes"])
    return {
        "source_bytes": integer(value["source_bytes"], 0, 1073741824),
        "compressed_bytes": integer(value["compressed_bytes"], 20, 2147483648),
        "total_bytes": integer(value["total_bytes"], 0, 4294967296),
    }


def entry(value: Json) -> Json:
    keys(value, ["id", "source", "size", "sha256", "compressed_size", "compressed_sha256", "level"])
    identifier(value["id"])
    pathname(value["source"])
    integer(value["size"], 0, 1073741824)
    integer(value["compressed_size"], 20, 2147483648)
    integer(value["level"], 0, 9)
    for name in ["sha256", "compressed_sha256"]:
        assert regex_fullmatch("[0-9a-f]{64}", json_string(value[name])), "invalid digest"
    return value
