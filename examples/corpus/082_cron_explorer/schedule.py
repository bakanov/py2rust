"""Explore UTC calendar days and selected minute/hour combinations in chronological order."""

from dataclasses import dataclass

from config import Job
from grammar import Expression, ordered

from py2rust.stdlib import (
    DateTime,
    Json,
    datetime_add_seconds,
    datetime_format,
    datetime_iso,
    datetime_parse,
)


@dataclass
class Search:
    runs: list[Json]
    more: bool
    next_omitted: str
    inspected_days: int


def explore(expression: Expression, job: Job) -> Search:
    midnight: DateTime = datetime_parse(datetime_format(job.start, "%Y-%m-%dT00:00:00Z"))
    minutes: list[int] = ordered(expression.fields[0].values)
    hours: list[int] = ordered(expression.fields[1].values)
    days: set[int] = expression.fields[2].values
    months: set[int] = expression.fields[3].values
    weekdays: set[int] = expression.fields[4].values
    use_and: bool = expression.fields[2].starred or expression.fields[4].starred
    result: list[Json] = []
    inspected: int = 0
    for offset in range(job.days + 1):
        day: DateTime = datetime_add_seconds(midnight, offset * 86400)
        if day >= job.end:
            break
        inspected = inspected + 1
        parts: list[str] = datetime_format(day, "%m %d %w").split(" ")
        month: int = int(parts[0])
        date: int = int(parts[1])
        weekday: int = int(parts[2])
        date_match: bool = date in days
        weekday_match: bool = weekday in weekdays
        matches: bool = (date_match and weekday_match) if use_and else (date_match or weekday_match)
        if month not in months or not matches:
            continue
        for hour in hours:
            for minute in minutes:
                candidate: DateTime = datetime_add_seconds(day, hour * 3600 + minute * 60)
                if candidate >= job.start and candidate < job.end:
                    text: str = datetime_iso(candidate)
                    if len(result) == job.limit:
                        return Search(result, True, text, inspected)
                    result.append({"utc": text, "weekday": weekday})
    return Search(result, False, "", inspected)
