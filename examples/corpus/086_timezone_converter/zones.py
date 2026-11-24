"""Load bounded named TZif snapshots or the exact rules exported in a prior bundle."""

# ruff: noqa: C414 - sorting requires an explicit list in the executable subset

from dataclasses import dataclass

from documents import Document, read

from py2rust.stdlib import (
    Json,
    base64_decode,
    datetime_from_unix,
    json_keys,
    json_loads,
    json_string,
    path_join,
    path_resolve,
    path_stat,
    regex_fullmatch,
    timezone_project,
)


def zone_name(value: Json) -> str:
    name: str = json_string(value)
    assert len(name) <= 128 and regex_fullmatch("[A-Za-z0-9_+-]+(/[A-Za-z0-9_+-]+)*", name), "invalid zone name"
    return name


@dataclass
class ZoneSnapshot:
    zones: dict[str, bytes]
    inputs: list[Document]


def load_zones(path: str, names: set[str]) -> ZoneSnapshot:
    zones: dict[str, bytes] = {}
    inputs: list[Document] = []
    metadata: Json = path_stat(path, False)
    if json_string(metadata["kind"]) == "directory":
        root: str = path_resolve(path)
        for name in sorted(list(names)):
            target: str = path_resolve(path_join(root, name))
            assert target.startswith("/" if root == "/" else root + "/"), "zone escapes timezone directory"
            document: Document = read(target, 65536)
            inputs.append(document)
            zones[name] = document.data
    else:
        bundle: Document = read(path, 1572864)
        inputs.append(bundle)
        value: Json = json_loads(bundle.data.decode())
        assert sorted(json_keys(value)) == sorted(list(names)), "zone bundle must contain exactly the requested zones"
        for name in sorted(list(names)):
            encoded: str = json_string(value[name])
            assert len(encoded) <= 87384, "encoded zone exceeds byte limit"
            zones[name] = base64_decode(encoded)
    for name in sorted(list(names)):
        assert len(zones[name]) <= 65536, "zone exceeds 64 KiB"
        probe: Json = timezone_project(zones[name], datetime_from_unix(0))
        assert json_string(probe["utc"]) == "1970-01-01T00:00:00.000000+00:00", "invalid zone projection"
    return ZoneSnapshot(zones, inputs)
