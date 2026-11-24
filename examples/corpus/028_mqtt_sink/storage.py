"""Atomic per-topic history and retained payloads with a strict restart validator."""

import sys

from settings import snapshot
from wire import text, topic_name

from py2rust.stdlib import (
    Json,
    env_get,
    file_open,
    file_size,
    json_array,
    json_bool,
    json_get,
    json_int,
    json_keys,
    json_loads,
    json_string,
    path_exists,
    path_is_symlink,
    pretty,
    read_text,
    regex_fullmatch,
    write_text_atomic,
)


def payload(encoded: str, limit: int) -> bytes:
    assert regex_fullmatch("([0-9a-f]{2})*", encoded), "noncanonical payload hex"
    data: bytes = bytes.fromhex(encoded)
    assert len(data) <= limit, "retained payload too large"
    return data


def validate(state: Json, policy: dict[str, int]) -> None:
    assert json_keys(state) == ["sequence", "topics", "version"] and json_int(state["version"]) == 1, "invalid snapshot"
    sequence: int = json_int(state["sequence"])
    assert sequence >= 0, "invalid sequence"
    topics: Json = state["topics"]
    assert len(json_keys(topics)) <= policy["max_topics"], "topic capacity exhausted"
    used: int = 0
    highest: int = 0
    seen: set[int] = set()
    for name in json_keys(topics):
        topic_name(name.encode(), policy["topic_bytes"])
        entry: Json = topics[name]
        assert json_keys(entry) == ["history", "retained"], "invalid topic record"
        retained: str = json_string(entry["retained"])
        used = used + len(name.encode()) + len(payload(retained, policy["payload_bytes"]))
        history: list[Json] = json_array(entry["history"])
        assert len(history) > 0 and len(history) <= policy["history"], "invalid history length"
        previous: int = 0
        for item in history:
            assert json_keys(item) == ["client", "payload", "retain", "sequence"], "invalid history record"
            number: int = json_int(item["sequence"])
            assert number > previous and number <= sequence and number not in seen, "invalid history sequence"
            seen.add(number)
            highest = max(highest, number)
            previous = number
            client: str = json_string(item["client"])
            assert len(client.encode()) > 0 and len(client.encode()) <= 64, "invalid client ID"
            text(client.encode())
            encoded: str = json_string(item["payload"])
            used = used + len(client.encode()) + len(payload(encoded, policy["payload_bytes"]))
            if json_bool(item["retain"]):
                retained = encoded
        assert retained == json_string(entry["retained"]), "retained payload disagrees with history"
    assert highest == sequence and used <= policy["total_bytes"], "history sequence or byte budget invalid"
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def load(policy: dict[str, int]) -> Json:
    assert not path_is_symlink(snapshot()), "snapshot must not be a symlink"
    if not path_exists(snapshot()):
        return {"version": 1, "sequence": 0, "topics": {}}
    with file_open(snapshot(), "rb") as handle:
        assert file_size(handle) <= 8388608, "snapshot exceeds 8 MiB"
    state: Json = json_loads(read_text(snapshot()))
    validate(state, policy)
    return state


def publish(topic: str, data: bytes, client: str, retain: bool, policy: dict[str, int]) -> int:
    state: Json = load(policy)
    topics: Json = state["topics"]
    entry: Json = json_get(topics, topic, {"history": [], "retained": ""})
    history: list[Json] = json_array(entry["history"])
    number: int = json_int(state["sequence"]) + 1
    history.append({"sequence": number, "client": client, "payload": data.hex(), "retain": retain})
    entry["history"] = history[-policy["history"] :]
    if retain:
        entry["retained"] = data.hex()
    topics[topic] = entry
    state["topics"] = topics
    state["sequence"] = number
    validate(state, policy)
    output: str = pretty(state)
    assert len(output.encode()) <= 8388608, "snapshot exceeds 8 MiB"
    if env_get("MQTT_FAULT", "") == "before_checkpoint":
        sys.exit(75)
    write_text_atomic(snapshot(), output)
    if env_get("MQTT_FAULT", "") == "after_checkpoint":
        sys.exit(75)
    return number
