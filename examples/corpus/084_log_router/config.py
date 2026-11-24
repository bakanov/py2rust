"""Explicit severity filters and finite source, batch and output bounds."""

# ruff: noqa: I001 - compact grouped runtime imports within 120 columns
# ruff: noqa: PLR1711 - explicit subset returns
from enum import Enum

from files import absolute, identity, present, read

from py2rust.stdlib import (
    Json, env_get, json_array, json_int, json_keys, json_loads, json_string, path_parent, path_resolve,
    regex_fullmatch
)


class Level(Enum):
    DEBUG = 10
    INFO = 20
    WARNING = 30
    ERROR = 40
    CRITICAL = 50


def severity(name: str) -> int:
    levels: dict[str, int] = {
        "DEBUG": Level.DEBUG.value,
        "INFO": Level.INFO.value,
        "WARNING": Level.WARNING.value,
        "ERROR": Level.ERROR.value,
        "CRITICAL": Level.CRITICAL.value,
    }
    assert name in levels, "unknown log level"
    return levels[name]


def exact(value: Json, keys: list[str]) -> None:
    assert sorted(json_keys(value)) == sorted(keys), "unexpected fields"
    return


def integer(value: Json, low: int, high: int) -> int:
    result: int = json_int(value)
    assert low <= result <= high, "integer outside bounds"
    return result


def identifier(value: Json) -> str:
    result: str = json_string(value)
    assert regex_fullmatch("[A-Za-z][A-Za-z0-9_-]{0,15}", result), "invalid identifier"
    return result


def configuration() -> Json:
    path: str = absolute(env_get("ROUTER_CONFIG", "router-job.json"), path_resolve("."))
    value: Json = json_loads(read(path, 65536).decode())
    exact(value, ["version", "sources", "routes", "output", "segment_bytes", "segments", "batch_lines"])
    assert json_int(value["version"]) == 1, "unsupported version"
    integer(value["segment_bytes"], 4096, 16384)
    integer(value["segments"], 1, 8)
    integer(value["batch_lines"], 1, 64)
    output: str = absolute(json_string(value["output"]), path_parent(path))
    assert output != path and output + ".lock" != path, "output overlaps configuration"
    value["output"] = output
    sources: list[Json] = json_array(value["sources"])
    routes: list[Json] = json_array(value["routes"])
    assert 1 <= len(sources) <= 4 and 1 <= len(routes) <= 4, "expected 1..4 sources and routes"
    source_ids: set[str] = set()
    identities: set[str] = set()
    for index in range(len(sources)):
        source: Json = sources[index]
        exact(source, ["id", "path"])
        key: str = identifier(source["id"])
        assert key not in source_ids, "duplicate source ID"
        source_ids.add(key)
        source_path: str = absolute(json_string(source["path"]), path_parent(path))
        assert source_path not in [path, output, output + ".lock"], "source overlaps controls"
        assert not source_path.startswith(output + "/"), "source is inside output directory"
        if present(source_path):
            token: str = identity(source_path)
            assert token not in identities, "aliased input sources"
            identities.add(token)
        source["path"] = source_path
        sources[index] = source
    route_ids: set[str] = set()
    for route in routes:
        exact(route, ["id", "sources", "minimum", "contains"])
        key: str = identifier(route["id"])
        assert key not in route_ids, "duplicate route ID"
        route_ids.add(key)
        severity(json_string(route["minimum"]))
        assert len(json_string(route["contains"]).encode()) <= 128, "filter exceeds 128 bytes"
        selected: list[Json] = json_array(route["sources"])
        assert 1 <= len(selected) <= len(source_ids), "invalid source selector"
        seen: set[str] = set()
        for entry in selected:
            name: str = json_string(entry)
            assert name in source_ids and name not in seen, "unknown or duplicate selected source"
            seen.add(name)
    value["sources"] = sources
    return value
