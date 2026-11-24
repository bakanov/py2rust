"""Atomically checkpoint records with their next-page cursor and page receipts."""

from model import checked_next, record_id

from py2rust.stdlib import (
    Json,
    env_get,
    json_array,
    json_equal,
    json_int,
    json_is_null,
    json_keys,
    json_loads,
    json_string,
    path_exists,
    path_resolve,
    pretty,
    read_text,
    write_text_atomic,
)


def state_path() -> str:
    return env_get("HARVEST_STATE", "harvest-state.json")


def validate_paths() -> None:
    paths: list[str] = [env_get("HARVEST_CONFIG", "harvest.json"), state_path(), state_path() + ".report.json"]
    for first in range(len(paths)):
        for second in range(first + 1, len(paths)):
            assert paths[first] != paths[second], "configuration, state and report must be different files"
            if path_exists(paths[first]) and path_exists(paths[second]):
                assert path_resolve(paths[first]) != path_resolve(paths[second]), "file paths alias one another"
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def save(state: Json) -> None:
    text: str = pretty(state)
    assert len(text.encode()) <= 16777216, "snapshot exceeds 16 MiB"
    write_text_atomic(state_path(), text)
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def load(policy: Json) -> Json:
    if not path_exists(state_path()):
        return {"version": 1, "policy": policy, "records": [], "pages": [], "next": policy["start"]}
    text: str = read_text(state_path())
    assert len(text.encode()) <= 16777216, "snapshot exceeds 16 MiB"
    state: Json = json_loads(text)
    assert json_keys(state) == ["next", "pages", "policy", "records", "version"], "invalid snapshot fields"
    assert json_int(state["version"]) == 1 and json_equal(state["policy"], policy), "snapshot policy mismatch"
    records: list[Json] = json_array(state["records"])
    assert len(records) <= json_int(policy["max_records"]), "stored record limit exceeded"
    identifiers: set[str] = set()
    for record in records:
        identifier: str = record_id(record)
        assert identifier not in identifiers, "duplicate stored record"
        identifiers.add(identifier)
    pages: list[Json] = json_array(state["pages"])
    assert len(pages) <= json_int(policy["max_pages"]), "stored page limit exceeded"
    seen: set[str] = set()
    expected: Json = policy["start"]
    added: int = 0
    for receipt in pages:
        assert json_keys(receipt) == ["added", "next", "received", "url"], "invalid page receipt"
        assert not json_is_null(expected) and json_equal(receipt["url"], expected), "broken cursor chain"
        url: str = json_string(receipt["url"])
        assert url not in seen, "repeated stored page URL"
        seen.add(url)
        count: int = json_int(receipt["received"])
        unique: int = json_int(receipt["added"])
        assert (
            count >= 0 and count <= json_int(policy["page_size"]) and unique >= 0 and unique <= count
        ), "invalid page counts"
        added = added + unique
        expected = checked_next(receipt["next"], policy, seen)
        assert json_equal(expected, receipt["next"]), "noncanonical stored next-page URL"
    assert added == len(records) and json_equal(state["next"], expected), "checkpoint disagrees with receipts"
    return state
