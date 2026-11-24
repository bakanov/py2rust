"""Bounded staffing inputs and canonical typed workers/shifts."""

# ruff: noqa: PLR1711, C414 - explicit returns and typed-list sorting

from dataclasses import dataclass

from py2rust.stdlib import Json, json_array, json_int, json_keys, json_string


@dataclass
class Worker:
    name: str
    skills: list[str]
    availability: list[tuple[int, int]]
    max_minutes: int
    max_shifts: int
    preferences: dict[str, int]


@dataclass
class Shift:
    name: str
    start: int
    end: int
    required: int
    skill: str


@dataclass
class Problem:
    workers: list[Worker]
    shifts: list[Shift]
    rest: int
    balance: int
    budget: int


def exact(value: Json, fields: list[str]) -> None:
    assert json_keys(value) == sorted(fields), "unexpected object fields"
    return


def number(value: Json, minimum: int, maximum: int) -> int:
    result: int = json_int(value)
    assert minimum <= result <= maximum, "integer outside supported bounds"
    return result


def name(value: Json) -> str:
    result: str = json_string(value)
    assert 1 <= len(result) <= 64 and len(result.encode()) <= 256 and "\x00" not in result, "invalid name"
    return result


def worker_name(worker: Worker) -> str:
    return worker.name


def shift_name(shift: Shift) -> str:
    return shift.name


def load(value: Json) -> Problem:
    exact(value, ["version", "workers", "shifts", "rest_minutes", "balance_weight", "budget"])
    assert json_int(value["version"]) == 1, "unsupported problem version"
    shifts: list[Shift] = []
    shift_names: set[str] = set()
    positions: int = 0
    rows: list[Json] = json_array(value["shifts"])
    assert len(rows) <= 12, "shift count exceeds 12"
    for row in rows:
        exact(row, ["id", "start", "end", "required", "skill"])
        identifier: str = name(row["id"])
        assert identifier not in shift_names, "duplicate shift"
        shift_names.add(identifier)
        start: int = number(row["start"], 0, 10080)
        end: int = number(row["end"], 0, 10080)
        assert start < end and end - start <= 1440, "invalid shift interval"
        required: int = number(row["required"], 0, 4)
        positions = positions + required
        shifts.append(Shift(identifier, start, end, required, name(row["skill"])))
    assert positions <= 24, "staffing positions exceed 24"
    workers: list[Worker] = []
    worker_names: set[str] = set()
    rows = json_array(value["workers"])
    assert len(rows) <= 12, "worker count exceeds 12"
    for row in rows:
        exact(row, ["id", "skills", "availability", "max_minutes", "max_shifts", "preferences"])
        identifier: str = name(row["id"])
        assert identifier not in worker_names, "duplicate worker"
        worker_names.add(identifier)
        skills: set[str] = set()
        items: list[Json] = json_array(row["skills"])
        assert len(items) <= 8, "skill count exceeds eight"
        for item in items:
            skills.add(name(item))
        items = json_array(row["availability"])
        assert len(items) <= 32, "availability count exceeds 32"
        windows: list[tuple[int, int]] = []
        for item in items:
            exact(item, ["start", "end"])
            start: int = number(item["start"], 0, 10080)
            end: int = number(item["end"], 0, 10080)
            assert start < end, "invalid availability interval"
            windows.append((start, end))
        merged: list[tuple[int, int]] = []
        for window in sorted(windows):
            if len(merged) > 0 and window[0] <= merged[-1][1]:
                merged[-1] = (merged[-1][0], max(merged[-1][1], window[1]))
            else:
                merged.append(window)
        preferences: dict[str, int] = {}
        for key in json_keys(row["preferences"]):
            assert key in shift_names, "preference references an unknown shift"
            preferences[key] = number(row["preferences"][key], 0, 100)
        workers.append(
            Worker(
                identifier,
                sorted(list(skills)),
                merged,
                number(row["max_minutes"], 0, 10080),
                number(row["max_shifts"], 0, 12),
                preferences,
            )
        )
    return Problem(
        sorted(workers, key=worker_name),
        sorted(shifts, key=shift_name),
        number(value["rest_minutes"], 0, 1440),
        number(value["balance_weight"], 0, 100),
        number(value["budget"], 1, 100000),
    )


def document(problem: Problem) -> Json:
    workers: list[Json] = []
    shifts: list[Json] = []
    for worker in problem.workers:
        windows: list[Json] = []
        for window in worker.availability:
            windows.append({"start": window[0], "end": window[1]})
        workers.append(
            {
                "id": worker.name,
                "skills": worker.skills,
                "availability": windows,
                "max_minutes": worker.max_minutes,
                "max_shifts": worker.max_shifts,
                "preferences": worker.preferences,
            }
        )
    for shift in problem.shifts:
        shifts.append(
            {"id": shift.name, "start": shift.start, "end": shift.end, "required": shift.required, "skill": shift.skill}
        )
    return {
        "version": 1,
        "workers": workers,
        "shifts": shifts,
        "rest_minutes": problem.rest,
        "balance_weight": problem.balance,
        "budget": problem.budget,
    }
