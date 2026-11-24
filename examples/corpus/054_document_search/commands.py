"""Validated commands expose document changes and search results without leaking stale postings."""

from index import Index, replace, summary
from lexicon import document, exact, frequencies, identifier
from query import search

from py2rust.stdlib import Json, json_int, json_string


def apply(index: Index, command: Json) -> tuple[Index, Json]:
    operation: str = json_string(command["op"])
    assert operation in ["PUT", "DELETE", "GET", "SEARCH", "INSPECT"], "unknown search operation"
    assert index.steps < 1000000000, "lifetime command limit reached"
    event: Json = {"step": index.steps + 1, "op": operation}
    if operation == "PUT":
        exact(command, ["op", "document"])
        value: Json = document(command["document"])
        name: str = identifier(value["id"])
        frequencies(value)
        event["id"] = name
        event["replaced"] = name in index.records
        event["accepted"] = True
        if name not in index.records and len(index.records) >= index.capacity:
            event["accepted"] = False
            event["reason"] = "capacity"
        else:
            index = replace(index, name, value)
    elif operation in ["GET", "DELETE"]:
        exact(command, ["op", "id"])
        name: str = identifier(command["id"])
        event["id"] = name
        event["found"] = name in index.records
        if operation == "GET":
            event["document"] = index.records.get(name, None)
        elif name in index.records:
            index = replace(index, name, None)
    elif operation == "SEARCH":
        exact(command, ["op", "query", "offset", "limit"])
        event["result"] = search(index, command["query"], json_int(command["offset"]), json_int(command["limit"]))
    else:
        exact(command, ["op"])
        event["index"] = summary(index)
    index.steps = index.steps + 1
    return (index, event)
