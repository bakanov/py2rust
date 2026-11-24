# ruff: noqa: PLR1711 - repository functions use explicit returns
"""Independent arbitrary-precision bitset model for persisted Bloom filters and exact audits."""

from __future__ import annotations

import copy
import hashlib
import json
import math
import random
import selectors
import struct
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .common import Application
from .csv_json import canonical


def command(operation: str, key: str) -> dict:
    return {"op": operation, "key": key}


def sample() -> list:
    return [command("INGEST", key) for key in ["", "hello", "世界", "hello", "café", "cafe\u0301", "\x00"]] + [
        command("CHECK", "hello"),
        command("CHECK", "absent"),
        {"op": "EXPORT"},
        {"op": "INSPECT"},
    ]


def sizing(expected: int, ppm: int) -> tuple[int, int]:
    bits = math.ceil(expected * (-math.log(ppm / 1_000_000) / math.log(2) ** 2))
    return bits, max(1, math.floor(bits / expected * math.log(2) + 0.5))


def mask(key: str, bits: int, hashes: int) -> int:
    result = 0
    for counter in range(hashes):
        payload = b"py2rust-bloom-v1\0" + struct.pack(">H", counter) + key.encode()
        position = int.from_bytes(hashlib.sha256(payload).digest()[:7], "big") % bits
        result |= 1 << position
    return result


def envelope(state: dict) -> dict:
    return {"state": state, "sha256": hashlib.sha256(canonical(state).encode()).hexdigest()}


def fresh(expected: int = 8, probability_ppm: int = 10000, capacity: int = 32) -> dict:
    bits, hashes = sizing(expected, probability_ppm)
    return {
        "version": 1,
        "expected": expected,
        "probability_ppm": probability_ppm,
        "capacity": capacity,
        "bit_count": bits,
        "hashes": hashes,
        "bits_hex": bytes((bits + 7) // 8).hex(),
        "keys": [],
        "steps": 0,
        "counts": dict.fromkeys(
            ["tests", "absent_tests", "false_positives", "ingests", "accepted", "duplicates", "refused"], 0
        ),
    }


def with_keys(keys: list[str], expected: int = 8, probability_ppm: int = 10000, capacity: int = 32) -> dict:
    state = fresh(expected, probability_ppm, capacity)
    state["keys"] = sorted(keys)
    value = 0
    for key in keys:
        value |= mask(key, state["bit_count"], state["hashes"])
    state["bits_hex"] = value.to_bytes((state["bit_count"] + 7) // 8, "little").hex()
    state["steps"] = len(keys)
    # Reconstruct the actual historical measurements of inserting these keys.
    value = 0
    for key in keys:
        selected = mask(key, state["bit_count"], state["hashes"])
        state["counts"]["false_positives"] += value & selected == selected
        value |= selected
    for name in ["tests", "absent_tests", "ingests", "accepted"]:
        state["counts"][name] = len(keys)
    return envelope(state)


def oracle(fix: Fixture) -> tuple[dict, list, dict]:
    state = fresh(fix.config["expected"], fix.config["probability_ppm"], fix.config["capacity"])
    if fix.config["state"]:
        state = json.loads((fix.work / fix.config["state"]).read_bytes())["state"]
    before = state["steps"]
    keys = set(state["keys"])
    word = int.from_bytes(bytes.fromhex(state["bits_hex"]), "little")
    counters = state["counts"]
    events = []

    def summary() -> dict:
        return {
            "expected": state["expected"],
            "target_probability_ppm": state["probability_ppm"],
            "capacity": state["capacity"],
            "keys": len(keys),
            "bit_count": state["bit_count"],
            "hashes": state["hashes"],
            "filter_bytes": (state["bit_count"] + 7) // 8,
            "occupied_bits": word.bit_count(),
            "audit_key_utf8_bytes": sum(len(key.encode()) for key in keys),
            "counts": copy.deepcopy(counters),
            "measured_false_positive_ppm": (
                counters["false_positives"] * 1_000_000 // counters["absent_tests"]
                if counters["absent_tests"]
                else None
            ),
        }

    trace = json.loads((fix.work / fix.config["trace"]).read_bytes())
    for instruction in trace:
        state["steps"] += 1
        operation = instruction["op"]
        event = {"step": state["steps"], "op": operation}
        if operation == "INSPECT":
            event["filter"] = summary()
        elif operation == "EXPORT":
            event["keys"] = sorted(keys)
        else:
            assert operation in ["INGEST", "CHECK"]
            key = instruction["key"]
            selected = mask(key, state["bit_count"], state["hashes"])
            probable, present = word & selected == selected, key in keys
            assert not present or probable
            counters["tests"] += 1
            if not present:
                counters["absent_tests"] += 1
                counters["false_positives"] += probable
            event.update(
                key=key, likely_duplicate=probable, exact_duplicate=present, false_positive=probable and not present
            )
            if operation == "INGEST":
                counters["ingests"] += 1
                decision = "duplicate" if present else ("accepted" if len(keys) < state["capacity"] else "refused")
                counters["duplicates" if present else decision] += 1
                event["decision"] = decision
                if decision == "accepted":
                    word |= selected
                    keys.add(key)
        events.append(event)
    state.update(keys=sorted(keys), bits_hex=word.to_bytes((state["bit_count"] + 7) // 8, "little").hex())
    report = {"before_steps": before, "after_steps": state["steps"], "commands": len(trace), "filter": summary()}
    return envelope(state), events, report


@dataclass
class Fixture:
    work: Path
    config: dict

    @property
    def path(self) -> Path:
        return self.work / "bloom-job.json"

    @property
    def output(self) -> Path:
        value = self.config.get("output", "bloom-run")
        return self.work / (value if isinstance(value, str) and "\x00" not in value else "bloom-run")

    def save(self) -> None:
        self.path.write_text(json.dumps(self.config, ensure_ascii=False))
        return

    def settings(self, mode: str = "write", **extra: str) -> dict:
        return {
            "BLOOM_CONFIG": str(self.path),
            "BLOOM_MODE": mode,
            "BLOOM_FAIL": "",
            "BLOOM_PAUSE": "",
            "BLOOM_CONTINUE": "",
            **extra,
        }


def fixture(directory: Path, name: str, commands: list, prior: dict | None = None, **changes: object) -> Fixture:
    work = directory / name
    work.mkdir(parents=True)
    (work / "trace.json").write_text(json.dumps(commands, ensure_ascii=False))
    config = {
        "trace": "trace.json",
        "state": "",
        "expected": 8,
        "probability_ppm": 10000,
        "capacity": 32,
        "output": "bloom-run",
        **changes,
    }
    if prior is not None:
        (work / "prior.json").write_text(canonical(prior))
        config["state"] = "prior.json"
    result = Fixture(work, config)
    result.save()
    return result


def outputs(fix: Fixture, expected: tuple[dict, list, dict]) -> None:
    saved, events, report = expected
    assert sorted(path.name for path in fix.output.iterdir()) == [
        "events.jsonl",
        "filter.bin",
        "keys.json",
        "report.json",
        "state.json",
    ]
    assert (fix.output / "state.json").read_bytes() == (canonical(saved) + "\n").encode()
    assert (fix.output / "filter.bin").read_bytes() == bytes.fromhex(saved["state"]["bits_hex"])
    assert (fix.output / "keys.json").read_bytes() == (canonical(saved["state"]["keys"]) + "\n").encode()
    assert (fix.output / "events.jsonl").read_bytes() == "".join(canonical(event) + "\n" for event in events).encode()
    assert json.loads((fix.output / "report.json").read_bytes()) == report
    return


def success(app: Application, fix: Fixture, mode: str = "write") -> tuple[dict, list, dict]:
    expected = oracle(fix)
    inputs = [fix.path, fix.work / fix.config["trace"]]
    if fix.config["state"]:
        inputs.append(fix.work / fix.config["state"])
    before = [path.read_bytes() for path in inputs]
    result = app.run(fix.work, fix.settings(mode), timeout=90)
    assert result.returncode == 0 and not result.stderr, (result, fix.config)
    assert json.loads(result.stdout) == expected[2], (result.stdout, expected[2])
    assert [path.read_bytes() for path in inputs] == before
    if mode == "write":
        outputs(fix, expected)
        assert (fix.output / "report.json").read_text() == result.stdout
    else:
        assert not fix.output.exists()
    assert not list(fix.work.glob(".bloom-*"))
    return expected


def failure(app: Application, fix: Fixture, message: str = "", **extra: str) -> None:
    existed = fix.output.exists() or fix.output.is_symlink()
    original = fix.output.read_bytes() if fix.output.is_file() else None
    result = app.run(fix.work, fix.settings(**extra), timeout=90)
    assert result.returncode == 2 and result.stderr and message in result.stderr and not result.stdout, (
        result,
        message,
    )
    assert (fix.output.exists() or fix.output.is_symlink()) == existed
    if original is not None:
        assert fix.output.read_bytes() == original
    assert not list(fix.work.glob(".bloom-*"))
    return


def invalid_inputs(app: Application, directory: Path) -> int:
    bad = [None, [], {}, {"op": "ingest"}, {"op": 1}, {"op": "UNKNOWN"}]
    for valid in [command("INGEST", "x"), command("CHECK", "x"), {"op": "INSPECT"}, {"op": "EXPORT"}]:
        bad.append({**valid, "extra": True})
        bad += [{key: value for key, value in valid.items() if key != field} for field in valid]
    for value in [None, True, 1, {}, [], "x" * 129, "😀" * 129]:
        bad += [command("INGEST", value), command("CHECK", value)]
    count = 0
    for item in bad:
        failure(app, fixture(directory, f"command-{count}", [command("INGEST", "valid"), item]), "command 2:")
        count += 1
    for field, values in {
        "expected": [0, 4097, -1, True, 1.0, "1"],
        "capacity": [0, 4097, -1, None, 1.0],
        "probability_ppm": [0, 1000000, -1, False, 1.0],
        "state": [None, 1],
        "trace": ["", "\x00", None],
        "output": ["", "\x00", None],
    }.items():
        for value in values:
            failure(app, fixture(directory, f"config-{count}", [], **{field: value}))
            count += 1
    base = fixture(directory, "base", []).config
    for field in base:
        fix = fixture(directory, f"missing-{field}", [])
        del fix.config[field]
        fix.save()
        failure(app, fix, "unexpected object fields")
        count += 1
    for value in ["[]", "null", "{", '{"trace":1,"trace":2}']:
        fix = fixture(directory, f"config-root-{count}", [])
        fix.path.write_text(value)
        failure(app, fix)
        count += 1
    for value in ["{}", "null", "{"]:
        fix = fixture(directory, f"trace-root-{count}", [])
        (fix.work / "trace.json").write_text(value)
        failure(app, fix)
        count += 1
    failure(app, fixture(directory, "mode", []), "invalid Bloom mode", BLOOM_MODE="unknown")
    return count + 1


def invalid_states(app: Application, directory: Path) -> int:
    original = with_keys(["", "hello", "世界"])
    bad = []
    for name in original["state"]:
        item = copy.deepcopy(original["state"])
        del item[name]
        bad.append(envelope(item))
    changes = [
        ("version", 2),
        ("version", True),
        ("expected", 9),
        ("probability_ppm", 10001),
        ("capacity", 33),
        ("bit_count", 1),
        ("hashes", 0),
        ("bits_hex", ""),
        ("bits_hex", original["state"]["bits_hex"].upper()),
        ("keys", ["", "世界", "hello"]),
        ("keys", ["", "", "hello"]),
        ("keys", [1]),
        ("keys", ["x" * 129]),
        ("steps", -1),
        ("steps", 1000000001),
        ("steps", 1),
        ("steps", 3.0),
    ]
    for name, value in changes:
        item = copy.deepcopy(original["state"])
        item[name] = value
        bad.append(envelope(item))
    for name, value in [
        ("tests", 2),
        ("absent_tests", 2),
        ("false_positives", 4),
        ("ingests", 2),
        ("accepted", 2),
        ("duplicates", 1),
        ("refused", 1),
        ("tests", True),
        ("tests", -1),
        ("tests", 1000000001),
    ]:
        item = copy.deepcopy(original["state"])
        item["counts"][name] = value
        bad.append(envelope(item))
    for name in original["state"]["counts"]:
        item = copy.deepcopy(original["state"])
        del item["counts"][name]
        bad.append(envelope(item))
    tampered = copy.deepcopy(original)
    tampered["state"]["steps"] += 1
    bad += [tampered, {**original, "extra": 1}, {"state": original["state"]}, {"sha256": original["sha256"]}]
    padding = copy.deepcopy(original["state"])
    data = bytearray.fromhex(padding["bits_hex"])
    data[-1] |= 128
    padding["bits_hex"] = data.hex()
    bad.append(envelope(padding))
    for index, item in enumerate(bad):
        failure(app, fixture(directory, f"bad-{index}", [], prior=item))
    return len(bad)


def limits(app: Application, directory: Path) -> int:
    success(app, fixture(directory, "key-length", [command("INGEST", "😀" * 128), command("CHECK", "😀" * 128)]))
    success(app, fixture(directory, "trace-length", [{"op": "INSPECT"}] * 2000))
    failure(app, fixture(directory, "trace-long", [{"op": "INSPECT"}] * 2001), "trace exceeds 2000")
    for name, filename, limit in [
        ("config", "bloom-job.json", 65536),
        ("trace", "trace.json", 4194304),
        ("state", "prior.json", 8388608),
    ]:
        for excess in [0, 1]:
            fix = fixture(directory, f"bytes-{name}-{excess}", [], prior=envelope(fresh()))
            path = fix.work / filename
            original = path.read_bytes()
            with path.open("ab") as stream:
                stream.write(b" " * (limit + excess - len(original)))
            if excess:
                failure(app, fix, "input byte limit exceeded")
            else:
                success(app, fix)
    for ppm in [1, 1000, 500000, 999999]:
        success(app, fixture(directory, f"sizing-{ppm}", sample(), expected=4096, probability_ppm=ppm, capacity=4096))
    terminal = fresh()
    terminal["steps"] = 1000000000
    success(app, fixture(directory, "last-step-empty", [], prior=envelope(terminal)))
    failure(app, fixture(directory, "last-step", [{"op": "INSPECT"}], prior=envelope(terminal)), "step limit")
    keys = [f"{number:04}" + "😀" * 124 for number in range(4096)]
    full = with_keys(keys, 4096, 10000, 4096)
    fix = fixture(
        directory,
        "full",
        [command("INGEST", keys[0]), command("INGEST", "overflow"), command("CHECK", keys[-1])],
        prior=full,
        expected=4096,
        capacity=4096,
    )
    result = success(app, fix)
    assert result[1][0]["decision"] == "duplicate" and result[1][1]["decision"] == "refused"
    # Large EXPORT responses must not publish a truncated bundle.
    failure(
        app,
        fixture(directory, "events-long", [{"op": "EXPORT"}] * 12, prior=full, expected=4096, capacity=4096),
        "events exceed 16 MiB",
    )
    overflowing = copy.deepcopy(full["state"])
    overflowing["capacity"] = 4095
    failure(
        app,
        fixture(directory, "audit-capacity", [], prior=envelope(overflowing), expected=4096, capacity=4095),
        "saved keys exceed capacity",
    )
    return 18


def check(app: Application, directory: Path) -> dict:
    assert sizing(8, 10000) == (77, 7) and sizing(1, 999999) == (1, 1)
    observations = []
    traces = [
        [],
        sample(),
        [command("CHECK", "absent"), {"op": "INSPECT"}],
        [command("INGEST", key) for key in ["a", "b", "c", "d", "a"]] + [command("CHECK", "a"), command("CHECK", "z")],
    ]
    rng = random.Random(5602026)
    for _ in range(32):
        pool = [""] + [
            f'key-{rng.randrange(64)}-{rng.choice(["😀", "世界", "ß", "café", "café", chr(0)])}' for _ in range(40)
        ]
        trace = [command(rng.choice(["INGEST", "INGEST", "CHECK"]), rng.choice(pool)) for _ in range(96)]
        trace += [command("CHECK", key) for key in pool] + [{"op": "EXPORT"}, {"op": "INSPECT"}]
        traces.append(trace)
    for number, trace in enumerate(traces):
        ppm = [999999, 500000, 10000, 1][number % 4]
        expected, capacity = (1, 3) if number == 3 else (8, 32)
        if number == 3:
            ppm = 999999
        fix = fixture(directory, f"trace-{number}", trace, expected=expected, capacity=capacity, probability_ppm=ppm)
        outcome = success(app, fix)
        observations.append(outcome)
        if number == 3:
            assert [event.get("decision") for event in outcome[1][:5]] == [
                "accepted",
                "accepted",
                "accepted",
                "refused",
                "duplicate",
            ]
            assert outcome[2]["filter"]["counts"]["false_positives"] == 4
        if number < 12:
            split = len(trace) // 2
            initial = fixture(
                directory, f"split-{number}-a", trace[:split], expected=expected, capacity=capacity, probability_ppm=ppm
            )
            success(app, initial)
            resumed = fixture(
                directory,
                f"split-{number}-b",
                trace[split:],
                expected=expected,
                capacity=capacity,
                probability_ppm=ppm,
                state=str(initial.output / "state.json"),
            )
            after = success(app, resumed)
            assert after[0] == outcome[0]
            assert (initial.output / "events.jsonl").read_bytes() + (resumed.output / "events.jsonl").read_bytes() == (
                fix.output / "events.jsonl"
            ).read_bytes()
    preview = fixture(directory, "preview", sample())
    success(app, preview, "preview")
    success(app, preview)
    return {
        "traces": len(traces),
        "generated_traces": 32,
        "restart_splits": 12,
        "invalid_inputs": invalid_inputs(app, directory / "invalid"),
        "invalid_states": invalid_states(app, directory / "states"),
        "limits": limits(app, directory / "limits"),
        "publication": publication(app, directory / "publication"),
        "results_sha256": hashlib.sha256(canonical(observations).encode()).hexdigest(),
    }


def paused(app: Application, fix: Fixture) -> subprocess.Popen:
    signal = fix.work / "continue"
    process = subprocess.Popen(
        app.command,
        cwd=fix.work,
        env=app.environment(fix.settings(BLOOM_PAUSE="ready", BLOOM_CONTINUE=str(signal))),
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
        "filter.bin",
        "keys.json",
        "events.jsonl",
        "report.json",
        "ready",
        "published",
    ]
    for point in points:
        fix = fixture(directory, "fault-" + point, sample())
        result = app.run(fix.work, fix.settings(BLOOM_FAIL=point))
        assert result.returncode == 2 and "injected failure: " + point in result.stderr and not result.stdout
        assert not list(fix.work.glob(".bloom-*"))
        if point == "published":
            outputs(fix, oracle(fix))
        else:
            assert not fix.output.exists()
            success(app, fix)
    for name in ["trace", "configuration", "state", "destination"]:
        fix = fixture(directory, "changed-" + name, sample(), prior=envelope(fresh()))
        process = paused(app, fix)
        try:
            if name == "destination":
                fix.output.mkdir()
                (fix.output / "keep").write_bytes(b"another writer")
            else:
                filename = {"trace": "trace.json", "configuration": "bloom-job.json", "state": "prior.json"}[name]
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
            assert not list(fix.work.glob(".bloom-*"))
        finally:
            if process.poll() is None:
                process.kill()
                process.communicate(timeout=5)
    fix = fixture(directory, "killed", sample())
    process = paused(app, fix)
    process.kill()
    process.communicate(timeout=5)
    assert not fix.output.exists()
    abandoned = list(fix.work.glob(".bloom-*"))
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
            fix.config["output"] = "trace.json" if name == "same-trace" else "bloom-job.json"
            fix.save()
        failure(app, fix, "output directory already exists")
    for name in ["trace.json", "bloom-job.json", "prior.json"]:
        fix = fixture(directory, "link-" + name, [], prior=envelope(fresh()))
        path = fix.work / name
        original = path.with_suffix(".original")
        path.rename(original)
        path.symlink_to(original)
        failure(app, fix, "input must be a regular file")
    return len(points) + 4 + 1 + 6 + 3
