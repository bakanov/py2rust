"""Choose explicit fold/gap policies; retain every alternative so decisions can be audited."""

# ruff: noqa: C414 - sorting requires an explicit list in the executable subset

# ruff: noqa: BLE001 - bounded conversion errors become individual report rows
from schedule import Inspection

from py2rust.stdlib import (
    Json,
    datetime_parse,
    json_array,
    json_int,
    json_string,
    sha256_digest,
    sha256_new,
    sha256_update,
    timezone_local,
    timezone_project,
)


def convert(item: Json, inspection: Inspection) -> Json:
    row: Json = {
        "appointment": item,
        "status": "invalid",
        "reason": "timestamp or projection outside supported range",
        "resolution": None,
        "selected": None,
        "destinations": [],
    }
    try:
        source: bytes = inspection.zones[json_string(item["zone"])]
        resolution: Json = timezone_local(source, json_string(item["local"]))
        row["resolution"] = resolution
        kind: str = json_string(resolution["kind"])
        choices: list[Json] = json_array(resolution["candidates"])
        choice: int = 0
        policy: str = "unique"
        if kind == "fold":
            policy = json_string(item["ambiguity"])
            choice = 1 if policy == "later" else 0
        elif kind == "gap":
            choices = json_array(resolution["projections"])
            policy = json_string(item["gap"])
            choice = 1 if policy == "shift_forward" else 0
        if policy == "reject":
            row["status"] = "rejected"
            row["reason"] = kind + " requires an explicit selection policy"
            return row
        selected: Json = choices[choice]
        destinations: list[Json] = []
        for name in inspection.targets:
            projected: Json = timezone_project(inspection.zones[name], datetime_parse(json_string(selected["utc"])))
            destinations.append({"zone": name, "time": projected})
        row["selected"] = selected
        row["destinations"] = destinations
        row["status"] = "converted"
        row["reason"] = policy
    except Exception:
        row["status"] = "invalid"
    return row


def inspect(inspection: Inspection) -> Json:
    rows: list[Json] = []
    counts: Json = {"converted": 0, "rejected": 0, "invalid": 0}
    for item in inspection.appointments:
        row: Json = convert(item, inspection)
        rows.append(row)
        status: str = json_string(row["status"])
        counts[status] = json_int(counts[status]) + 1
    hashes: Json = {}
    for name in sorted(list(inspection.zones)):
        hashes[name] = sha256_digest(sha256_update(sha256_new(), inspection.zones[name]))
    return {"version": 1, "counts": counts, "tzif_sha256": hashes, "appointments": rows}
