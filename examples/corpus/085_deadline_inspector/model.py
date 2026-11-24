"""Classify earliest observed completions against inclusive grace cutoffs."""

from enum import Enum

from schedule import Inspection

from py2rust.stdlib import (
    DateTime,
    Json,
    datetime_format,
    datetime_iso,
    datetime_parse,
    json_int,
    json_string,
)


class Status(Enum):
    ON_TIME = "on_time"
    LATE = "late"
    MISSING = "missing"
    PENDING = "pending"


def microseconds(value: DateTime) -> int:
    fields: list[str] = datetime_format(value, "%Y %j %H %M %S %f").split(" ")
    year: int = int(fields[0]) - 1
    days: int = 365 * year + year // 4 - year // 100 + year // 400 + int(fields[1]) - 1
    seconds: int = days * 86400 + int(fields[2]) * 3600 + int(fields[3]) * 60 + int(fields[4])
    return seconds * 1000000 + int(fields[5])


def inspect(inspection: Inspection) -> Json:
    received: dict[str, int] = {}
    times: dict[str, list[str]] = {}
    for job in inspection.jobs:
        key: str = json_string(job["id"])
        received[key] = 0
        times[key] = []
    for event in inspection.events:
        key: str = json_string(event["job"])
        received[key] = received[key] + 1
        text: str = json_string(event["completed_at"])
        if text not in times[key]:
            times[key].append(text)
    counts: Json = {"on_time": 0, "late": 0, "missing": 0, "pending": 0}
    rows: list[Json] = []
    future: int = 0
    duplicates: int = 0
    for job in inspection.jobs:
        key: str = json_string(job["id"])
        eligible: list[str] = []
        for text in sorted(times[key]):
            if datetime_parse(text) <= inspection.observed:
                eligible.append(text)
        deferred: int = len(times[key]) - len(eligible)
        repeated: int = received[key] - len(times[key])
        future = future + deferred
        duplicates = duplicates + repeated
        cutoff: DateTime = datetime_parse(json_string(job["cutoff"]))
        status: Status = Status.PENDING
        completed: Json = None
        delay: int = 0
        if len(eligible) > 0:
            completed = eligible[0]
            first: DateTime = datetime_parse(eligible[0])
            status = Status.ON_TIME if first <= cutoff else Status.LATE
            delay = max(0, microseconds(first) - microseconds(cutoff))
        elif inspection.observed >= cutoff:
            status = Status.MISSING
            delay = microseconds(inspection.observed) - microseconds(cutoff)
        counts[status.value] = json_int(counts[status.value]) + 1
        rows.append(
            {
                "id": key,
                "label": job["label"],
                "deadline": job["deadline"],
                "grace_seconds": job["grace_seconds"],
                "cutoff": job["cutoff"],
                "status": status.value,
                "completed_at": completed,
                "lateness_us": delay,
                "observed_events": len(eligible),
                "future_events": deferred,
                "duplicate_events": repeated,
            }
        )
    return {
        "version": 1,
        "observed_at": datetime_iso(inspection.observed),
        "counts": counts,
        "jobs": rows,
        "received_events": len(inspection.events),
        "future_events": future,
        "duplicate_events": duplicates,
    }
