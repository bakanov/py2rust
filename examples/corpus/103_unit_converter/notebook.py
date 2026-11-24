"""Validate retained results by recomputation; append only successful conversions with stable identities."""

# ruff: noqa: BLE001, PLR1711 - domain failures are per-conversion outcomes
from conversion import convert, identifier, text
from units import Unit

from py2rust.stdlib import (
    Json,
    json_array,
    json_canonical,
    json_equal,
    json_int,
    json_keys,
    sha256_digest,
    sha256_new,
    sha256_update,
)


def encoded(value: Json) -> bytes:
    return (json_canonical(value) + "\n").encode()


def digest(data: bytes) -> str:
    return sha256_digest(sha256_update(sha256_new(), data))


def exact(value: Json, fields: list[str]) -> None:
    assert sorted(json_keys(value)) == sorted(fields), "unexpected fields"
    return


def entry(request: Json, available: dict[str, Unit]) -> Json:
    exact(request, ["id", "quantity", "to"])
    identifier(request["id"])
    result: Json = convert(text(request["quantity"]), text(request["to"]), available)
    return {"request": request, "result": result}


def load(book: Json, available: dict[str, Unit]) -> list[Json]:
    exact(book, ["version", "entries"])
    assert json_int(book["version"]) == 1, "unsupported notebook version"
    entries: list[Json] = json_array(book["entries"])
    assert len(entries) <= 256, "notebook entry limit"
    seen: set[str] = set()
    for stored in entries:
        exact(stored, ["request", "result"])
        checked: Json = entry(stored["request"], available)
        assert encoded(checked) == encoded(stored), "notebook result mismatch"
        name: str = identifier(stored["request"]["id"])
        assert name not in seen, "duplicate notebook identifier"
        seen.add(name)
    return entries


def attempt(entries: list[Json], request: Json, index: int, available: dict[str, Unit]) -> tuple[list[Json], Json]:
    try:
        created: Json = entry(request, available)
        name: str = identifier(request["id"])
        for stored in entries:
            if text(stored["request"]["id"]) == name:
                assert json_equal(stored["request"], request), "conversion identifier conflicts"
                return (entries, {"index": index, "status": "duplicate", "id": name})
        assert len(entries) < 256, "notebook entry limit"
        return (entries + [created], {"index": index, "status": "converted", "id": name})
    except Exception as error:
        return (entries, {"index": index, "status": "rejected", "request": request, "reason": str(error)})
