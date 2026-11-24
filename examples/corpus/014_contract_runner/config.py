"""Validate fixture input before making any requests or changing snapshots."""

from py2rust.stdlib import (
    Json,
    env_get,
    json_array,
    json_bool,
    json_get,
    json_int,
    json_kind,
    json_loads,
    json_string,
    read_text,
    regex_fullmatch,
)


def text(value: Json, key: str, default: str) -> str:
    return json_string(json_get(value, key, default))


def load_config() -> Json:
    return json_loads(read_text(env_get("CONTRACT_CONFIG", "contracts.json")))


def base_url(config: Json) -> str:
    return env_get("CONTRACT_BASE", text(config, "base_url", ""))


def snapshot_directory() -> str:
    return env_get("CONTRACT_SNAPSHOTS", "snapshots")


def timeout(config: Json) -> int:
    return json_int(json_get(config, "timeout_ms", 1000))


def maximum_body(config: Json) -> int:
    return json_int(json_get(config, "max_body", 1048576))


def validate_config(config: Json) -> None:
    assert json_kind(config) == "object", "configuration must be an object"
    base: str = base_url(config)
    # The profile currently supports a single startswith prefix.
    assert base.startswith("http://") or base.startswith("https://"), "expected HTTP(S) URL"  # noqa: PIE810
    assert not base.endswith("/"), "base URL must not end in slash"
    assert "?" not in base and "#" not in base, "base URL must not contain query or fragment"
    assert timeout(config) > 0 and timeout(config) <= 60000, "timeout must be 1–60000 ms"
    assert maximum_body(config) > 0 and maximum_body(config) <= 1048576, "max_body must be 1–1048576"
    json_bool(json_get(config, "update_snapshots", False))
    cases: list[Json] = json_array(config["cases"])
    assert len(cases) > 0 and len(cases) <= 200, "expected 1–200 cases"
    names: set[str] = set()
    snapshots: set[str] = set()
    for case in cases:
        name: str = text(case, "name", "")
        assert name != "" and name not in names, "case names must be unique"
        names.add(name)
        method: str = text(case, "method", "GET")
        assert method in ["GET", "POST", "PUT", "DELETE"], "unsupported request method"
        path: str = text(case, "path", "")
        assert path.startswith("/") and not path.startswith("//"), "case path must be relative to base URL"
        assert "\r" not in path and "\n" not in path and "#" not in path, "invalid request path"
        status: int = json_int(case["status"])
        assert status >= 200 and status <= 599, "expected status must be 200–599"
        assert not ("body" in case and "text_body" in case), "choose JSON body or text_body"
        if "text_body" in case:
            json_string(case["text_body"])
        snapshot: str = text(case, "snapshot", "")
        if snapshot != "":
            assert regex_fullmatch("[A-Za-z0-9_-]+[.]json", snapshot), "unsafe snapshot name"
            assert snapshot not in snapshots, "snapshot names must be unique"
            snapshots.add(snapshot)
        seen: set[str] = set()
        for rule in json_array(json_get(case, "fields", [])):
            field: str = text(rule, "path", "")
            assert field == "$" or regex_fullmatch("[A-Za-z0-9_-]+([.][A-Za-z0-9_-]+)*", field), "invalid field path"
            assert field not in seen, "duplicate field assertion"
            seen.add(field)
            present: bool = json_bool(json_get(rule, "exists", True))
            assert present or "value" not in rule, "absent field cannot have an expected value"
    return  # noqa: PLR1711 - explicit return required by repository guidelines
