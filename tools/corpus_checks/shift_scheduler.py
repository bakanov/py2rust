"""Exhaustive combination oracle, feasibility audits and publication tests for scheduler 063."""

# ruff: noqa: PLR1711 - explicit repository returns

from __future__ import annotations

import copy
import hashlib
import itertools
import json
import random
import selectors
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .common import Application
from .csv_json import canonical


def worker(identifier: str, **changes: object) -> dict:
    return {
        "id": identifier,
        "skills": ["support"],
        "availability": [{"start": 0, "end": 10080}],
        "max_minutes": 10080,
        "max_shifts": 12,
        "preferences": {},
        **changes,
    }


def shift(identifier: str, start: int, end: int, required: int = 1, skill: str = "support") -> dict:
    return {"id": identifier, "start": start, "end": end, "required": required, "skill": skill}


def problem(workers: list, shifts: list, **changes: object) -> dict:
    return {
        "version": 1,
        "workers": workers,
        "shifts": shifts,
        "rest_minutes": 0,
        "balance_weight": 0,
        "budget": 100000,
        **changes,
    }


def sample() -> dict:
    return problem(
        [
            worker("Ada", max_minutes=480, max_shifts=2, preferences={"morning": 0, "afternoon": 3}),
            worker("Ben", max_minutes=480, max_shifts=2, preferences={"morning": 2, "afternoon": 0}),
            worker("Chen", max_minutes=240, max_shifts=1, preferences={"morning": 1, "afternoon": 1}),
        ],
        [shift("morning", 480, 720, 2), shift("afternoon", 780, 1020)],
        rest_minutes=60,
        balance_weight=2,
    )


def normalized(value: dict) -> dict:
    result = copy.deepcopy(value)
    result["workers"].sort(key=lambda row: row["id"])
    result["shifts"].sort(key=lambda row: row["id"])
    for row in result["workers"]:
        row["skills"] = sorted(set(row["skills"]))
        # An independent endpoint sweep reconstructs the union of availability windows.
        changes = {}
        for window in row["availability"]:
            changes[window["start"]] = changes.get(window["start"], 0) + 1
            changes[window["end"]] = changes.get(window["end"], 0) - 1
        merged, active, start = [], 0, 0
        for point in sorted(changes):
            before = active
            active += changes[point]
            if before == 0 and active > 0:
                start = point
            if before > 0 and active == 0:
                merged.append({"start": start, "end": point})
        row["availability"] = merged
    return result


def eligible(person: dict, event: dict) -> bool:
    available = any(
        window["start"] <= event["start"] and event["end"] <= window["end"] for window in person["availability"]
    )
    return (
        event["skill"] in person["skills"]
        and available
        and person["max_shifts"] > 0
        and event["end"] - event["start"] <= person["max_minutes"]
    )


def audit_schedule(value: dict, assignments: list, complete: bool = True) -> tuple[int, tuple[str, ...]]:
    value = normalized(value)
    people = {row["id"]: row for row in value["workers"]}
    events = value["shifts"]
    assert len(assignments) == len(events)
    duties = {name: [] for name in people}
    preference = 0
    signature = []
    for event, row in zip(events, assignments, strict=True):
        assert set(row) == {"shift", "workers"} and row["shift"] == event["id"]
        crew = row["workers"]
        assert crew == sorted(set(crew)) and set(crew) <= set(people)
        assert len(crew) == event["required"] if complete else len(crew) <= event["required"]
        for name in crew:
            assert eligible(people[name], event)
            duties[name].append(event)
            preference += people[name]["preferences"].get(event["id"], 0)
        signature.extend(crew)
    for name, assigned in duties.items():
        assert len(assigned) <= people[name]["max_shifts"]
        assert sum(event["end"] - event["start"] for event in assigned) <= people[name]["max_minutes"]
        chronological = sorted(assigned, key=lambda event: (event["start"], event["end"]))
        assert all(
            first["end"] + value["rest_minutes"] <= second["start"]
            for first, second in itertools.pairwise(chronological)
        )
    score = preference + value["balance_weight"] * sum(len(assigned) ** 2 for assigned in duties.values())
    return score, tuple(signature)


def oracle(value: dict) -> tuple[int, tuple[str, ...]] | None:
    value = normalized(value)
    # Enumerate shift crews with itertools, then filter full schedules independently.
    options = [
        list(itertools.combinations([row["id"] for row in value["workers"] if eligible(row, event)], event["required"]))
        for event in value["shifts"]
    ]
    result = None
    for crews in itertools.product(*options):
        assignments = [
            {"shift": event["id"], "workers": list(crew)} for event, crew in zip(value["shifts"], crews, strict=True)
        ]
        try:
            candidate = audit_schedule(value, assignments)
        except AssertionError:
            continue
        if result is None or candidate < result:
            result = candidate
    return result


@dataclass
class Fixture:
    work: Path
    config: dict

    @property
    def path(self) -> Path:
        return self.work / "shift-job.json"

    @property
    def output(self) -> Path:
        return self.work / self.config["output"]

    def save(self) -> None:
        self.path.write_text(json.dumps(self.config, ensure_ascii=False))
        return

    def settings(self, mode: str = "write", **extra: str) -> dict:
        return {
            "SHIFT_CONFIG": str(self.path),
            "SHIFT_MODE": mode,
            "SHIFT_FAIL": "",
            "SHIFT_PAUSE": "",
            "SHIFT_CONTINUE": "",
            **extra,
        }


def fixture(directory: Path, name: str, value: dict, **changes: object) -> Fixture:
    work = directory / name
    work.mkdir(parents=True)
    fix = Fixture(work, {"problem": "staffing.json", "output": "shift-schedule", **changes})
    (work / "staffing.json").write_text(json.dumps(value, ensure_ascii=False))
    fix.save()
    return fix


def validate(value: dict, report: dict, exhaustive: bool = True) -> None:
    value = normalized(value)
    assert report["status"] in ["optimal", "feasible", "unsatisfiable", "search_limit"]
    assert set(report) == {
        "status",
        "complete_search",
        "attempts",
        "budget",
        "score",
        "schedule",
        "shortages",
        "diagnostic_prefix",
        "frontier",
        "problem_sha256",
    }
    assert report["problem_sha256"] == hashlib.sha256((canonical(value) + "\n").encode()).hexdigest()
    assert report["budget"] == value["budget"] and 0 <= report["attempts"] <= value["budget"]
    shortages = [
        {
            "shift": event["id"],
            "required": event["required"],
            "eligible": sum(eligible(row, event) for row in value["workers"]),
        }
        for event in value["shifts"]
        if sum(eligible(row, event) for row in value["workers"]) < event["required"]
    ]
    assert report["shortages"] == shortages
    found = report["status"] in ["optimal", "feasible"]
    assert report["complete_search"] == (report["status"] in ["optimal", "unsatisfiable"])
    if not report["complete_search"]:
        assert report["attempts"] == value["budget"]
    if found:
        score, signature = audit_schedule(value, report["schedule"])
        assert report["score"] == score and not report["diagnostic_prefix"] and report["frontier"] is None
    else:
        assert report["score"] is None and report["schedule"] == []
        audit_schedule(value, report["diagnostic_prefix"], complete=False)
        assert report["frontier"] is not None
        frontier = report["frontier"]
        event = next(row for row in value["shifts"] if row["id"] == frontier["next_shift"])
        assert [row["worker"] for row in frontier["candidates"]] == [row["id"] for row in value["workers"]]
        for person, row in zip(value["workers"], frontier["candidates"], strict=True):
            previous = [
                item
                for item in value["shifts"]
                if person["id"]
                in next(
                    assignment["workers"]
                    for assignment in report["diagnostic_prefix"]
                    if assignment["shift"] == item["id"]
                )
            ]
            reasons = set()
            if event["skill"] not in person["skills"]:
                reasons.add("skill")
            if not any(
                window["start"] <= event["start"] and event["end"] <= window["end"] for window in person["availability"]
            ):
                reasons.add("availability")
            if len(previous) + 1 > person["max_shifts"]:
                reasons.add("max_shifts")
            if sum(item["end"] - item["start"] for item in [*previous, event]) > person["max_minutes"]:
                reasons.add("max_minutes")
            if any(
                not (
                    old["end"] + value["rest_minutes"] <= event["start"]
                    or event["end"] + value["rest_minutes"] <= old["start"]
                )
                for old in previous
            ):
                reasons.add("overlap_or_rest")
            assert len(row["reasons"]) == len(set(row["reasons"])) and set(row["reasons"]) == reasons
    if shortages:
        assert report["status"] == "unsatisfiable" and report["attempts"] == 0
    if exhaustive:
        optimum = oracle(value)
        if report["status"] == "optimal":
            assert optimum == (score, signature)
        elif report["status"] == "unsatisfiable":
            assert optimum is None
        elif found:
            assert optimum is not None and optimum <= (score, signature)
    return


def outputs(fix: Fixture, report: dict) -> dict:
    value = json.loads((fix.work / fix.config["problem"]).read_bytes())
    lines = ["Status: " + report["status"], "Score: " + canonical(report["score"])]
    lines += [canonical(row["shift"]) + ": " + canonical(row["workers"]) for row in report["schedule"]]
    if report["status"] in ["unsatisfiable", "search_limit"]:
        lines += [
            "Individual eligibility shortages: " + canonical(report["shortages"]),
            "Diagnostic partial assignment: " + canonical(report["diagnostic_prefix"]),
            "Next-shift constraints at that prefix: " + canonical(report["frontier"]),
        ]
    expected = {
        "problem.json": (canonical(normalized(value)) + "\n").encode(),
        "schedule.json": (canonical(report) + "\n").encode(),
        "schedule.txt": ("\n".join(lines) + "\n").encode(),
    }
    manifest = {
        "version": 1,
        "files": {
            name: {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()} for name, raw in expected.items()
        },
    }
    expected["manifest.json"] = (json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode()
    actual = {path.name: path.read_bytes() for path in fix.output.iterdir()}
    assert actual == expected
    return actual


def success(app: Application, fix: Fixture, mode: str = "write", exhaustive: bool = True) -> dict:
    source = fix.work / fix.config["problem"]
    before = [fix.path.read_bytes(), source.read_bytes()]
    value = json.loads(before[1])
    result = app.run(fix.work, fix.settings(mode), timeout=180)
    assert result.returncode in [0, 1] and not result.stderr, (fix.work, result)
    report = json.loads(result.stdout)
    validate(value, report, exhaustive)
    assert result.returncode == int(report["status"] != "optimal")
    assert result.stdout == canonical(report) + "\n"
    assert before == [fix.path.read_bytes(), source.read_bytes()]
    if mode == "write":
        outputs(fix, report)
    else:
        assert not fix.output.exists()
    assert not list(fix.work.glob(".shift-schedule-*"))
    return report


def failure(app: Application, fix: Fixture, message: str = "", **extra: str) -> None:
    existed = fix.output.exists() or fix.output.is_symlink()
    before = fix.output.read_bytes() if fix.output.is_file() else None
    result = app.run(fix.work, fix.settings(**extra), timeout=30)
    assert result.returncode == 2 and result.stderr and message in result.stderr and not result.stdout, (
        result,
        message,
    )
    assert (fix.output.exists() or fix.output.is_symlink()) == existed
    if before is not None:
        assert fix.output.read_bytes() == before
    assert not list(fix.work.glob(".shift-schedule-*"))
    return


def scenarios(app: Application, directory: Path) -> dict:
    rng = random.Random(63063)
    observations = []
    shifts = [shift("a", 0, 60), shift("b", 90, 150)]
    count = 0
    for mask in range(16):
        people = [
            worker(
                name,
                availability=[
                    {"start": shifts[event]["start"], "end": shifts[event]["end"]}
                    for event in range(2)
                    if mask & (1 << (index * 2 + event))
                ],
                max_minutes=120,
                max_shifts=2,
            )
            for index, name in enumerate(["A", "B"])
        ]
        for first, second in itertools.product(range(3), repeat=2):
            events = [{**shifts[0], "required": first}, {**shifts[1], "required": second}]
            fix = fixture(
                directory,
                f"exhaustive-{mask}-{first}-{second}",
                problem(people, events, rest_minutes=30, balance_weight=1),
            )
            result = success(app, fix, "preview")
            assert result["complete_search"]
            observations.append(result)
            count += 1
    for index, limits in enumerate(itertools.product([0, 60, 120], [0, 60, 120], range(3), range(3))):
        people = [
            worker("A", max_minutes=limits[0], max_shifts=limits[2]),
            worker("B", max_minutes=limits[1], max_shifts=limits[3]),
        ]
        fix = fixture(directory, "workload-" + str(index), problem(people, shifts, balance_weight=2))
        observations.append(success(app, fix, "preview"))
    print(app.engine + " shift scheduler: 144 availability/staffing and 81 workload cases passed", flush=True)
    cases = [
        problem([], []),
        problem([], [shift("zero", 0, 60, 0)]),
        sample(),
        problem([worker("solo")], [shift("a", 0, 60), shift("b", 30, 90)]),
        problem([worker("solo")], [shift("a", 0, 60), shift("b", 70, 130)], rest_minutes=11),
        problem([worker("solo", max_minutes=119)], [shift("a", 0, 60), shift("b", 70, 130)]),
        problem(
            [worker("世界", availability=[{"start": 30, "end": 60}, {"start": 0, "end": 30}]), worker("é")],
            [shift("🙂", 0, 60)],
            balance_weight=1,
        ),
        problem(
            [worker("gap", availability=[{"start": 0, "end": 29}, {"start": 30, "end": 60}])], [shift("gap", 0, 60)]
        ),
    ]
    for _ in range(40):
        events = [
            shift(
                "s" + str(index),
                index * 60,
                index * 60 + rng.choice([30, 60, 90]),
                rng.randrange(3),
                rng.choice(["support", "ops"]),
            )
            for index in range(rng.randrange(5))
        ]
        people = []
        for index in range(rng.randrange(5)):
            skills = rng.choice([[], ["support"], ["ops"], ["support", "ops"]])
            windows = rng.choice(
                [
                    [{"start": 0, "end": 600}],
                    [{"start": 60, "end": 180}],
                    [{"start": 0, "end": 120}, {"start": 150, "end": 600}],
                    [],
                ]
            )
            people.append(
                worker(
                    "w" + str(index),
                    skills=skills,
                    availability=windows,
                    max_minutes=rng.choice([0, 60, 120, 240, 600]),
                    max_shifts=rng.randrange(5),
                    preferences={event["id"]: rng.randrange(10) for event in events},
                )
            )
        cases.append(problem(people, events, rest_minutes=rng.choice([0, 15, 60]), balance_weight=rng.randrange(4)))
    for index, value in enumerate(cases):
        first = fixture(directory, "case-" + str(index), value)
        report = success(app, first)
        assert report["complete_search"]
        observations.append(report)
        shuffled = copy.deepcopy(value)
        rng.shuffle(shuffled["workers"])
        rng.shuffle(shuffled["shifts"])
        for person in shuffled["workers"]:
            rng.shuffle(person["availability"])
            rng.shuffle(person["skills"])
        second = fixture(directory, "permuted-" + str(index), shuffled)
        assert success(app, second) == report
        assert {p.name: p.read_bytes() for p in first.output.iterdir()} == {
            p.name: p.read_bytes() for p in second.output.iterdir()
        }
    return {
        "exhaustive_availability_staffing": count,
        "workload_combinations": 81,
        "other_problems": len(cases),
        "generated_problems": 40,
        "permutations": len(cases),
        "reports_sha256": hashlib.sha256(canonical(observations).encode()).hexdigest(),
    }


def budgets(app: Application, directory: Path) -> dict:
    value = sample()
    full = success(app, fixture(directory, "full", value))
    observations = []
    previous_score = None
    for budget in range(1, full["attempts"] + 2):
        report = success(app, fixture(directory, "budget-" + str(budget), {**value, "budget": budget}))
        if report["score"] is not None:
            assert previous_score is None or report["score"] <= previous_score
            previous_score = report["score"]
        observations.append(report)
    assert observations[-1]["status"] == "optimal" and observations[-2]["status"] == "optimal"
    assert {row["status"] for row in observations} == {"optimal", "feasible", "search_limit"}
    value = problem([worker("A", preferences={"s": 10}), worker("B", preferences={"s": 0})], [shift("s", 0, 60)])
    first = success(app, fixture(directory, "nonoptimal-incumbent", {**value, "budget": 1}))
    best = success(app, fixture(directory, "improved-incumbent", value))
    assert first["status"] == "feasible" and first["score"] == 10
    assert best["status"] == "optimal" and best["score"] == 0
    impossible = problem([worker("A")], [shift("a", 0, 60), shift("b", 0, 60)])
    truncated = success(app, fixture(directory, "unknown-impossible", {**impossible, "budget": 1}))
    proved = success(app, fixture(directory, "proved-impossible", impossible))
    assert truncated["status"] == "search_limit" and proved["status"] == "unsatisfiable"
    return {
        "prefix_budgets": len(observations),
        "status_and_improvement_cases": 4,
        "reports_sha256": hashlib.sha256(canonical(observations).encode()).hexdigest(),
    }


def invalid_inputs(app: Application, directory: Path) -> int:
    base = problem([worker("A")], [shift("s", 0, 60)])
    variants = [None, [], {}, {**base, "extra": 1}]
    variants += [{key: val for key, val in base.items() if key != missing} for missing in base]
    for key, values in {
        "version": [0, 2, True, 1.0, None],
        "rest_minutes": [-1, 1441, True, 1.0, "1", None],
        "balance_weight": [-1, 101, True, 1.0, None],
        "budget": [0, 100001, True, 1.0, None],
        "workers": [None, {}, "", True],
        "shifts": [None, {}, "", True],
    }.items():
        variants += [{**base, key: value} for value in values]
    for collection, row in [("workers", base["workers"][0]), ("shifts", base["shifts"][0])]:
        malformed = [None, [], {}, {**row, "extra": 1}]
        malformed += [{key: val for key, val in row.items() if key != missing} for missing in row]
        malformed += [{**row, "id": val} for val in ["", "a\x00", "x" * 65, "🙂" * 65, True, 1, None, [], {}]]
        variants += [{**base, collection: [value]} for value in malformed]
        variants.append({**base, collection: [row, row]})
    for field, values in {
        "start": [-1, 10081, True, 1.0, None],
        "end": [-1, 0, 1441, 10081, True, 1.0, None],
        "required": [-1, 5, True, 1.0, None],
        "skill": ["", "x" * 65, "a\x00", True, 1, None, [], {}],
    }.items():
        variants += [{**base, "shifts": [{**base["shifts"][0], field: value}]} for value in values]
    for field, values in {
        "skills": [None, {}, "support", [None], [True], [1], [""], ["x\x00"], ["x" * 65], ["support"] * 9],
        "availability": [
            None,
            {},
            "",
            [None],
            [{}],
            [{"start": 0}],
            [{"end": 1}],
            [{"start": 0, "end": 1, "extra": 1}],
            [{"start": 0, "end": 0}],
            [{"start": 1, "end": 0}],
            [{"start": -1, "end": 1}],
            [{"start": 0, "end": 10081}],
            [{"start": True, "end": 1}],
            [{"start": 0, "end": 1.0}],
            [{"start": 0, "end": 1}] * 33,
        ],
        "max_minutes": [-1, 10081, True, 1.0, None],
        "max_shifts": [-1, 13, True, 1.0, None],
        "preferences": [None, [], "", {"missing": 1}, {"s": -1}, {"s": 101}, {"s": True}, {"s": 1.0}, {"s": None}],
    }.items():
        variants += [{**base, "workers": [{**base["workers"][0], field: value}]} for value in values]
    for index, value in enumerate(variants):
        failure(app, fixture(directory, "problem-" + str(index), value))
    count = len(variants)
    for key in ["problem", "output"]:
        for index, value in enumerate(["", "\x00", None, True, 1, [], {}]):
            fix = fixture(directory, f"config-{key}-{index}", base)
            fix.path.write_text(json.dumps({**fix.config, key: value}))
            failure(app, fix)
            count += 1
        fix = fixture(directory, "missing-" + key, base)
        fix.path.write_text(json.dumps({k: v for k, v in fix.config.items() if k != key}))
        failure(app, fix)
        count += 1
    fix = fixture(directory, "extra-config", base)
    fix.path.write_text(json.dumps({**fix.config, "extra": 1}))
    failure(app, fix)
    count += 1
    failure(app, fixture(directory, "mode", base), "invalid scheduler mode", SHIFT_MODE="bad")
    count += 1
    for name in ["staffing.json", "shift-job.json"]:
        for index, raw in enumerate([b"\xff", b"{", b"[] trailing", b"[NaN]", b"[Infinity]", b'{"a":1,"a":2}']):
            fix = fixture(directory, f"raw-{name}-{index}", base)
            (fix.work / name).write_bytes(raw)
            failure(app, fix)
            count += 1
    return count


def limits(app: Application, directory: Path) -> dict:
    names = ["w" + str(index).zfill(2) for index in range(12)]
    people = [worker(name) for name in names]
    events = [shift("s" + str(index).zfill(2), index * 2, index * 2 + 1, 2) for index in range(12)]
    fix = fixture(directory, "maximum-dimensions", problem(people, events, budget=1))
    report = success(app, fix, exhaustive=False)
    assert report["status"] == "search_limit"
    failure(app, fixture(directory, "workers-above", problem([*people, worker("extra")], [])), "worker count")
    failure(app, fixture(directory, "shifts-above", problem([], [*events, shift("extra", 60, 61)])), "shift count")
    failure(
        app,
        fixture(directory, "slots-above", problem(people, [{**events[0], "required": 3}, *events[1:]])),
        "positions",
    )
    full = problem(people, [shift("s" + str(i), i * 2, i * 2 + 1, 4) for i in range(6)])
    report = success(app, fixture(directory, "budget-maximum", full), exhaustive=False)
    assert report["attempts"] == 100000 and report["status"] == "feasible" and report["score"] == 0
    # Two workers doing all twelve one-minute shifts reach the maximum supported objective value.
    people = [
        worker(name, max_shifts=12, max_minutes=12, preferences={event["id"]: 100 for event in events})
        for name in ["a", "b"]
    ]
    report = success(
        app, fixture(directory, "maximum-score", problem(people, events, rest_minutes=1, balance_weight=100))
    )
    assert report["score"] == 31200 and report["status"] == "optimal"
    skills = ["🙂" * 63 + str(index) for index in range(8)]
    people = [
        worker("🙂" * 64, skills=skills, availability=[{"start": 0, "end": 10080}] * 32, preferences={"🙂" * 64: 100})
    ]
    full = problem(people, [shift("🙂" * 64, 8640, 10080, skill=skills[-1])], rest_minutes=1440, balance_weight=100)
    report = success(app, fixture(directory, "field-maxima", full))
    assert report["score"] == 200
    for name, maximum in [("shift-job.json", 65536), ("staffing.json", 1048576)]:
        fix = fixture(directory, "bytes-" + name, sample())
        path = fix.work / name
        raw = path.read_bytes()
        path.write_bytes(raw + b" " * (maximum - len(raw)))
        success(app, fix, "preview")
        path.write_bytes(raw + b" " * (maximum + 1 - len(raw)))
        failure(app, fix, "byte limit")
        path.write_bytes(raw)
    return {
        "workers": 12,
        "shifts": 12,
        "staff_per_shift": 4,
        "staffing_positions": 24,
        "budget": 100000,
        "maximum_score": 31200,
        "week_minutes": 10080,
        "shift_duration": 1440,
        "rest_minutes": 1440,
        "skills": 8,
        "availability_windows": 32,
        "name_characters": 64,
        "name_bytes": 256,
        "preference_cost": 100,
        "balance_weight": 100,
        "config_bytes": 65536,
        "problem_bytes": 1048576,
    }


def paused(app: Application, fix: Fixture) -> subprocess.Popen:
    process = subprocess.Popen(
        app.command,
        cwd=fix.work,
        env=app.environment(fix.settings(SHIFT_PAUSE="ready", SHIFT_CONTINUE=str(fix.work / "continue"))),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )
    with selectors.DefaultSelector() as selector:
        selector.register(process.stdout, selectors.EVENT_READ)
        ready = bool(selector.select(20))
    if not ready or process.stdout.readline() != "PAUSED ready\n":
        process.kill()
        raise AssertionError(process.communicate(timeout=5))
    return process


def stop(process: subprocess.Popen) -> None:
    if process.poll() is None:
        process.kill()
    process.communicate(timeout=5)
    return


def publication(app: Application, directory: Path) -> int:
    points = [
        "validated",
        "stage",
        "problem.json",
        "schedule.json",
        "schedule.txt",
        "manifest.json",
        "ready",
        "published",
    ]
    for point in points:
        fix = fixture(directory, "fault-" + point, sample())
        reference = success(app, fix, "preview")
        result = app.run(fix.work, fix.settings(SHIFT_FAIL=point))
        assert result.returncode == 2 and "injected failure: " + point in result.stderr and not result.stdout
        assert not list(fix.work.glob(".shift-schedule-*"))
        if point == "published":
            outputs(fix, reference)
        else:
            assert not fix.output.exists()
            success(app, fix)
    for name in ["problem", "config", "destination"]:
        fix = fixture(directory, "changed-" + name, sample())
        process = paused(app, fix)
        try:
            if name == "destination":
                fix.output.mkdir()
                (fix.output / "keep").write_bytes(b"another writer")
            else:
                path = fix.path if name == "config" else fix.work / fix.config[name]
                with path.open("ab") as stream:
                    stream.write(b" ")
            (fix.work / "continue").touch()
            output, error = process.communicate(timeout=20)
            assert process.returncode == 2 and error and not output
            assert not list(fix.work.glob(".shift-schedule-*"))
            if name == "destination":
                assert list(fix.output.iterdir()) == [fix.output / "keep"]
                assert (fix.output / "keep").read_bytes() == b"another writer"
            else:
                assert "input changed before publication" in error and not fix.output.exists()
        finally:
            stop(process)
    fix = fixture(directory, "killed", sample())
    reference = success(app, fix, "preview")
    process = paused(app, fix)
    stop(process)
    assert not fix.output.exists()
    abandoned = list(fix.work.glob(".shift-schedule-*"))
    assert len(abandoned) == 1
    old = {path.name: path.read_bytes() for path in abandoned[0].iterdir()}
    result = app.run(fix.work, fix.settings())
    assert result.returncode == 0 and not result.stderr
    outputs(fix, reference)
    assert {path.name: path.read_bytes() for path in abandoned[0].iterdir()} == old
    return len(points) + 4


def paths(app: Application, directory: Path) -> int:
    for name in ["file", "directory", "symlink", "dangling", "same-problem", "same-config"]:
        fix = fixture(directory, "destination-" + name, sample())
        if name == "file":
            fix.output.write_bytes(b"preserve")
        elif name == "directory":
            fix.output.mkdir()
            (fix.output / "keep").write_bytes(b"preserve")
        elif name in ["symlink", "dangling"]:
            fix.output.symlink_to(fix.work / ("staffing.json" if name == "symlink" else "missing"))
        else:
            fix.config["output"] = "staffing.json" if name == "same-problem" else "shift-job.json"
            fix.save()
        failure(app, fix, "output directory already exists")
    for name in ["staffing.json", "shift-job.json"]:
        fix = fixture(directory, "symlink-" + name, sample())
        path = fix.work / name
        path.rename(fix.work / "original")
        path.symlink_to(fix.work / "original")
        original = (fix.work / "original").read_bytes()
        failure(app, fix, "regular file")
        assert path.is_symlink() and (fix.work / "original").read_bytes() == original
    fix = fixture(directory, "readonly", sample())
    parent = fix.work / "readonly"
    parent.mkdir()
    fix.config["output"] = "readonly/result"
    fix.save()
    parent.chmod(0o500)
    try:
        failure(app, fix)
        assert not list(parent.iterdir())
    finally:
        parent.chmod(0o700)
    return 9


def check(app: Application, directory: Path) -> dict:
    cases = scenarios(app, directory / "scenarios")
    budget_cases = budgets(app, directory / "budgets")
    print(
        app.engine + " shift scheduler: exhaustive scores, deterministic ties and search-budget semantics passed",
        flush=True,
    )
    invalid = invalid_inputs(app, directory / "invalid")
    bounds = limits(app, directory / "limits")
    faults = publication(app, directory / "publication")
    path_cases = paths(app, directory / "paths")
    print(app.engine + " shift scheduler: validation, capacity, publication and path cases passed", flush=True)
    return {
        **cases,
        "budgets": budget_cases,
        "invalid_inputs": invalid,
        "limits": bounds,
        "publication_cases": faults,
        "path_cases": path_cases,
    }
