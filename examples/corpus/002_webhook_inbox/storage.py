"""Persistent receipt order and immutable, idempotent event identities."""

from model import normalize, setting

from py2rust.stdlib import (
    Json,
    env_get,
    json_array,
    json_equal,
    json_float,
    json_int,
    json_loads,
    json_string,
    path_exists,
    pretty,
    read_text,
    write_text_atomic,
)


def state_path() -> str:
    return env_get("INBOX_STATE", "inbox-state.json")


def load() -> Json:
    content: str = read_text(state_path())
    assert len(content.encode()) <= setting("INBOX_MAX_STATE", 8388608), "snapshot exceeds size limit"
    return json_loads(content)


def save(state: Json) -> None:
    content: str = pretty(state)
    assert len(content.encode()) <= setting("INBOX_MAX_STATE", 8388608), "snapshot exceeds size limit"
    write_text_atomic(state_path(), content)
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def initialize() -> None:
    if not path_exists(state_path()):
        save({"format": 1, "next_receipt": 1, "events": []})
    state: Json = load()
    assert json_int(state["format"]) == 1, "unsupported inbox format"
    events: list[Json] = json_array(state["events"])
    assert len(events) <= setting("INBOX_LIMIT", 1000), "stored event count exceeds limit"
    seen: set[str] = set()
    receipt: int = 1
    for item in events:
        event: Json = item["event"]
        assert json_equal(normalize(event), event), "stored envelope is not normalized"
        identifier: str = json_string(event["id"])
        assert identifier not in seen, "duplicate stored event ID"
        seen.add(identifier)
        assert json_int(item["receipt"]) == receipt, "receipt sequence is discontinuous"
        assert json_float(item["received_at"]) >= 0.0, "invalid received timestamp"
        receipt = receipt + 1
    assert json_int(state["next_receipt"]) == receipt, "invalid next receipt"
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def find(events: list[Json], identifier: str) -> Json:
    for item in events:
        if json_string(item["event"]["id"]) == identifier:
            return item
    return None


def statistics(state: Json) -> Json:
    sources: Json = {}
    kinds: Json = {}
    events: list[Json] = json_array(state["events"])
    for item in events:
        source: str = json_string(item["event"]["source"])
        kind: str = json_string(item["event"]["type"])
        if source not in sources:
            sources[source] = 0
        if kind not in kinds:
            kinds[kind] = 0
        sources[source] = json_int(sources[source]) + 1
        kinds[kind] = json_int(kinds[kind]) + 1
    return {"count": len(events), "next_receipt": state["next_receipt"], "sources": sources, "types": kinds}
