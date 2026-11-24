"""Atomic resource/booking snapshots checked for overlapping active intervals."""

from model import (
    conflict,
    definition,
    find,
    normalize_booking,
    normalize_resource,
    setting,
)

from py2rust.stdlib import (
    Json,
    env_get,
    json_array,
    json_equal,
    json_float,
    json_int,
    json_keys,
    json_kind,
    json_loads,
    json_string,
    path_exists,
    pretty,
    read_text,
    write_text_atomic,
)


def state_path() -> str:
    return env_get("RESERVE_STATE", "reservations.json")


def load() -> Json:
    content: str = read_text(state_path())
    assert len(content.encode()) <= 8388608, "snapshot exceeds byte limit"
    state: Json = json_loads(content)
    assert json_keys(state) == ["bookings", "resources", "version"], "invalid snapshot fields"
    assert json_int(state["version"]) == 1, "unsupported snapshot version"
    return state


def save(state: Json) -> None:
    assert len(json_array(state["resources"])) <= setting("RESERVE_RESOURCES", 100), "resource limit exceeded"
    assert len(json_array(state["bookings"])) <= setting("RESERVE_BOOKINGS", 1000), "booking limit exceeded"
    content: str = pretty(state)
    assert len(content.encode()) <= 8388608, "snapshot exceeds byte limit"
    write_text_atomic(state_path(), content)
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def initialize() -> None:
    if not path_exists(state_path()):
        save({"version": 1, "resources": [], "bookings": []})
    state: Json = load()
    resources: list[Json] = json_array(state["resources"])
    bookings: list[Json] = json_array(state["bookings"])
    assert len(resources) <= setting("RESERVE_RESOURCES", 100), "stored resource limit exceeded"
    assert len(bookings) <= setting("RESERVE_BOOKINGS", 1000), "stored booking limit exceeded"
    names: set[str] = set()
    for resource in resources:
        assert json_equal(resource, normalize_resource(resource)), "invalid stored resource"
        identifier: str = json_string(resource["id"])
        assert identifier not in names, "duplicate resource ID"
        names.add(identifier)
    names.clear()
    previous: list[Json] = []
    for record in bookings:
        assert json_keys(record) == [
            "cancelled_at",
            "created_at",
            "end",
            "id",
            "owner",
            "resource",
            "start",
            "status",
            "title",
        ], "invalid booking fields"
        assert json_equal(normalize_booking(definition(record)), definition(record)), "booking is not normalized"
        identifier: str = json_string(record["id"])
        assert identifier not in names, "duplicate booking ID"
        names.add(identifier)
        assert (
            json_kind(find(resources, json_string(record["resource"]))) != "null"
        ), "booking references missing resource"
        created: float = json_float(record["created_at"])
        assert created >= 0.0, "invalid creation time"
        if json_string(record["status"]) == "active":
            assert json_float(record["cancelled_at"]) == 0.0, "active booking is marked cancelled"
            assert conflict(previous, record) == "", "stored active bookings overlap"
        else:
            assert json_string(record["status"]) == "cancelled", "invalid booking status"
            assert json_float(record["cancelled_at"]) >= created, "invalid cancellation time"
        previous.append(record)
    return  # noqa: PLR1711 - explicit return required by repository guidelines
