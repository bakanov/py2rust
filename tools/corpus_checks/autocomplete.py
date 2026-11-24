# ruff: noqa: PLR1711 - repository functions use explicit returns
"""A flat dictionary and prefix scan independently verify the recursive autocomplete trie."""

from __future__ import annotations

import copy
import hashlib
import json
import os
import random
import selectors
import subprocess
import unicodedata
from dataclasses import dataclass
from pathlib import Path

from .common import Application
from .csv_json import canonical


def normalized(term: str) -> str:
    return unicodedata.normalize("NFKC", term).casefold()


def put(term: str, uses: int = 0) -> dict:
    return {"op": "PUT", "term": term, "uses": uses}


def suggest(prefix: str, offset: int = 0, limit: int = 128) -> dict:
    return {"op": "SUGGEST", "prefix": prefix, "offset": offset, "limit": limit}


def envelope(state: dict) -> dict:
    return {"state": state, "sha256": hashlib.sha256(canonical(state).encode()).hexdigest()}


def fresh(capacity: int) -> dict:
    return {"version": 1, "capacity": capacity, "steps": 0, "entries": [], "nodes": 1}


def nodes(records: dict) -> int:
    return len({key[:length] for key in records for length in range(1, len(key) + 1)}) + 1


def oracle(fix: Fixture) -> tuple[dict, list, dict]:
    state = fresh(fix.config["capacity"])
    if fix.config["state"]:
        state = json.loads((fix.work / fix.config["state"]).read_bytes())["state"]
    records = {value["key"]: copy.deepcopy(value) for value in state["entries"]}
    before, steps = state["steps"], state["steps"]
    events = []
    trace = json.loads((fix.work / fix.config["trace"]).read_bytes())

    def entries() -> list:
        return [records[key] for key in sorted(records)]

    def summary() -> dict:
        return {"terms": len(records), "nodes": nodes(records), "capacity": state["capacity"]}

    for instruction in trace:
        steps += 1
        operation = instruction["op"]
        event = {"step": steps, "op": operation}
        if operation in {"PUT", "HIT", "GET", "DELETE"}:
            key = normalized(instruction["term"])
            event.update(key=key, found=key in records)
            if operation == "PUT":
                accepted = key in records or len(records) < state["capacity"]
                event["accepted"] = accepted
                if accepted:
                    records[key] = {"key": key, "term": instruction["term"], "uses": instruction["uses"]}
                    event["entry"] = records[key]
                else:
                    event["reason"] = "capacity"
            elif operation == "HIT":
                if key in records:
                    records[key]["uses"] += instruction["amount"]
                    event["entry"] = records[key]
            elif operation == "GET":
                event["entry"] = records.get(key)
            else:
                records.pop(key, None)
        elif operation == "SUGGEST":
            prefix = normalized(instruction["prefix"])
            matches = sorted(
                [value for key, value in records.items() if key.startswith(prefix)],
                key=lambda value: (-value["uses"], value["key"]),
            )
            start, stop = instruction["offset"], instruction["offset"] + instruction["limit"]
            event["result"] = {
                "prefix": prefix,
                "hits": matches[start:stop],
                "count": len(matches),
                "more": stop < len(matches),
            }
        elif operation == "EXPORT":
            event["entries"] = entries()
        else:
            assert operation == "INSPECT"
            event["index"] = summary()
        events.append(copy.deepcopy(event))
    saved = {"version": 1, "capacity": state["capacity"], "steps": steps, "entries": entries(), "nodes": nodes(records)}
    report = {"before_steps": before, "after_steps": steps, "commands": len(trace), "index": summary()}
    return envelope(saved), events, report


def sample() -> list:
    return [
        put("car", 2),
        put("cart", 2),
        put("cat", 4),
        suggest("ca"),
        {"op": "HIT", "term": "CAR", "amount": 3},
        suggest("CA", 0, 1),
        {"op": "DELETE", "term": "car"},
        suggest("car"),
        {"op": "GET", "term": "cart"},
        {"op": "DELETE", "term": "cart"},
        put("Straße", 1),
        put("STRASSE", 6),
        {"op": "HIT", "term": "straße", "amount": 2},
        suggest("strass"),
        put("cafe\u0301", 8),
        suggest("", 1, 2),
        {"op": "EXPORT"},
        {"op": "DELETE", "term": "cat"},
        {"op": "DELETE", "term": "cat"},
        {"op": "GET", "term": "CAT"},
        {"op": "HIT", "term": "missing", "amount": 1},
        {"op": "INSPECT"},
    ]


def invalid_commands(app: Application, directory: Path) -> int:
    bad = [None, [], {}, {"op": "put"}, {"op": 1}, {"op": "UNKNOWN"}]
    valid = [
        put("a"),
        suggest("a"),
        {"op": "HIT", "term": "a", "amount": 1},
        {"op": "GET", "term": "a"},
        {"op": "DELETE", "term": "a"},
        {"op": "EXPORT"},
        {"op": "INSPECT"},
    ]
    for instruction in valid:
        bad.append({**instruction, "extra": True})
        for field in instruction:
            bad.append({key: value for key, value in instruction.items() if key != field})
    for value in [None, True, 1, "", "😀" * 129, "x" * 129, "ß" * 65]:
        bad += [put(value), {"op": "GET", "term": value}, {"op": "DELETE", "term": value}]
    for value in [None, True, "1", -1, 1000000001, 1.0]:
        bad.append(put("a", value))
    for value in [None, True, "1", 0, -1, 1000001, 1.0]:
        bad.append({"op": "HIT", "term": "missing", "amount": value})
    for value in [None, False, 1, "x" * 129, "ß" * 65]:
        bad.append(suggest(value))
    for field, values in {"offset": [-1, 129, True, 1.0, None], "limit": [0, 129, True, 1.0, None]}.items():
        for value in values:
            bad.append({**suggest("a"), field: value})
    for index, instruction in enumerate(bad):
        failure(app, fixture(directory, f"invalid-command-{index}", [put("ok"), instruction]), "command 2:")
    settings = [
        {field: value}
        for field, values in {
            "capacity": [0, 129, True, "3"],
            "state": [None],
            "trace": ["", "\x00"],
            "output": [""],
        }.items()
        for value in values
    ] + [{"extra": 1}]
    for index, changes in enumerate(settings):
        fix = fixture(directory, f"invalid-config-{index}", [])
        fix.config.update(changes)
        fix.save()
        failure(app, fix, "")
    for index, content in enumerate([b"{", b"\xff", b"null", b"{}", b"[NaN]"]):
        fix = fixture(directory, f"invalid-trace-{index}", [])
        (fix.work / "trace.json").write_bytes(content)
        failure(app, fix, "")
    return len(bad) + len(settings) + 5


def states(app: Application, directory: Path) -> int:
    origin = fixture(directory, "state-origin", sample()[:6])
    state = success(app, origin)[0]["state"]
    mutations = []
    for field, value in [
        ("version", 2),
        ("version", True),
        ("capacity", 0),
        ("capacity", 4),
        ("steps", -1),
        ("steps", True),
        ("steps", 1000000001),
        ("entries", None),
        ("entries", state["entries"][:2]),
        ("nodes", 0),
        ("nodes", True),
    ]:
        mutations.append({**copy.deepcopy(state), field: value})
    for field, value in [
        ("term", ""),
        ("term", "x" * 129),
        ("term", "different"),
        ("key", "CAR"),
        ("key", 1),
        ("uses", -1),
        ("uses", 1000000001),
        ("uses", True),
        ("uses", 1.0),
    ]:
        changed = copy.deepcopy(state)
        changed["entries"][0][field] = value
        mutations.append(changed)
    for name in ["state", "entry"]:
        for action in ["missing", "extra"]:
            changed = copy.deepcopy(state)
            target = changed if name == "state" else changed["entries"][0]
            if action == "missing":
                del target[next(iter(target))]
            else:
                target["extra"] = None
            mutations.append(changed)
    changed = copy.deepcopy(state)
    changed["entries"][0] = copy.deepcopy(changed["entries"][1])
    mutations.append(changed)
    changed = copy.deepcopy(state)
    changed["entries"].append({"key": "new", "term": "new", "uses": 0})
    changed["nodes"] = nodes({entry["key"]: entry for entry in changed["entries"]})
    mutations.append(changed)
    for index, value in enumerate(mutations):
        failure(app, fixture(directory, f"bad-state-{index}", [], prior=envelope(value)), "")
    raw = [None, [], {}, {"state": state, "sha256": "invalid"}, {"state": state, "sha256": 1}]
    for index, value in enumerate(raw):
        bad = fixture(directory, f"bad-envelope-{index}", [], prior=value)
        if value is None:
            bad.config["state"] = "prior.json"
            bad.save()
            (bad.work / "prior.json").write_text("null")
        failure(app, bad, "")
    permuted = copy.deepcopy(state)
    permuted["entries"].reverse()
    resumed = fixture(directory, "shuffled-state", sample()[6:], prior=envelope(permuted))
    whole = fixture(directory, "state-whole", sample())
    assert canonical(success(app, resumed)[0]) == canonical(success(app, whole)[0])
    return len(mutations) + len(raw) + 1


def limits(app: Application, directory: Path) -> int:
    checks = 0
    for size in [1, 128]:
        trace = [put(str(index), 1) for index in range(size)]
        trace += [
            put("overflow"),
            put("0", 2),
            suggest("", 0, 1),
            {"op": "DELETE", "term": "0"},
            put("overflow"),
            {"op": "INSPECT"},
        ]
        result = success(app, fixture(directory, f"full-{size}", trace, size))
        assert result[1][size]["reason"] == "capacity"
        assert result[1][size + 1]["accepted"] and result[1][size + 1]["found"]
        assert result[1][-2]["accepted"]
        checks += 1
    success(app, fixture(directory, "trace-max", [{"op": "INSPECT"}] * 2000))
    failure(app, fixture(directory, "trace-too-many", [{"op": "INSPECT"}] * 2001), "2000 commands")
    checks += 2
    for name, target, size in [
        ("config", "autocomplete-job.json", 65537),
        ("trace", "trace.json", 4194305),
        ("state", "prior.json", 8388609),
    ]:
        fix = fixture(directory, "bytes-" + name, [], prior=envelope(fresh(3)))
        with (fix.work / target).open("wb") as stream:
            stream.truncate(size)
        failure(app, fix, "input byte limit")
        checks += 1
    success(
        app,
        fixture(
            directory,
            "exact-text-bounds",
            [
                put("😀" * 128),
                suggest("😀" * 128),
                put("ß" * 64),
                suggest("s" * 128, 128, 128),
                put("x", 999000000),
                {"op": "HIT", "term": "x", "amount": 1000000},
                suggest(""),
            ],
        ),
    )
    failure(
        app,
        fixture(directory, "counter-overflow", [put("x", 1000000000), {"op": "HIT", "term": "x", "amount": 1}]),
        "usage must",
    )
    checks += 2
    # Sixty-three disjoint paths of 128 nodes, then one of 127: root + paths = 8192.
    terms = [chr(0x4E00 + index) + "x" * 127 for index in range(63)] + [chr(0x4E3F) + "x" * 126]
    trace = [put(term, index) for index, term in enumerate(terms)]
    result = success(app, fixture(directory, "node-limit", trace + [suggest(terms[-1])], 128))
    assert result[2]["index"]["nodes"] == 8192
    failure(app, fixture(directory, "node-overflow", trace + [put("new")], 128), "8192 nodes")
    success(app, fixture(directory, "prune-at-limit", trace + [{"op": "DELETE", "term": terms[0]}, put("new")], 128))
    checks += 3
    # Heavy exports exceed the event budget even though the input fits comfortably.
    trace = [put("😀" * 125 + f"{index:03d}") for index in range(128)] + [{"op": "EXPORT"}] * 150
    failure(app, fixture(directory, "events-too-big", trace, 128), "events exceed 16 MiB")
    checks += 1
    capped = fresh(3)
    capped["steps"] = 1000000000
    success(app, fixture(directory, "lifetime-at-limit", [], prior=envelope(capped)))
    failure(
        app,
        fixture(directory, "lifetime-overflow", [{"op": "INSPECT"}], prior=envelope(capped)),
        "lifetime command limit",
    )
    checks += 2
    fix = fixture(directory, "permission", sample())
    assert os.geteuid() != 0, "permission check needs a non-root user"
    fix.work.chmod(0o555)
    try:
        failure(app, fix, "")
    finally:
        fix.work.chmod(0o755)
    return checks + 1


def check(app: Application, directory: Path) -> dict:
    cases = [(1, []), (3, []), (1, sample()), (3, sample()), (8, sample())]
    unicode_trace = [
        put("Straße", 3),
        put("STRASSE", 7),
        put("cafe\u0301", 7),
        put("Σςσ", 1),
        put("İIı", 1),
        put("ﬃle", 2),
        put("ＨＴＴＰ", 2),
        put("世界😀", 2),
    ]
    unicode_trace += [
        suggest(value) for value in ["", "s", "STRASS", "café", "CAF", "Σ", "i̇", "ffi", "http", "世界", "absent"]
    ]
    unicode_trace += [{"op": "GET", "term": "straße"}, {"op": "DELETE", "term": "STRASSE"}, suggest("str")]
    cases.append((8, unicode_trace))
    for operation_order in [list(range(8)), list(reversed(range(8)))]:
        terms = ["a", "ab", "abc", "abd", "ac", "b", "ba", "a\x00b"]
        trace = [put(term) for term in terms]
        trace += [
            item
            for index in operation_order
            for item in [{"op": "DELETE", "term": terms[index]}, suggest(""), {"op": "INSPECT"}]
        ]
        cases.append((8, trace))
    churn = [item for _ in range(100) for item in [put("reuse", 1), put("REUSE", 2), {"op": "DELETE", "term": "reuse"}]]
    cases.append((1, churn + [{"op": "INSPECT"}]))
    rng = random.Random(550055)
    vocabulary = [
        "a",
        "ab",
        "abc",
        "ac",
        "b",
        "ba",
        "a\x00b",
        "Straße",
        "STRASSE",
        "café",
        "cafe\u0301",
        "Σςσ",
        "世界",
        "😀",
    ]
    for _ in range(32):
        trace = []
        for _index in range(160):
            operation = rng.choice(["PUT"] * 3 + ["SUGGEST"] * 5 + ["DELETE", "GET", "HIT", "EXPORT", "INSPECT"])
            term = rng.choice(vocabulary)
            if operation == "PUT":
                trace.append(put(term, rng.randrange(20)))
            elif operation == "SUGGEST":
                prefix = term[: rng.randrange(len(term) + 1)]
                trace.append(suggest(prefix, rng.randrange(5), rng.randrange(1, 5)))
            elif operation == "HIT":
                trace.append({"op": operation, "term": term, "amount": rng.randrange(1, 11)})
            else:
                trace.append({"op": operation, **({"term": term} if operation in {"GET", "DELETE"} else {})})
        cases.append((rng.randrange(1, 10), trace))
    observations = []
    for index, (size, trace) in enumerate(cases):
        fix = fixture(directory, f"trace-{index}", trace, size)
        success(app, fix, "preview")
        observations.append(success(app, fix))
        resumed = fixture(directory, f"unchanged-{index}", [], size, state=str(fix.output / "state.json"))
        success(app, resumed)
        assert (resumed.output / "state.json").read_bytes() == (fix.output / "state.json").read_bytes()
    whole = fixture(directory, "whole", sample())
    complete = success(app, whole)
    for split in range(len(sample()) + 1):
        prefix = fixture(directory, f"prefix-{split}", sample()[:split])
        success(app, prefix)
        suffix = fixture(directory, f"suffix-{split}", sample()[split:], state=str(prefix.output / "state.json"))
        assert canonical(success(app, suffix)[0]) == canonical(complete[0])
        assert (prefix.output / "events.jsonl").read_bytes() + (suffix.output / "events.jsonl").read_bytes() == (
            whole.output / "events.jsonl"
        ).read_bytes()
        assert (suffix.output / "dictionary.json").read_bytes() == (whole.output / "dictionary.json").read_bytes()
    return {
        "traces": len(cases),
        "generated_traces": 32,
        "split_replays": len(sample()) + 1,
        "invalid_inputs": invalid_commands(app, directory),
        "state_checks": states(app, directory),
        "capacity_checks": limits(app, directory),
        "publication_checks": publication(app, directory),
        "results_sha256": hashlib.sha256(canonical(observations).encode()).hexdigest(),
    }


@dataclass
class Fixture:
    work: Path
    config: dict

    @property
    def path(self) -> Path:
        return self.work / "autocomplete-job.json"

    @property
    def output(self) -> Path:
        return self.work / self.config["output"]

    def save(self) -> None:
        self.path.write_text(json.dumps(self.config, ensure_ascii=False))
        return

    def settings(self, mode: str = "write", **extra: str) -> dict:
        return {
            "AUTOCOMPLETE_CONFIG": str(self.path),
            "AUTOCOMPLETE_MODE": mode,
            "AUTOCOMPLETE_FAIL": "",
            "AUTOCOMPLETE_PAUSE": "",
            "AUTOCOMPLETE_CONTINUE": "",
            **extra,
        }


def fixture(
    directory: Path, name: str, commands: list, capacity: int = 3, prior: dict | None = None, **changes: object
) -> Fixture:
    work = directory / name
    work.mkdir(parents=True)
    (work / "trace.json").write_text(json.dumps(commands, ensure_ascii=False))
    config = {"trace": "trace.json", "state": "", "capacity": capacity, "output": "autocomplete-run", **changes}
    if prior is not None:
        (work / "prior.json").write_text(canonical(prior))
        config["state"] = "prior.json"
    fix = Fixture(work, config)
    fix.save()
    return fix


def outputs(fix: Fixture, expected: tuple[dict, list, dict]) -> None:
    saved, events, report = expected
    assert (fix.output / "dictionary.json").read_text() == canonical(saved["state"]["entries"]) + "\n"
    assert sorted(path.name for path in fix.output.iterdir()) == [
        "dictionary.json",
        "events.jsonl",
        "report.json",
        "state.json",
    ]
    assert (fix.output / "state.json").read_text() == canonical(saved) + "\n"
    assert (fix.output / "events.jsonl").read_text() == "".join(canonical(event) + "\n" for event in events)
    assert canonical(json.loads((fix.output / "report.json").read_bytes())) == canonical(report)
    return


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
    assert not list(fix.work.glob(".autocomplete-*"))
    return expected


def failure(app: Application, fix: Fixture, message: str, **extra: str) -> None:
    existed = fix.output.exists() or fix.output.is_symlink()
    original = fix.output.read_bytes() if fix.output.is_file() else None
    result = app.run(fix.work, fix.settings(**extra), timeout=45)
    assert result.returncode == 2 and message in result.stderr and not result.stdout, (result, message, fix.config)
    assert (fix.output.exists() or fix.output.is_symlink()) == existed
    if original is not None:
        assert fix.output.read_bytes() == original
    assert not list(fix.work.glob(".autocomplete-*"))
    return


def paused(app: Application, fix: Fixture) -> subprocess.Popen:
    signal = fix.work / "continue"
    process = subprocess.Popen(
        app.command,
        cwd=fix.work,
        env=app.environment(fix.settings(AUTOCOMPLETE_PAUSE="ready", AUTOCOMPLETE_CONTINUE=str(signal))),
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
    points = [
        "validated",
        "stage",
        "state.json",
        "dictionary.json",
        "events.jsonl",
        "report.json",
        "ready",
        "published",
    ]
    for point in points:
        fix = fixture(directory, "fault-" + point, sample())
        result = app.run(fix.work, fix.settings(AUTOCOMPLETE_FAIL=point))
        assert result.returncode == 2 and "injected failure: " + point in result.stderr and not result.stdout
        assert not list(fix.work.glob(".autocomplete-*"))
        if point == "published":
            outputs(fix, oracle(fix))
        else:
            assert not fix.output.exists()
            success(app, fix)
    for name in ["trace", "configuration", "state", "destination"]:
        fix = fixture(directory, "changed-" + name, sample(), prior=envelope(fresh(3)))
        process = paused(app, fix)
        try:
            if name == "destination":
                fix.output.mkdir()
                (fix.output / "keep").write_bytes(b"another writer")
            else:
                filename = {"trace": "trace.json", "configuration": "autocomplete-job.json", "state": "prior.json"}[
                    name
                ]
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
            assert not list(fix.work.glob(".autocomplete-*"))
        finally:
            if process.poll() is None:
                process.kill()
                process.communicate(timeout=5)
    fix = fixture(directory, "killed", sample())
    process = paused(app, fix)
    process.kill()
    process.communicate(timeout=5)
    assert not fix.output.exists()
    abandoned = list(fix.work.glob(".autocomplete-*"))
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
            fix.config["output"] = "trace.json" if name == "same-trace" else "autocomplete-job.json"
            fix.save()
        failure(app, fix, "output directory already exists")
    for name in ["trace.json", "autocomplete-job.json", "prior.json"]:
        fix = fixture(directory, "link-" + name, [], prior=envelope(fresh(3)))
        path = fix.work / name
        original = path.with_suffix(".original")
        path.rename(original)
        path.symlink_to(original)
        failure(app, fix, "input must be a regular file")
    return len(points) + 4 + 1 + 6 + 3
