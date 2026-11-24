"""Validate recorded runs, calculate medians and compare compatible workloads without timing equality claims."""
# ruff: noqa: I001, C414 - compact imports and explicit ordered lists
from model import exact, integer, suite
from workers import validate
from py2rust.stdlib import Json, json_array, json_equal, json_int, json_keys, json_string


def median(values: list[int]) -> int:
    ordered: list[int] = sorted(values)
    middle: int = len(ordered) // 2
    return ordered[middle] if len(ordered) % 2 == 1 else (ordered[middle - 1] + ordered[middle]) // 2


def statistics(cases: list[Json], runs: list[Json], repetitions: int) -> Json:
    output: Json = {}
    for case in cases:
        wall: list[int] = []
        sender: list[int] = []
        receiver: list[int] = []
        for run in runs:
            if json_string(run["case"]) == json_string(case["id"]) and json_string(run["status"]) == "ok":
                wall.append(json_int(run["wall_us"]))
                sender.append(json_int(run["sender"]["elapsed_us"]))
                receiver.append(json_int(run["receiver"]["elapsed_us"]))
        row: Json = {"successful": len(wall), "requested": repetitions, "wall_us": None,
                     "sender_us": None, "receiver_us": None, "sender_Bps": None, "receiver_Bps": None}
        if len(wall) > 0:
            row["wall_us"] = median(wall)
            row["sender_us"] = median(sender)
            row["receiver_us"] = median(receiver)
            row["sender_Bps"] = json_int(case["size"]) * 1000000 // median(sender)
            row["receiver_Bps"] = json_int(case["size"]) * 1000000 // median(receiver)
        output[json_string(case["id"])] = row
    return output


def checked(report: Json) -> Json:
    exact(report, ["version", "kind", "cases", "repetitions", "workers", "runs", "statistics"])
    assert json_int(report["version"]) == 1 and json_string(report["kind"]) == "benchmark", "expected benchmark report"
    cases: list[Json] = json_array(report["cases"])
    repetitions: int = integer(report["repetitions"], 1, 4)
    suite(cases, repetitions)
    exact(report["workers"], ["sender", "receiver"])
    for role in ["sender", "receiver"]:
        arguments: list[Json] = json_array(report["workers"][role])
        assert 1 <= len(arguments) <= 32, "invalid worker provenance"
        for argument in arguments:
            assert len(json_string(argument)) <= 8192, "worker argument limit"
    known: Json = {}
    for case in cases:
        known[json_string(case["id"])] = case
    runs: list[Json] = json_array(report["runs"])
    assert 1 <= len(runs) <= len(cases) * repetitions, "invalid run count"
    seen: set[str] = set()
    interrupted: bool = False
    for run in runs:
        exact(run, ["case", "trial", "status", "phase", "error", "sender", "receiver", "wall_us"])
        name: str = json_string(run["case"])
        assert name in json_keys(known) and not interrupted, "invalid run order or case"
        trial: int = integer(run["trial"], 1, repetitions)
        key: str = name + ":" + str(trial)
        assert key not in seen, "duplicate trial"
        seen.add(key)
        status: str = json_string(run["status"])
        assert status in ["ok", "failed", "interrupted"], "invalid run status"
        phases: list[str] = ["spawn_receiver", "readiness", "spawn_sender", "transfer", "reports"]
        assert json_string(run["phase"]) in phases, "invalid phase"
        assert len(json_string(run["error"])) <= 8192, "error text limit"
        ceiling: int = integer(run["wall_us"], 1, 120000000)
        if status == "ok":
            assert json_string(run["error"]) == "" and json_string(run["phase"]) == "reports", "inconsistent success"
            validate(run["sender"], "sender", known[name], ceiling)
            validate(run["receiver"], "receiver", known[name], ceiling)
        else:
            assert json_string(run["error"]) != "", "failed run needs a reason"
        interrupted = status == "interrupted"
    assert len(runs) == len(cases) * repetitions or interrupted, "incomplete benchmark"
    calculated: Json = statistics(cases, runs, repetitions)
    assert json_equal(report["statistics"], calculated), "incorrect recorded statistics"
    return calculated


def compare(baseline: Json, candidate: Json) -> list[Json]:
    before: Json = checked(baseline)
    after: Json = checked(candidate)
    first: Json = {}
    second: Json = {}
    for case in json_array(baseline["cases"]):
        first[json_string(case["id"])] = case
    for case in json_array(candidate["cases"]):
        second[json_string(case["id"])] = case
    names: set[str] = set(json_keys(first))
    names = names.union(set(json_keys(second)))
    rows: list[Json] = []
    for name in sorted(list(names)):
        status: str = "missing_baseline" if name not in json_keys(first) else "missing_candidate"
        change: Json = None
        if name in json_keys(first) and name in json_keys(second):
            status = "incompatible"
            if json_equal(first[name], second[name]):
                status = "unavailable"
                if (before[name]["successful"] == before[name]["requested"] and
                        after[name]["successful"] == after[name]["requested"]):
                    status = "comparable"
                    old: int = json_int(before[name]["wall_us"])
                    new: int = json_int(after[name]["wall_us"])
                    change = (new - old) * 1000000 // old
        rows.append({"case": name, "status": status, "wall_change_ppm": change,
                     "baseline": before[name] if name in json_keys(before) else None,
                     "candidate": after[name] if name in json_keys(after) else None})
    return rows
