"""Document bounds, exact number-preserving equality and escaped pointer paths."""

from py2rust.stdlib import (
    Json,
    int_from_decimal,
    json_array,
    json_canonical,
    json_keys,
    json_kind,
    regex_fullmatch,
    sha256_digest,
    sha256_new,
    sha256_update,
)


def fields(value: Json, names: list[str]) -> None:
    assert json_kind(value) == "object" and json_keys(value) == sorted(names), "unexpected document fields"
    return  # noqa: PLR1711


def child(path: str, key: str) -> str:
    return path + "/" + key.replace("~", "~0").replace("/", "~1")


def tokens(path: str) -> list[str]:
    assert len(path.encode()) <= 4096 and (path == "" or path.startswith("/")), "invalid pointer"
    assert regex_fullmatch("([^~]|~[01])*", path), "invalid pointer escape"
    result: list[str] = []
    if path != "":
        for part in path[1:].split("/"):
            result.append(part.replace("~1", "/").replace("~0", "~"))
    assert len(result) <= 24, "pointer exceeds 24 levels"
    return result


def index(token: str, size: int, insertion: bool) -> int:
    assert regex_fullmatch("0|[1-9][0-9]*", token), "array index must be canonical nonnegative decimal"
    position: int = int_from_decimal(token)
    assert position <= size if insertion else position < size, "array index is out of bounds"
    return position


def same(left: Json, right: Json) -> bool:
    return json_canonical(left) == json_canonical(right)


def digest(value: Json) -> str:
    return sha256_digest(sha256_update(sha256_new(), json_canonical(value).encode()))


def nodes(value: Json, path: str, depth: int, limit: int) -> int:
    assert depth <= 24 and len(path.encode()) <= 4096, "document nesting/path limit exceeded"
    count: int = 1
    if json_kind(value) == "object":
        for name in json_keys(value):
            count = count + nodes(value[name], child(path, name), depth + 1, limit)
            assert count <= limit, "document node limit exceeded"
    elif json_kind(value) == "array":
        items: list[Json] = json_array(value)
        for number in range(len(items)):
            count = count + nodes(items[number], child(path, str(number)), depth + 1, limit)
            assert count <= limit, "document node limit exceeded"
    return count


def validate(value: Json, limit: int) -> int:
    assert len(json_canonical(value).encode()) <= 4194304, "document exceeds 4 MiB"
    return nodes(value, "", 0, limit)
