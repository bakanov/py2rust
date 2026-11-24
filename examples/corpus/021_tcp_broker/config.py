"""Finite broker limits and protected configuration/state paths."""

from py2rust.stdlib import (
    Json,
    env_get,
    json_get,
    json_int,
    json_keys,
    json_loads,
    path_exists,
    path_is_symlink,
    path_join,
    path_name,
    path_parent,
    path_resolve,
    path_same,
    read_text,
)


def state_path() -> str:
    return env_get("BROKER_STATE", "broker-state.json")


def shutdown_requested() -> bool:
    path: str = env_get("BROKER_SHUTDOWN", "")
    return path != "" and path_exists(path)


def distinct_paths(paths: list[str]) -> None:
    seen: set[str] = set()
    for index in range(len(paths)):
        value: str = paths[index]
        normalized: str = path_join(path_resolve(path_parent(value)), path_name(value))
        assert normalized not in seen, "broker paths overlap"
        seen.add(normalized)
        for previous in range(index):
            if path_exists(value) and path_exists(paths[previous]):
                assert not path_same(value, paths[previous]), "broker paths alias"
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def validate_paths() -> None:
    paths: list[str] = [state_path(), env_get("BROKER_CONFIG", "broker.json")]
    marker: str = env_get("BROKER_SHUTDOWN", "")
    if marker != "":
        paths.append(marker)
    assert not path_is_symlink(state_path()), "state must not be a symlink"
    distinct_paths(paths)
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def configuration() -> Json:
    validate_paths()
    text: str = read_text(env_get("BROKER_CONFIG", "broker.json"))
    assert len(text.encode()) <= 65536, "configuration exceeds 64 KiB"
    raw: Json = json_loads(text)
    for key in json_keys(raw):
        assert key in [
            "max_jobs",
            "max_payload",
            "max_frame",
            "frame_timeout_ms",
            "connection_frames",
        ], "unknown setting"
    jobs: int = json_int(json_get(raw, "max_jobs", 1000))
    payload: int = json_int(json_get(raw, "max_payload", 4096))
    frame: int = json_int(json_get(raw, "max_frame", 65536))
    timeout: int = json_int(json_get(raw, "frame_timeout_ms", 1000))
    frames: int = json_int(json_get(raw, "connection_frames", 32))
    assert jobs >= 1 and jobs <= 1000, "invalid retained job limit"
    assert frame >= 1024 and frame <= 65536, "invalid frame limit"
    assert payload >= 1 and payload <= 4096 and payload <= frame - 512, "invalid payload limit"
    assert timeout >= 50 and timeout <= 30000, "invalid frame deadline"
    assert frames >= 1 and frames <= 100, "invalid connection frame limit"
    return {
        "max_jobs": jobs,
        "max_payload": payload,
        "max_frame": frame,
        "frame_timeout_ms": timeout,
        "connection_frames": frames,
    }
