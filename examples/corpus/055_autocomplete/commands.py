"""Validate updates and lookups; normalized spellings share a term and its usage counter."""

from trie import (
    Index,
    Node,
    change,
    entries,
    entry,
    exact,
    find,
    normalized,
    suggestions,
    summary,
    usage,
)

from py2rust.stdlib import Json, json_int, json_string


def apply(index: Index, command: Json) -> tuple[Index, Json]:
    operation: str = json_string(command["op"])
    assert operation in [
        "PUT",
        "HIT",
        "GET",
        "DELETE",
        "SUGGEST",
        "EXPORT",
        "INSPECT",
    ], "unknown autocomplete operation"
    assert index.steps < 1000000000, "lifetime command limit reached"
    event: Json = {"step": index.steps + 1, "op": operation}
    if operation in ["PUT", "HIT", "GET", "DELETE"]:
        fields: list[str] = ["op", "term"]
        if operation == "PUT":
            fields.append("uses")
        if operation == "HIT":
            fields.append("amount")
        exact(command, fields)
        key: str = normalized(command["term"], False)
        original: Node = find(index.root, key)
        event["key"] = key
        event["found"] = original.terminal
        if operation == "PUT":
            count: int = usage(command["uses"])
            event["accepted"] = True
            if not original.terminal and index.root.words >= index.capacity:
                event["accepted"] = False
                event["reason"] = "capacity"
            else:
                index.root = change(index.root, key, 0, True, json_string(command["term"]), count)
                event["entry"] = entry(find(index.root, key), key)
        elif operation == "HIT":
            amount: int = json_int(command["amount"])
            assert 1 <= amount <= 1000000, "hit amount must be 1..1000000"
            if original.terminal:
                count: int = usage(original.uses + amount)
                index.root = change(index.root, key, 0, True, original.term, count)
                event["entry"] = entry(find(index.root, key), key)
        elif operation == "GET":
            event["entry"] = entry(original, key) if original.terminal else None
        elif original.terminal:
            index.root = change(index.root, key, 0, False, "", 0)
    elif operation == "SUGGEST":
        exact(command, ["op", "prefix", "offset", "limit"])
        prefix: str = normalized(command["prefix"], True)
        event["result"] = suggestions(index, prefix, json_int(command["offset"]), json_int(command["limit"]))
    elif operation == "EXPORT":
        exact(command, ["op"])
        event["entries"] = entries(index.root, "")
    else:
        exact(command, ["op"])
        event["index"] = summary(index)
    assert index.root.nodes <= 8192, "trie exceeds 8192 nodes"
    index.steps = index.steps + 1
    return (index, event)
