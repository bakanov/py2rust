"""Check persisted cursor identities, segment inventories and bounded counters."""

# ruff: noqa: I001 - compact grouped runtime imports within 120 columns
# ruff: noqa: PLR1711 - explicit subset returns
from config import exact, integer
from files import hashed, identity

from py2rust.stdlib import (
    Json, json_array, json_equal, json_int, json_keys, json_string, regex_fullmatch
)


def initial(config: Json) -> Json:
    sources: Json = {}
    segments: Json = {}
    for source in json_array(config["sources"]):
        sources[json_string(source["id"])] = {
            "identity": identity(json_string(source["path"])),
            "past": [],
            "offset": 0,
            "sha256": hashed(b""),
            "lines": 0,
        }
    for route in json_array(config["routes"]):
        segments[json_string(route["id"])] = 0
    return {"version": 1, "policy": config, "sources": sources, "segments": segments, "files": {}, "filtered": 0}


def checksum(value: Json) -> None:
    assert regex_fullmatch("[0-9a-f]{64}", json_string(value)), "invalid SHA-256"
    return


def validate(config: Json, value: Json) -> None:
    exact(value, ["version", "policy", "sources", "segments", "files", "filtered"])
    assert json_int(value["version"]) == 1 and json_equal(config, value["policy"]), "saved policy differs"
    source_ids: list[str] = []
    route_ids: list[str] = []
    identities: set[str] = set()
    total: int = 0
    for source in json_array(config["sources"]):
        key: str = json_string(source["id"])
        source_ids.append(key)
        cursor: Json = value["sources"][key]
        exact(cursor, ["identity", "past", "offset", "sha256", "lines"])
        past: list[Json] = json_array(cursor["past"])
        assert len(past) <= 32, "too many retired inputs"
        tokens: list[Json] = past + [cursor["identity"]]
        for item in tokens:
            token: str = json_string(item)
            assert regex_fullmatch("[0-9]+:[0-9]+", token) and token not in identities, "invalid input identity"
            identities.add(token)
        integer(cursor["offset"], 0, 67108864)
        total = total + integer(cursor["lines"], 0, 1099511627776)
        checksum(cursor["sha256"])
        assert json_int(cursor["offset"]) != 0 or json_string(cursor["sha256"]) == hashed(b""), "invalid empty prefix"
    exact(value["sources"], source_ids)
    names: list[str] = []
    records: int = 0
    for route in json_array(config["routes"]):
        key: str = json_string(route["id"])
        route_ids.append(key)
        last: int = integer(value["segments"][key], 0, json_int(config["segments"]) - 1)
        for index in range(last + 1):
            name: str = key + "." + str(index) + ".jsonl"
            if last == 0 and name not in json_keys(value["files"]):
                continue
            names.append(name)
            metadata: Json = value["files"][name]
            exact(metadata, ["bytes", "sha256", "records"])
            size: int = integer(metadata["bytes"], 1, json_int(config["segment_bytes"]))
            records = records + integer(metadata["records"], 1, size)
            checksum(metadata["sha256"])
    exact(value["segments"], route_ids)
    exact(value["files"], names)
    assert records <= total * len(route_ids), "output record count exceeds consumed lines"
    integer(value["filtered"], 0, total)
    return
