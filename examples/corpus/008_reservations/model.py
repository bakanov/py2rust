"""UTC interval rules, canonical booking identities and agenda order."""

from py2rust.stdlib import (
    DateTime,
    Json,
    datetime_iso,
    datetime_parse,
    env_get,
    json_float,
    json_int,
    json_keys,
    json_parse,
    json_string,
    regex_fullmatch,
    regex_search,
    unix_time,
)


def setting(name: str, default: int) -> int:
    return json_int(json_parse(env_get(name, str(default)), None))


def clock() -> float:
    value: str = env_get("RESERVE_NOW", "")
    if value != "":
        return json_float(json_parse(value, None))
    return unix_time()


def valid_id(value: str) -> bool:
    return regex_fullmatch("[A-Za-z0-9_-]{1,64}", value)


def label(value: Json, limit: int) -> str:
    text: str = json_string(value).strip()
    assert len(text) >= 1 and len(text) <= limit, "invalid label length"
    assert not regex_search("[\\x00-\\x1f\\x7f]", text), "label contains controls"
    return text


def normalize_resource(value: Json) -> Json:
    assert json_keys(value) == ["id", "name"], "invalid resource fields"
    identifier: str = json_string(value["id"])
    assert valid_id(identifier), "invalid resource ID"
    return {"id": identifier, "name": label(value["name"], 120)}


def definition(record: Json) -> Json:
    return {
        "id": record["id"],
        "resource": record["resource"],
        "owner": record["owner"],
        "title": record["title"],
        "start": record["start"],
        "end": record["end"],
    }


def normalize_booking(value: Json) -> Json:
    assert json_keys(value) == ["end", "id", "owner", "resource", "start", "title"], "invalid booking fields"
    identifier: str = json_string(value["id"])
    resource: str = json_string(value["resource"])
    assert valid_id(identifier) and valid_id(resource), "invalid booking or resource ID"
    start: DateTime = datetime_parse(json_string(value["start"]))
    end: DateTime = datetime_parse(json_string(value["end"]))
    assert start < end, "interval must have positive duration"
    return {
        "id": identifier,
        "resource": resource,
        "owner": label(value["owner"], 80),
        "title": label(value["title"], 200),
        "start": datetime_iso(start),
        "end": datetime_iso(end),
    }


def find(records: list[Json], identifier: str) -> Json:
    for record in records:
        if json_string(record["id"]) == identifier:
            return record
    return None


def conflict(records: list[Json], proposed: Json) -> str:
    start: DateTime = datetime_parse(json_string(proposed["start"]))
    end: DateTime = datetime_parse(json_string(proposed["end"]))
    for record in records:
        if (
            json_string(record["resource"]) == json_string(proposed["resource"])
            and json_string(record["status"]) == "active"
        ):
            previous_start: DateTime = datetime_parse(json_string(record["start"]))
            previous_end: DateTime = datetime_parse(json_string(record["end"]))
            if start < previous_end and previous_start < end:
                return json_string(record["id"])
    return ""


def ordered(records: list[Json]) -> list[Json]:
    keys: list[tuple[str, str]] = []
    for record in records:
        # Canonical UTC strings have fixed-width dates and fractional seconds.
        keys.append((json_string(record["start"]), json_string(record["id"])))
    keys.sort()
    result: list[Json] = []
    for key in keys:
        result.append(find(records, key[1]))
    return result


def configure() -> None:
    assert setting("RESERVE_PORT", 8773) >= 0 and setting("RESERVE_PORT", 8773) <= 65535, "invalid port"
    assert setting("RESERVE_RESOURCES", 100) >= 1 and setting("RESERVE_RESOURCES", 100) <= 100, "invalid resource limit"
    assert setting("RESERVE_BOOKINGS", 1000) >= 1 and setting("RESERVE_BOOKINGS", 1000) <= 1000, "invalid booking limit"
    assert clock() >= 0.0, "invalid clock"
    return  # noqa: PLR1711 - explicit return required by repository guidelines
