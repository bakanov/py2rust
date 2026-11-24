"""Millisecond clocks, finite journal bounds and protected local state paths."""

# ruff: noqa: PLR1711 - explicit subset returns
from documents import absolute, present, read, stamp

from py2rust.stdlib import (
    Json,
    env_get,
    floor,
    json_int,
    json_keys,
    json_loads,
    monotonic,
    path_resolve,
    path_same,
    unix_time,
)

MAX_TIME: int = 4102444799999
MAX_MONO: int = 9000000000000000


def setting(name: str, default: int) -> int:
    return json_int(json_loads(env_get(name, str(default))))


def state_path() -> str:
    return absolute(env_get("TIMER_STATE", "activity-state.json"), path_resolve("."))


def integer(value: Json, low: int, high: int) -> int:
    result: int = json_int(value)
    assert low <= result <= high, "integer outside allowed range"
    return result


def clocks() -> tuple[int, int]:
    path: str = env_get("TIMER_CLOCK", "")
    if path != "":
        value: Json = json_loads(read(absolute(path, path_resolve(".")), 256).data.decode())
        assert sorted(json_keys(value)) == ["mono_ms", "wall_ms"], "invalid injected clock fields"
        return (integer(value["wall_ms"], 0, MAX_TIME), integer(value["mono_ms"], 0, MAX_MONO))
    return (integer(floor(unix_time() * 1000.0), 0, MAX_TIME), integer(floor(monotonic() * 1000.0), 0, MAX_MONO))


def now(state: Json, sample: tuple[int, int]) -> int:
    previous: int = json_int(state["mono_ms"])
    assert sample[1] >= previous, "monotonic clock moved backward within a process"
    logical: int = json_int(state["clock_ms"]) + sample[1] - previous
    return integer(max(logical, sample[0]), 0, MAX_TIME)


def configure() -> None:
    assert 0 <= setting("TIMER_PORT", 8793) <= 65535, "invalid port"
    assert 1 <= setting("TIMER_SESSIONS", 128) <= 128, "invalid session limit"
    assert 1 <= setting("TIMER_INTERVALS", 256) <= 256, "invalid interval limit"
    for hook in ["TIMER_FAULT", "TIMER_PAUSE"]:
        assert env_get(hook, "") in ["", "before_commit", "after_commit"], "invalid checkpoint hook"
    paths: list[str] = [state_path(), state_path() + ".lock"]
    clock: str = env_get("TIMER_CLOCK", "")
    if clock != "":
        paths.append(absolute(clock, path_resolve(".")))
    for index in range(len(paths)):
        path: str = paths[index]
        if present(path):
            metadata: Json = stamp(path)
            assert json_int(metadata["links"]) == 1, "state, lock and clock must not have hard-link aliases"
        for previous in paths[:index]:
            assert previous != path, "state, lock and clock paths overlap"
            if present(path) and present(previous):
                assert not path_same(path, previous), "state, lock and clock files alias"
    clocks()
    return
