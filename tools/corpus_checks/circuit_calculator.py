"""Whole-application circuit checks: rational oracle, every reduction, errors, replay and publication recovery."""

from __future__ import annotations

import copy
import itertools
import json
import os
import random
import select
import subprocess
from pathlib import Path

from .circuit_fixture import (
    canonical,
    case,
    close,
    digest,
    fixtures,
    generated,
    group,
    inspect_result,
    resistor,
)
from .common import Application


def save(path: Path, value: object) -> None:
    path.write_bytes(canonical(value))
    return  # noqa: PLR1711


def files_at(path: Path) -> dict[str, bytes]:
    return {p.name: p.read_bytes() for p in path.iterdir() if p.is_file()}


def fixture(root: Path, rows: list | None = None) -> dict:
    root.mkdir(parents=True, exist_ok=True)
    config = {"version": 1, "mode": "solve", "input": "networks.json", "output": "output"}
    save(root / "circuit-job.json", config)
    save(root / "networks.json", {"version": 1, "cases": fixtures() if rows is None else rows})
    return config


def label(measure: dict) -> str:
    if measure["state"] == "open":
        return "open circuit"
    if measure["state"] == "short":
        return "short circuit (0 ohms)"
    return canonical(measure["ohms"]).decode().strip() + " ohms"


def inspect(root: Path, config: dict, reasons: dict[str, str] | None = None) -> dict:
    reasons = {} if reasons is None else reasons
    source = json.loads((root / config["input"]).read_bytes())
    directory = root / config["output"]
    raw = (directory / "archive.json").read_bytes()
    archive = json.loads(raw)
    assert archive.keys() == {"version", "cases", "results"} and type(archive["version"]) is int
    assert archive["version"] == 1 and canonical(archive["cases"]) == canonical(source["cases"])
    assert len(archive["cases"]) == len(archive["results"]) and raw == canonical(archive)
    counts = {"solved": 0, "rejected": 0, "finite": 0, "open": 0, "short": 0}
    lines = []
    for row, result in zip(archive["cases"], archive["results"]):
        name = row["id"]
        if name in reasons:
            assert result == {"id": name, "status": "rejected", "reason": reasons[name]}, result
            counts["rejected"] += 1
            lines.append(name + ": rejected: " + reasons[name])
        else:
            inspect_result(row, result)
            counts["solved"] += 1
            counts[result["equivalent"]["state"]] += 1
            lines.append(name + ": " + label(result["equivalent"]))
            for step in result["steps"]:
                lines.append(f'  {step["id"]} ({step["kind"]}): ' + label(step["equivalent"]) + "; " + step["rule"])
    report = {"version": 1, "mode": config["mode"], "summary": counts, "archive_sha256": digest(raw)}
    files = {
        "archive.json": raw,
        "networks.json": canonical({"version": 1, "cases": source["cases"]}),
        "report.json": canonical(report),
        "report.txt": (
            "\n".join(["Ideal DC series/parallel circuits", canonical(counts).decode().strip(), *lines]) + "\n"
        ).encode(),
        "replay.json": canonical({"version": 1, "mode": "verify", "input": "archive.json", "output": "replayed"}),
        "solve.json": canonical({"version": 1, "mode": "solve", "input": "networks.json", "output": "solved"}),
    }
    files["manifest.json"] = canonical(
        {name: {"bytes": len(data), "sha256": digest(data)} for name, data in files.items()}
    )
    assert files_at(directory) == files
    assert {p.name for p in directory.iterdir()} == set(files)
    if config["mode"] == "verify":
        assert canonical(source["results"]) == canonical(archive["results"])
    return archive


def run(
    app: Application, root: Path, config: dict, reasons: dict | None = None, selected: str = "circuit-job.json"
) -> dict:
    unchanged = {
        root / selected: (root / selected).read_bytes(),
        root / config["input"]: (root / config["input"]).read_bytes(),
    }
    result = app.run(root, {"CIRCUIT_CONFIG": str(root / selected)}, timeout=30)
    assert result.returncode == int(bool(reasons)) and not result.stderr, (root, result)
    archive = inspect(root, config, reasons)
    report = json.loads((root / config["output"] / "report.json").read_bytes())
    assert result.stdout == canonical(report["summary"]).decode()
    assert all(path.read_bytes() == data for path, data in unchanged.items())
    return archive


def consume(app: Application, root: Path, name: str, reasons: dict | None = None) -> dict:
    config = json.loads((root / name).read_bytes())
    return run(app, root, config, reasons, name)


def reject(app: Application, root: Path, reason: str = "") -> None:
    result = app.run(root, {}, timeout=10)
    assert result.returncode == 2 and result.stderr and not result.stdout, (root, result)
    assert reason in result.stderr, (reason, result)
    assert not (root / "output").exists() and not list(root.glob(".circuit-*"))
    return  # noqa: PLR1711


def semantics(app: Application, root: Path) -> dict:
    config = fixture(root)
    archive = run(app, root, config)
    original = files_at(root / "output")
    assert consume(app, root / "output", "replay.json") == archive
    assert consume(app, root / "output", "solve.json") == archive
    assert files_at(root / "output") == original
    expected = [100, 0, 0, None, 650, 75, 25, None, 120, 500, 0, 0, None, 1e-100, 1e100, 500]
    for value, result in zip(expected, archive["results"]):
        if value is None:
            assert result["equivalent"]["state"] == "open"
        else:
            close(result["equivalent"]["ohms"], value)
    return {
        "golden_circuits": len(expected),
        "reduction_nodes": sum(row["nodes"] for row in archive["results"]),
        "actual_replay_and_resolve_requests": True,
        "archive_sha256": digest(original["archive.json"]),
    }


def generated_cases(app: Application, root: Path) -> dict:
    rng = random.Random(104)
    hashes, nodes = [], 0
    for batch in range(24):
        rows = []
        for index in range(8):
            tree = generated(rng)
            rows.append(case("base" + str(index), tree))
            transformed = copy.deepcopy(tree)
            stack = [transformed]
            while stack:
                item = stack.pop()
                if "children" in item:
                    item["children"].reverse()
                    stack.extend(item["children"])
            rows.append(case("permuted" + str(index), transformed))
        work = root / str(batch)
        archive = run(app, work, fixture(work, rows))
        for first, second in zip(archive["results"][::2], archive["results"][1::2]):
            assert first["equivalent"]["state"] == second["equivalent"]["state"]
            if first["equivalent"]["state"] != "open":
                close(second["equivalent"]["ohms"], first["equivalent"]["ohms"])
        nodes += sum(row["nodes"] for row in archive["results"])
        hashes.append(digest(canonical(archive)))
    return {
        "seed": 104,
        "batches": 24,
        "circuits": 384,
        "permutation_pairs": 192,
        "reduction_nodes": nodes,
        "exact_rational_oracle": True,
        "archives_sha256": digest(canonical(hashes)),
    }


def invalid_trees() -> list[tuple[dict, str]]:
    number_error = "expected zero or finite resistance in 1e-100..1e100 ohms"
    cases = [
        (resistor(value), "resistance spelling length limit" if value == "" else number_error)
        for value in [
            "-1",
            "nan",
            "inf",
            "1e309",
            "1e101",
            "1e-101",
            "1e-999",
            "1__0",
            "1e",
            "",
            " 1",
            "1 ",
            "１",
            "0x1p0",
            "++1",
        ]
    ]
    cases += [({"kind": "resistor", "ohms": value}, "expected text") for value in [0, 1.5, True, None, [], {}]]
    cases += [(resistor("0" * 65), "resistance spelling length limit")]
    cases += [
        (group(kind, *[resistor(1)] * count), "group requires 2..16 children")
        for kind in ["series", "parallel"]
        for count in [0, 1, 17]
    ]
    cases += [
        ({"kind": "other"}, "unknown node kind"),
        ({"kind": "series", "children": {}}, "expected child array"),
        ({"kind": "short", "ohms": "1"}, "unexpected fields"),
        ({"kind": "resistor"}, "unexpected fields"),
        (group("parallel", {"kind": "short"}, resistor("-2")), number_error),
        (group("series", {"kind": "open"}, resistor("1e999")), number_error),
    ]
    return [(case("bad" + str(i), tree), reason) for i, (tree, reason) in enumerate(cases)]


def invalid(app: Application, root: Path) -> dict:
    bad = invalid_trees()
    for value in [None, [], {}, 1, "resistor", {"id": "x"}, {"kind": "open"}]:
        bad.append(({"id": "bad" + str(len(bad)), "tree": value}, "expected identified node"))
    for name in ["", "1x", "é", "a" * 33]:
        bad.append(({"id": "bad" + str(len(bad)), "tree": {"id": name, "kind": "open"}}, "invalid identifier"))
    duplicate = case("duplicate", group("series", resistor(10), resistor(20)))
    duplicate["tree"]["children"][1]["id"] = duplicate["tree"]["children"][0]["id"]
    bad.append((duplicate, "duplicate node identifier"))
    for offset in range(0, len(bad), 15):
        selected = bad[offset : offset + 15]
        rows = [row for row, _ in selected] + [case("after_errors", resistor(123))]
        reasons = {row["id"]: reason for row, reason in selected}
        work = root / ("trees-" + str(offset))
        archive = run(app, work, fixture(work, rows), reasons)
        assert consume(app, work / "output", "replay.json", reasons) == archive
    invalid_docs = [
        None,
        [],
        {},
        {"version": 2, "cases": fixtures()},
        {"version": True, "cases": fixtures()},
        {"version": 1.0, "cases": fixtures()},
        {"version": 1, "cases": []},
        {"version": 1, "cases": {}},
        {"version": 1, "cases": fixtures() + fixtures()[:1]},
        {"version": 1, "cases": [fixtures()[0], fixtures()[0]]},
        {"version": 1, "cases": [{"id": "1x", "tree": {}}]},
        {"version": 1, "cases": [None]},
        {"version": 1, "cases": [{"id": "x"}]},
        {"version": 1, "cases": fixtures(), "extra": True},
    ]
    for index, value in enumerate(invalid_docs):
        work = root / ("document-" + str(index))
        fixture(work)
        save(work / "networks.json", value)
        reject(app, work)
    config_bad = [
        None,
        [],
        {},
        {"version": 2},
        {"mode": "unknown"},
        {"version": True},
        {"version": 1.0},
        {"input": ""},
        {"output": ""},
        {"input": None},
        {"output": []},
        {"extra": 1},
    ]
    for index, value in enumerate(config_bad):
        work = root / ("request-" + str(index))
        config = fixture(work)
        save(work / "circuit-job.json", {**config, **value} if isinstance(value, dict) and value else value)
        reject(app, work)
    raw_bad = [
        b'{"version":1,"version":1,"cases":[]}',
        b'{"x":NaN}',
        b'{"x":Infinity}',
        b'{"x":1e999}',
        b'{"x":9223372036854775808}',
        b'{"x":"\\ud800"}',
        b"{} {}",
        b'{"x":1,}',
        b"\xff",
        b"",
    ]
    for index, raw in enumerate(raw_bad):
        for name in ["circuit-job.json", "networks.json"]:
            work = root / ("json-" + str(index) + name)
            fixture(work)
            (work / name).write_bytes(raw)
            reject(app, work)
    work = root / "seed"
    archive = run(app, work, fixture(work, [case("seed", group("parallel", resistor(100), resistor(300)))]))
    variants = []
    for mutation in range(15):
        value = copy.deepcopy(archive)
        result = value["results"][0]
        if mutation == 0:
            value["version"] = True
        elif mutation == 1:
            value["extra"] = 1
        elif mutation == 2:
            result["equivalent"]["ohms"] = 75
        elif mutation == 3:
            result["nodes"] = float(result["nodes"])
        elif mutation == 4:
            result["steps"][-1]["arithmetic"]["normalized_sum"] = 1.0
        elif mutation == 5:
            result["steps"][-1]["arithmetic"]["normalized_terms"].reverse()
        elif mutation == 6:
            result["steps"].reverse()
        elif mutation == 7:
            result["steps"][0]["rule"] = "forged"
        elif mutation == 8:
            result["steps"][-1]["children"][0]["equivalent"]["ohms"] = 200.0
        elif mutation == 9:
            result["steps"].pop()
        elif mutation == 10:
            result["equivalent"]["state"] = "open"
        elif mutation == 11:
            value["cases"][0]["tree"]["children"][0]["ohms"] = "200"
        elif mutation == 12:
            value["results"] = []
        elif mutation == 13:
            result["steps"][0]["extra"] = None
        else:
            value["results"] = {"fake": True}
        variants.append(value)
    for index, value in enumerate(variants):
        work = root / ("tampered-" + str(index))
        config = fixture(work)
        config.update(mode="verify", input="archive.json")
        save(work / "circuit-job.json", config)
        save(work / "archive.json", value)
        reject(app, work)
    return {
        "invalid_trees": len(bad),
        "valid_circuit_after_rejections": True,
        "rejected_archive_replay": True,
        "invalid_documents": len(invalid_docs),
        "invalid_requests": len(config_bad),
        "invalid_json_per_input": len(raw_bad),
        "tampered_archives": len(variants),
        "strict_cached_numeric_types": True,
    }


def chain(depth: int) -> dict:
    result = resistor(1)
    for _ in range(depth):
        result = group("series", resistor(1), result)
    return result


def broad(count: int) -> dict:
    branches = [group("series", *[resistor("1e100")] * 16) for _ in range(14)]
    branches.append(group("series", *[resistor("1e100")] * (count - 240)))
    return group("series", *branches)


def limits(app: Application, root: Path) -> dict:
    rows = [
        case("depth16", chain(16)),
        case("depth17", chain(17)),
        case("nodes256", broad(256)),
        case("nodes257", broad(257)),
        case("spelling64", resistor("0" * 63 + "1")),
        case("smallest", resistor("1e-100")),
        case("largest", resistor("1e100")),
    ]
    # 257 nodes at the same fanout/depth: replace one leaf with a two-child group in a 255-node tree.
    rows[3] = case("nodes257", broad(255))
    rows[3]["tree"]["children"][0]["children"][0] = group("series", resistor(1), resistor(1))
    rows[3] = case("nodes257", rows[3]["tree"])
    work = root / "trees"
    reasons = {"depth17": "tree depth limit", "nodes257": "tree node limit"}
    archive = run(app, work, fixture(work, rows), reasons)
    assert archive["results"][2]["nodes"] == 256
    work = root / "exact-bytes"
    config = fixture(work)
    for name, size in [("circuit-job.json", 65536), ("networks.json", 1048576)]:
        p = work / name
        p.write_bytes(p.read_bytes().ljust(size, b" "))
    archive = run(app, work, config)
    for name, size in [("circuit-job.json", 65536), ("networks.json", 1048576)]:
        work = root / ("over-" + name)
        fixture(work)
        p = work / name
        p.write_bytes(p.read_bytes().ljust(size + 1, b" "))
        reject(app, work)
    work = root / "archive-limit"
    config = fixture(work)
    config.update(mode="verify", input="archive.json")
    save(work / "circuit-job.json", config)
    (work / "archive.json").write_bytes(canonical(archive).ljust(4194304, b" "))
    run(app, work, config)
    work = root / "archive-over"
    config = fixture(work)
    config.update(mode="verify", input="archive.json")
    save(work / "circuit-job.json", config)
    (work / "archive.json").write_bytes(canonical(archive).ljust(4194305, b" "))
    reject(app, work)
    return {
        "nodes": 256,
        "root_zero_depth": 16,
        "group_children": 16,
        "cases": 16,
        "resistance_characters": 64,
        "request_bytes": 65536,
        "network_bytes": 1048576,
        "archive_bytes": 4194304,
        "resistance_range": "0 or 1e-100..1e100 ohms",
        "every_branch_validated_before_simplification": True,
    }


def publication(app: Application, root: Path) -> dict:
    rows = [case("seed", group("parallel", resistor(100), resistor(300)))]
    for stage in ["staged", "published"]:
        work = root / ("fault-" + stage)
        config = fixture(work, rows)
        result = app.run(work, {"CIRCUIT_FAULT": stage})
        assert result.returncode == 2 and result.stderr and not result.stdout
        assert not list(work.glob(".circuit-*")) and (work / "output").exists() == (stage == "published")
        if stage == "published":
            inspect(work, config)
    for mutation in ["request", "network", "competitor", "kill-staged", "kill-published"]:
        work = root / mutation
        config = fixture(work, rows)
        release = work / "release"
        stage = "published" if mutation == "kill-published" else "staged"
        process = subprocess.Popen(
            app.command,
            cwd=work,
            env=app.environment({"CIRCUIT_PAUSE": stage, "CIRCUIT_RELEASE": str(release), "PYTHONUNBUFFERED": "1"}),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        try:
            assert select.select([process.stdout], [], [], 10)[0]
            assert process.stdout.readline() == "PAUSED " + stage + "\n"
            if mutation.startswith("kill"):
                process.kill()
                process.communicate(timeout=5)
                assert process.returncode == -9 and (work / "output").exists() == (stage == "published")
                assert len(list(work.glob(".circuit-*"))) == (1 if stage == "staged" else 0)
                if stage == "published":
                    inspect(work, config)
                config["output"] = "retry"
                save(work / "retry.json", config)
                run(app, work, config, selected="retry.json")
            else:
                if mutation == "competitor":
                    (work / "output").mkdir()
                    (work / "output/keep").write_text("original")
                else:
                    name = "circuit-job.json" if mutation == "request" else "networks.json"
                    with (work / name).open("ab") as stream:
                        stream.write(b" ")
                release.touch()
                stdout, stderr = process.communicate(timeout=10)
                assert process.returncode == 2 and stderr and not stdout and not list(work.glob(".circuit-*"))
                if mutation == "competitor":
                    assert (work / "output/keep").read_text() == "original"
                else:
                    assert not (work / "output").exists()
        finally:
            if process.poll() is None:
                process.kill()
            process.communicate(timeout=5)
            process.stdout.close()
            process.stderr.close()
    return {
        "caught_faults": 2,
        "hard_kills": 2,
        "input_output_races": 3,
        "retry_after_hard_kill": True,
        "complete_or_absent_final_bundle": True,
    }


def filesystem(app: Application, root: Path) -> dict:
    count = 0
    for name, kind in itertools.product(
        ["circuit-job.json", "networks.json"], ["symlink", "hardlink", "fifo", "directory", "unreadable"]
    ):
        work = root / str(count)
        fixture(work)
        path = work / name
        raw = path.read_bytes()
        path.unlink()
        target = work / "target"
        target.write_bytes(raw)
        if kind == "symlink":
            path.symlink_to(target)
        elif kind == "hardlink":
            os.link(target, path)
        elif kind == "fifo":
            os.mkfifo(path)
        elif kind == "directory":
            path.mkdir()
        else:
            path.write_bytes(raw)
            path.chmod(0)
        try:
            reject(app, work)
            assert target.read_bytes() == raw
        finally:
            if kind == "unreadable":
                path.chmod(0o600)
        count += 1
    for kind in ["file", "directory", "symlink", "permission"]:
        work = root / str(count)
        fixture(work)
        output = work / "output"
        if kind == "file":
            output.write_text("keep")
        elif kind == "directory":
            output.mkdir()
        elif kind == "symlink":
            output.symlink_to(work / "circuit-job.json")
        else:
            work.chmod(0o500)
        try:
            result = app.run(work, {})
            assert result.returncode == 2 and result.stderr and not result.stdout
            if kind == "file":
                assert output.read_text() == "keep"
            elif kind == "directory":
                assert not list(output.iterdir())
            elif kind == "symlink":
                assert output.is_symlink()
            else:
                assert not output.exists()
        finally:
            work.chmod(0o700)
        count += 1
    return {"guarded_paths_and_permissions": count}


def check(app: Application, directory: Path) -> dict:
    observations = {}
    for name, test in [
        ("semantics", semantics),
        ("generated", generated_cases),
        ("invalid", invalid),
        ("limits", limits),
        ("publication", publication),
        ("filesystem", filesystem),
    ]:
        observations[name] = test(app, directory / name)
        print(app.engine + " circuit calculator " + name + ": passed", flush=True)
    return observations
