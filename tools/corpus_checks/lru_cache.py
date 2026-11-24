"""A logical-access-clock oracle checks recency, accounting, saved state and complete replay bundles."""

from __future__ import annotations

import copy
import hashlib
import json
import random
import selectors
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .common import Application
from .csv_json import canonical

COUNTERS = [
    "steps",
    "gets",
    "hits",
    "misses",
    "puts",
    "overwrites",
    "dropped",
    "deletes",
    "deleted",
    "evictions",
    "resizes",
    "peeks",
    "inspections",
]


def command(op: str, key: str = "", **fields: object) -> dict:
    return {"op": op, **({"key": key} if op in {"GET", "PUT", "DELETE", "PEEK"} else {}), **fields}


def envelope(state: dict) -> dict:
    return {"state": state, "sha256": hashlib.sha256(canonical(state).encode()).hexdigest()}


def fresh(capacity: int) -> dict:
    return {"version": 1, "capacity": capacity, "entries": [], "stats": dict.fromkeys(COUNTERS, 0)}


@dataclass
class Fixture:
    work: Path
    config: dict

    @property
    def path(self) -> Path:
        return self.work / "cache-job.json"

    @property
    def output(self) -> Path:
        return self.work / self.config["output"]

    def save(self) -> None:
        self.path.write_text(json.dumps(self.config, ensure_ascii=False))
        return  # noqa: PLR1711

    def settings(self, mode: str = "write", **extra: str) -> dict:
        return {
            "LRU_CONFIG": str(self.path),
            "LRU_MODE": mode,
            "LRU_FAIL": "",
            "LRU_PAUSE": "",
            "LRU_CONTINUE": "",
            **extra,
        }


def fixture(
    directory: Path, name: str, commands: list, capacity: int = 2, prior: dict | None = None, **changes: object
) -> Fixture:
    work = directory / name
    work.mkdir(parents=True)
    (work / "trace.json").write_text(json.dumps(commands, ensure_ascii=False))
    config = {"trace": "trace.json", "state": "", "capacity": capacity, "output": "cache-run", **changes}
    if prior is not None:
        (work / "prior.json").write_text(canonical(prior))
        config["state"] = "prior.json"
    fix = Fixture(work, config)
    fix.save()
    return fix


def metrics(stats: dict) -> dict:
    return {"counters": copy.deepcopy(stats), "hit_rate": stats["hits"] / stats["gets"] if stats["gets"] else 0.0}


def oracle(fix: Fixture) -> tuple[dict, list, dict]:
    state = fresh(fix.config["capacity"])
    if fix.config["state"]:
        state = json.loads((fix.work / fix.config["state"]).read_bytes())["state"]
    values = {entry["key"]: copy.deepcopy(entry["value"]) for entry in state["entries"]}
    ranks = {entry["key"]: rank for rank, entry in enumerate(state["entries"])}
    stats, capacity = copy.deepcopy(state["stats"]), state["capacity"]
    before = stats["steps"]
    trace = json.loads((fix.work / fix.config["trace"]).read_bytes())
    events = []

    def entries() -> list:
        return [{"key": name, "value": copy.deepcopy(values[name])} for name in sorted(ranks, key=ranks.get)]

    for instruction in trace:
        op, key = instruction["op"], instruction.get("key", "")
        found, previous = key in values, copy.deepcopy(values.get(key))
        stats["steps"] += 1
        event = {"step": stats["steps"], "op": op}
        if op in {"GET", "PEEK"}:
            event.update(key=key, hit=found, value=previous)
            if op == "GET":
                stats["gets"] += 1
                stats["hits" if found else "misses"] += 1
                if found:
                    ranks[key] = stats["steps"]
            else:
                stats["peeks"] += 1
        elif op == "PUT":
            stats["puts"] += 1
            stats["overwrites"] += int(found)
            if capacity:
                values[key] = copy.deepcopy(instruction["value"])
                ranks[key] = stats["steps"]
            else:
                stats["dropped"] += 1
            event.update(key=key, stored=capacity > 0, replaced=found, previous=previous)
        elif op == "DELETE":
            stats["deletes"] += 1
            stats["deleted"] += int(found)
            if found:
                del values[key]
                del ranks[key]
            event.update(key=key, deleted=found, value=previous)
        elif op == "RESIZE":
            stats["resizes"] += 1
            capacity = instruction["capacity"]
            event["capacity"] = capacity
        elif op == "INSPECT":
            stats["inspections"] += 1
            event.update(capacity=capacity, entries=entries(), stats=metrics(stats))
        else:
            raise AssertionError(op)
        if op in {"PUT", "RESIZE"}:
            evicted = []
            while len(values) > capacity:
                victim = min(ranks, key=ranks.get)
                evicted.append({"key": victim, "value": copy.deepcopy(values.pop(victim))})
                del ranks[victim]
                stats["evictions"] += 1
            event["evicted"] = evicted
        events.append(event)
    after = {"version": 1, "capacity": capacity, "entries": entries(), "stats": stats}
    report = {
        "before_steps": before,
        "after_steps": stats["steps"],
        "commands": len(trace),
        "capacity": capacity,
        "entries": entries(),
        "stats": metrics(stats),
    }
    return envelope(after), events, report


def outputs(fix: Fixture, expected: tuple[dict, list, dict]) -> None:
    saved, events, report = expected
    assert sorted(path.name for path in fix.output.iterdir()) == ["events.jsonl", "report.json", "state.json"]
    assert (fix.output / "state.json").read_text() == canonical(saved) + "\n"
    assert (fix.output / "events.jsonl").read_text() == "".join(canonical(event) + "\n" for event in events)
    assert canonical(json.loads((fix.output / "report.json").read_bytes())) == canonical(report)
    return  # noqa: PLR1711


def success(app: Application, fix: Fixture, mode: str = "write") -> tuple[dict, list, dict]:
    expected = oracle(fix)
    inputs = [fix.path, fix.work / fix.config["trace"]]
    if fix.config["state"]:
        inputs.append(fix.work / fix.config["state"])
    before = [path.read_bytes() for path in inputs]
    result = app.run(fix.work, fix.settings(mode), timeout=45)
    assert result.returncode == 0 and not result.stderr, (result, fix.config)
    assert canonical(json.loads(result.stdout)) == canonical(expected[2])
    assert [path.read_bytes() for path in inputs] == before
    if mode == "write":
        outputs(fix, expected)
        assert (fix.output / "report.json").read_text() == result.stdout
    else:
        assert not fix.output.exists()
    assert not list(fix.work.glob(".lru-cache-*"))
    return expected


def failure(app: Application, fix: Fixture, message: str, **extra: str) -> None:
    existed = fix.output.exists() or fix.output.is_symlink()
    original = fix.output.read_bytes() if fix.output.is_file() else None
    result = app.run(fix.work, fix.settings(**extra), timeout=45)
    assert result.returncode == 2 and message in result.stderr and not result.stdout, (result, message, fix.config)
    assert (fix.output.exists() or fix.output.is_symlink()) == existed
    if original is not None:
        assert fix.output.read_bytes() == original
    assert not list(fix.work.glob(".lru-cache-*"))
    return  # noqa: PLR1711


def sample() -> list:
    return [
        command("PUT", "a", value={"list": [1, True, None]}),
        command("PUT", "b", value=None),
        command("INSPECT"),
        command("GET", "a"),
        command("PUT", "c", value="世界"),
        command("GET", "b"),
        command("PEEK", "a"),
        command("PUT", "a", value=[-0.0, 2**63 - 1]),
        command("DELETE", "absent"),
        command("DELETE", "c"),
        command("PUT", "d", value=False),
        command("INSPECT"),
        command("RESIZE", capacity=0),
        command("PUT", "discarded", value=3),
        command("GET", "discarded"),
        command("RESIZE", capacity=2),
        command("PUT", "x", value=0.1),
        command("INSPECT"),
    ]


def check(app: Application, directory: Path) -> dict:
    cases = [(0, []), (2, []), (0, sample()), (1, sample()), (2, sample()), (8, sample())]
    cases.append(
        (
            2,
            [
                command("PUT", "a", value=1),
                command("PUT", "b", value=2),
                command("PEEK", "a"),
                command("PUT", "c", value=3),
                command("GET", "a"),
                command("INSPECT"),
            ],
        )
    )
    values = [None, False, True, -(2**63), 2**63 - 1, 1.0, -0.0, 5e-324, "\x00世界😀", [], {}, {"x": [1.0, False]}]
    cases.append(
        (
            2,
            [
                item
                for value in values
                for item in [command("PUT", "value", value=value), command("GET", "value"), command("INSPECT")]
            ],
        )
    )
    rng = random.Random(510051)
    for _ in range(32):
        trace = []
        for index in range(rng.randrange(50, 151)):
            op = rng.choice(["GET", "PUT", "PUT", "DELETE", "PEEK", "INSPECT", "RESIZE"])
            key = rng.choice(["a", "b", "c", "é", "e\u0301", "世界", "a\x00b"])
            fields = {"value": {"index": index, "data": rng.choice(values)}} if op == "PUT" else {}
            if op == "RESIZE":
                fields = {"capacity": rng.randrange(9)}
            trace.append(command(op, key, **fields))
        cases.append((rng.randrange(9), trace))
    observations = []
    for index, (size, trace) in enumerate(cases):
        fix = fixture(directory, f"trace-{index}", trace, size)
        success(app, fix, "preview")
        expected = success(app, fix)
        observations.append(expected)
        repeated = fixture(
            directory, f"unchanged-{index}", [], expected[0]["state"]["capacity"], state=str(fix.output / "state.json")
        )
        success(app, repeated)
        assert (fix.output / "state.json").read_bytes() == (repeated.output / "state.json").read_bytes()
    # Split every boundary, including an empty prefix/suffix, and consume the actual saved state.
    trace = sample()
    full = fixture(directory, "full", trace)
    expected = success(app, full)
    for split in range(len(trace) + 1):
        prefix = fixture(directory, f"prefix-{split}", trace[:split])
        prefix_result = success(app, prefix)
        suffix = fixture(
            directory,
            f"suffix-{split}",
            trace[split:],
            prefix_result[0]["state"]["capacity"],
            state=str(prefix.output / "state.json"),
        )
        suffix_result = success(app, suffix)
        assert canonical(suffix_result[0]) == canonical(expected[0])
        assert (prefix.output / "events.jsonl").read_bytes() + (suffix.output / "events.jsonl").read_bytes() == (
            full.output / "events.jsonl"
        ).read_bytes()
    return {
        "traces": len(cases),
        "generated_traces": 32,
        "previews": len(cases),
        "unchanged_restores": len(cases),
        "split_replays": len(trace) + 1,
        "invalid_commands": invalid_commands(app, directory),
        "state_checks": states(app, directory),
        "capacity_checks": limits(app, directory),
        "publication_checks": publication(app, directory),
        "results_sha256": hashlib.sha256(canonical(observations).encode()).hexdigest(),
    }


def invalid_commands(app: Application, directory: Path) -> int:
    bad = [
        None,
        1,
        False,
        [],
        {},
        {"op": "get", "key": "x"},
        {"op": "UNKNOWN"},
        {"op": True},
        {"op": "GET"},
        {"op": "PUT", "key": "x"},
        {"op": "DELETE", "key": "x", "value": 1},
        {"op": "INSPECT", "key": "x"},
        {"op": "RESIZE"},
        command("GET", ""),
        command("GET", "x" * 129),
    ]
    bad.extend(
        {"op": op, "key": value} for op in ["GET", "PUT", "DELETE", "PEEK"] for value in [None, False, 1, [], {}]
    )
    bad.extend(command("RESIZE", capacity=value) for value in [-1, 257, True, 1.0, "1", None])
    for index, row in enumerate(bad):
        failure(app, fixture(directory, f"command-{index}", [command("PUT", "before", value=1), row]), "command 2:")
    configs = [{"capacity": value} for value in [-1, 257, True, 1.0, "1", None]]
    configs += [{"trace": ""}, {"trace": True}, {"output": ""}, {"state": None}, {"unknown": 1}]
    for index, changes in enumerate(configs):
        failure(app, fixture(directory, f"config-{index}", [], **changes), "")
    failure(app, fixture(directory, "mode", []), "invalid LRU mode", LRU_MODE="invalid")
    for index, raw in enumerate([b"{}", b"null", b"[NaN]", b"[1,]", b"[\xff]", b"[9223372036854775808]"]):
        fix = fixture(directory, f"malformed-{index}", [])
        (fix.work / "trace.json").write_bytes(raw)
        failure(app, fix, "")
    return len(bad) + len(configs) + 1 + 6


def states(app: Application, directory: Path) -> int:
    initial = fixture(directory, "state-initial", sample()[:12])
    good = success(app, initial)[0]
    bad = [{"state": good["state"], "sha256": "0" * 64}, {**good, "extra": 1}, {"state": good["state"]}]
    variations = [
        {"version": 2},
        {"version": True},
        {"capacity": 0},
        {"capacity": 257},
        {"capacity": 1.0},
        {"entries": good["state"]["entries"] * 2},
        {"entries": []},
        {"entries": [None]},
        {"entries": [{"key": "", "value": None}]},
        {"entries": [{"key": "x", "value": 1, "extra": 1}]},
        {"extra": 1},
    ]
    bad.extend(envelope({**good["state"], **change}) for change in variations)
    for name in COUNTERS:
        bad.append(envelope({**good["state"], "stats": {**good["state"]["stats"], name: -1}}))
        altered = copy.deepcopy(good["state"])
        del altered["stats"][name]
        bad.append(envelope(altered))
    for changes in [
        {"hits": 100},
        {"steps": 0},
        {"deleted": 100},
        {"overwrites": 100},
        {"dropped": 100},
        {"evictions": 100},
        {"puts": True},
        {"extra": 1},
    ]:
        bad.append(envelope({**good["state"], "stats": {**good["state"]["stats"], **changes}}))
    for index, snapshot in enumerate(bad):
        failure(app, fixture(directory, f"state-{index}", [], prior=snapshot), "")
    failure(app, fixture(directory, "capacity-mismatch", [], capacity=3, prior=good), "configured capacity differs")
    for index, (gets, hits) in enumerate([(2**53 + 3, 2**53 + 1), (2**63 - 2, 2**63 - 3), (0, 0)]):
        state = fresh(2)
        state["stats"].update(steps=gets, gets=gets, hits=hits, misses=gets - hits)
        success(app, fixture(directory, f"large-rate-{index}", [], prior=envelope(state)))
    full = fresh(2)
    full["stats"].update(steps=2**63 - 1, gets=2**63 - 1, misses=2**63 - 1)
    failure(app, fixture(directory, "counter-overflow", [command("GET", "x")], prior=envelope(full)), "command 1:")
    return len(bad) + 5


def limits(app: Application, directory: Path) -> int:
    success(app, fixture(directory, "command-count-exact", [command("PEEK", "missing")] * 2000))
    failure(app, fixture(directory, "command-count-over", [command("PEEK", "missing")] * 2001), "trace exceeds")
    trace = [command("PUT", str(index), value=index) for index in range(257)]
    result = success(app, fixture(directory, "capacity-exact", trace, capacity=256))
    assert [row["key"] for row in result[0]["state"]["entries"]] == [str(index) for index in range(1, 257)]
    success(app, fixture(directory, "key-exact", [command("PUT", "😀" * 32, value=None)]))
    failure(app, fixture(directory, "key-over", [command("PUT", "😀" * 32 + "a", value=None)]), "key must contain")
    success(app, fixture(directory, "value-exact", [command("PUT", "x", value="x" * 16382)]))
    failure(app, fixture(directory, "value-over", [command("PUT", "x", value="x" * 16383)]), "value exceeds")
    nested = 1
    for _ in range(16):
        nested = [nested]
    success(app, fixture(directory, "depth-exact", [command("PUT", "x", value=nested)]))
    failure(app, fixture(directory, "depth-over", [command("PUT", "x", value=[nested])]), "value nesting exceeds")
    for name, limit, filename in [
        ("trace", 4194304, "trace.json"),
        ("config", 65536, "cache-job.json"),
        ("state", 8388608, "prior.json"),
    ]:
        fix = fixture(directory, name + "-bytes-exact", [], prior=envelope(fresh(2)))
        path = fix.work / filename
        raw = path.read_bytes()
        path.write_bytes(raw + b" " * (limit - len(raw)))
        success(app, fix)
        over = fixture(directory, name + "-bytes-over", [], prior=envelope(fresh(2)))
        (over.work / filename).write_bytes(raw + b" " * (limit + 1 - len(raw)))
        failure(app, over, "input byte limit exceeded")
    many = [command("PUT", str(index), value="x" * 4096) for index in range(256)] + [command("INSPECT")] * 40
    failure(app, fixture(directory, "events-over", many, capacity=256), "events exceed 16 MiB")
    return 16


def paused(app: Application, fix: Fixture) -> subprocess.Popen:
    signal = fix.work / "continue"
    process = subprocess.Popen(
        app.command,
        cwd=fix.work,
        env=app.environment(fix.settings(LRU_PAUSE="ready", LRU_CONTINUE=str(signal))),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )
    with selectors.DefaultSelector() as selector:
        selector.register(process.stdout, selectors.EVENT_READ)
        ready = bool(selector.select(10))
    if not ready or process.stdout.readline() != "PAUSED ready\n":
        process.kill()
        output, error = process.communicate(timeout=5)
        raise AssertionError((output, error))
    return process


def publication(app: Application, directory: Path) -> int:
    points = ["validated", "stage", "state.json", "events.jsonl", "report.json", "ready", "published"]
    for point in points:
        fix = fixture(directory, "fault-" + point, sample())
        result = app.run(fix.work, fix.settings(LRU_FAIL=point))
        assert result.returncode == 2 and "injected failure: " + point in result.stderr and not result.stdout
        assert not list(fix.work.glob(".lru-cache-*"))
        if point == "published":
            outputs(fix, oracle(fix))
        else:
            assert not fix.output.exists()
            success(app, fix)
    for name in ["trace", "configuration", "state", "destination"]:
        fix = fixture(directory, "changed-" + name, sample(), prior=envelope(fresh(2)))
        process = paused(app, fix)
        try:
            if name == "destination":
                fix.output.mkdir()
                (fix.output / "keep").write_bytes(b"another writer")
            else:
                filename = {"trace": "trace.json", "configuration": "cache-job.json", "state": "prior.json"}[name]
                with (fix.work / filename).open("ab") as stream:
                    stream.write(b" ")
            (fix.work / "continue").touch()
            output, error = process.communicate(timeout=10)
            assert process.returncode == 2 and not output, (output, error)
            if name == "destination":
                assert list(fix.output.iterdir()) == [fix.output / "keep"]
                assert (fix.output / "keep").read_bytes() == b"another writer"
            else:
                assert "input changed before publication" in error and not fix.output.exists()
            assert not list(fix.work.glob(".lru-cache-*"))
        finally:
            if process.poll() is None:
                process.kill()
                process.communicate(timeout=5)
    fix = fixture(directory, "killed", sample())
    process = paused(app, fix)
    process.kill()
    process.communicate(timeout=5)
    assert not fix.output.exists()
    abandoned = list(fix.work.glob(".lru-cache-*"))
    assert len(abandoned) == 1
    contents = {path.name: path.read_bytes() for path in abandoned[0].iterdir()}
    result = app.run(fix.work, fix.settings())
    assert result.returncode == 0
    outputs(fix, oracle(fix))
    assert {path.name: path.read_bytes() for path in abandoned[0].iterdir()} == contents
    for name in ["file", "directory", "symlink", "dangling", "same-trace", "same-config"]:
        fix = fixture(directory, "existing-" + name, [])
        if name == "file":
            fix.output.write_bytes(b"keep")
        elif name == "directory":
            fix.output.mkdir()
        elif name in ["symlink", "dangling"]:
            fix.output.symlink_to(fix.work / ("trace.json" if name == "symlink" else "absent"))
        else:
            fix.config["output"] = "trace.json" if name == "same-trace" else "cache-job.json"
            fix.save()
        failure(app, fix, "output directory already exists")
    for name in ["trace.json", "cache-job.json", "prior.json"]:
        fix = fixture(directory, "link-" + name, [], prior=envelope(fresh(2)))
        path = fix.work / name
        original = path.with_suffix(".original")
        path.rename(original)
        path.symlink_to(original)
        failure(app, fix, "input must be a regular file")
    return len(points) + 4 + 1 + 6 + 3
