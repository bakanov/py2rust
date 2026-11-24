"""Room state and bounded per-peer delivery queues; all policy stays in Python."""

from py2rust.stdlib import (
    Json,
    json_array,
    json_bool,
    json_float,
    json_int,
    json_keys,
    json_string,
    monotonic,
)


def store(state: Json, key: str, peer: Json) -> Json:
    peers: Json = state["peers"]
    peers[key] = peer
    state["peers"] = peers
    return state


def drop(state: Json, key: str, reason: str, drain: bool, policy: Json) -> Json:
    peer: Json = state["peers"][key]
    if json_string(peer["closing"]) == "" or not drain:
        peer["closing"] = reason
        peer["drain"] = drain
        peer["deadline"] = monotonic() + json_float(policy["close_ms"]) * 0.001
        if not drain:
            peer["queue"] = []
            peer["queued"] = 0
            peer["offset"] = 0
    return store(state, key, peer)


def enqueue(state: Json, key: str, line: str, policy: Json) -> Json:
    peer: Json = state["peers"][key]
    if json_string(peer["closing"]) != "":
        return state
    queue: list[Json] = json_array(peer["queue"])
    size: int = len(line.encode()) + 1
    pending: int = json_int(peer["queued"]) + size
    if len(queue) >= json_int(policy["queue_lines"]) or pending > json_int(policy["queue_bytes"]):
        return drop(state, key, "slow", False, policy)
    queue.append(line + "\n")
    peer["queue"] = queue
    peer["queued"] = pending
    return store(state, key, peer)


def broadcast(state: Json, room: str, line: str, policy: Json) -> Json:
    if room != "":
        for key in json_keys(state["peers"]):
            peer: Json = state["peers"][key]
            if json_string(peer["room"]) == room:
                state = enqueue(state, key, line, policy)
    return state


def add(state: Json, key: str, policy: Json) -> Json:
    peer: Json = {
        "nick": "",
        "room": "",
        "queue": [],
        "queued": 0,
        "offset": 0,
        "closing": "",
        "drain": False,
        "deadline": 0.0,
        "active": monotonic(),
        "partial": 0.0,
    }
    state = store(state, key, peer)
    return enqueue(state, key, "HELLO NICK JOIN SAY WHO ROOMS PING QUIT STATS", policy)


def remove(state: Json, key: str, policy: Json) -> Json:
    peers: Json = state["peers"]
    peer: Json = peers[key]
    del peers[key]
    state["peers"] = peers
    counts: Json = state["closed"]
    reason: str = json_string(peer["closing"])
    counts[reason] = json_int(counts[reason]) + 1
    state["closed"] = counts
    room: str = json_string(peer["room"])
    return broadcast(state, room, "LEAVE " + room + " " + json_string(peer["nick"]) + " " + reason, policy)


def ready_to_close(peer: Json) -> bool:
    return json_string(peer["closing"]) != "" and (
        not json_bool(peer["drain"]) or json_int(peer["queued"]) == 0 or monotonic() >= json_float(peer["deadline"])
    )
