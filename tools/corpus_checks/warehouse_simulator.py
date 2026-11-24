"""Complete warehouse acceptance with an independent coordinate-set oracle and actual continuation exports."""

from __future__ import annotations

import copy
import itertools
import json
import os
import random
import select
import subprocess
from pathlib import Path

from .common import Application
from .warehouse_fixture import canonical, digest, display, document, expected, program


def save(path: Path, value: object) -> None:
    path.write_bytes(canonical(value))
    return  # noqa: PLR1711


def files_at(path: Path) -> dict[str, bytes]:
    return {p.name: p.read_bytes() for p in path.iterdir() if p.is_file()}


def fixture(root: Path, source: dict | None = None) -> dict:
    root.mkdir(parents=True, exist_ok=True)
    config = {"version": 1, "mode": "simulate", "input": "program.json", "output": "output"}
    save(root / "warehouse-job.json", config)
    save(root / "program.json", document() if source is None else source)
    return config


def inspect(root: Path, config: dict) -> dict:
    imported = json.loads((root / config["input"]).read_bytes())
    source = imported["source"] if config["mode"] == "verify" else imported
    results = expected(source)
    archive = {"version": 1, "source": source, "results": results}
    active = results["active_commands"]
    lines = [display(source["title"]), canonical(results["summary"]).decode().strip(), "", *results["final"]["grid"]]
    files = {
        "archive.json": canonical(archive),
        "program.json": canonical(source),
        "trace.json": canonical(results["trace"]),
        "continuation.json": canonical(program(source["grid"], active, source["title"])),
        "rewind.json": canonical(program(source["grid"], active + ["undo"] * len(active), source["title"])),
        "layout.json": canonical(program(results["final"]["grid"], [], source["title"])),
        "layout.txt": ("\n".join(lines) + "\n").encode(),
        "report.json": canonical(
            {
                "version": 1,
                "mode": config["mode"],
                "summary": results["summary"],
                "archive_sha256": digest(canonical(archive)),
            }
        ),
    }
    for name, mode, input_name, output in [
        ("replay.json", "verify", "archive.json", "replayed"),
        ("simulate.json", "simulate", "program.json", "simulated"),
        ("continue-job.json", "simulate", "continuation.json", "continued"),
        ("rewind-job.json", "simulate", "rewind.json", "rewound"),
        ("restart-job.json", "simulate", "layout.json", "restarted"),
    ]:
        files[name] = canonical({"version": 1, "mode": mode, "input": input_name, "output": output})
    files["manifest.json"] = canonical(
        {name: {"bytes": len(raw), "sha256": digest(raw)} for name, raw in files.items()}
    )
    directory = root / config["output"]
    assert {p.name for p in directory.iterdir()} == set(files)
    for name, raw in files.items():
        actual = (directory / name).read_bytes()
        assert actual == raw, (directory, name, actual[:2000], raw[:2000])
    if config["mode"] == "verify":
        assert canonical(imported["results"]) == canonical(results)
    return archive


def run(app: Application, root: Path, config: dict, selected: str = "warehouse-job.json") -> dict:
    unchanged = {root / name: (root / name).read_bytes() for name in [selected, config["input"]]}
    result = app.run(root, {"WAREHOUSE_CONFIG": str(root / selected)}, timeout=120)
    assert result.returncode == 0 and not result.stderr, (root, result)
    archive = inspect(root, config)
    assert result.stdout == canonical(archive["results"]["summary"]).decode()
    assert all(path.read_bytes() == raw for path, raw in unchanged.items())
    return archive


def consume(app: Application, root: Path, name: str) -> dict:
    return run(app, root, json.loads((root / name).read_bytes()), name)


def reject(app: Application, root: Path, needle: str = "") -> None:
    result = app.run(root, {}, timeout=30)
    assert result.returncode == 2 and result.stderr and not result.stdout, (root, result)
    assert needle in result.stderr
    assert not (root / "output").exists() and not list(root.glob(".warehouse-*"))
    return  # noqa: PLR1711


def exported_programs(app: Application, root: Path, archive: dict) -> None:
    original = files_at(root)
    continued = consume(app, root, "continue-job.json")
    assert continued["results"]["final"] == archive["results"]["final"]
    assert continued["results"]["active_commands"] == archive["results"]["active_commands"]
    rewound = consume(app, root, "rewind-job.json")
    assert rewound["results"]["final"] == archive["results"]["initial"]
    assert rewound["results"]["active_commands"] == []
    restarted = consume(app, root, "restart-job.json")
    assert restarted["results"]["initial"] == dict(archive["results"]["final"], history_depth=0)
    assert restarted["results"]["initial"] == restarted["results"]["final"]
    assert files_at(root) == original
    return  # noqa: PLR1711


def semantics(app: Application, root: Path) -> dict:
    archive = run(app, root, fixture(root))
    results = archive["results"]
    assert results["summary"] == {"commands": 15, "walks": 6, "pushes": 3, "undos": 3, "blocked": 3, "history_depth": 6}
    assert results["final"]["grid"] == ["########", "#...$..#", "#.@$#..#", "#..$...#", "#......#", "########"]
    assert results["final"]["robot"] == [2, 2] and results["final"]["boxes"] == [[1, 4], [2, 3], [3, 3]]
    assert results["active_commands"] == ["up", "right", "left", "down", "down", "up"]
    assert consume(app, root / "output", "replay.json") == archive
    assert consume(app, root / "output", "simulate.json") == archive
    exported_programs(app, root / "output", archive)
    cases = [
        (["@"], ["up", "right", "down", "left", "undo"]),
        (["@#"], ["right", "left", "undo"]),
        (["@$$."], ["right", "undo"]),
        (["@$#"], ["right", "undo"]),
        (["@$"], ["right", "undo"]),
        (["@$."], ["right", "left", "undo", "undo"]),
        (["...", ".$.", ".@.", "..."], ["up", "up", "undo"]),
        (["...", ".@.", ".$.", "..."], ["down", "down", "undo"]),
        (["....", ".$@.", "...."], ["left", "left", "undo"]),
        (["....", ".@$.", "...."], ["right", "right", "undo"]),
        ([".@."], []),
    ]
    reasons = set()
    for index, (grid, commands) in enumerate(cases):
        work = root / ("hand-" + str(index))
        current = run(app, work, fixture(work, program(grid, commands, " Café\t倉庫\n ")))
        assert current["results"]["final"] == current["results"]["initial"]
        reasons.update(row["reason"] for row in current["results"]["trace"] if row["reason"])
        exported_programs(app, work / "output", current)
    assert reasons == {"boundary", "wall", "box_boundary", "box_wall", "box_chain", "empty_history"}
    return {
        "hand_programs": 1 + len(cases),
        "all_four_push_directions": True,
        "all_six_block_reasons": True,
        "walk_and_push_undo_restore_exact_state": True,
        "blocked_moves_preserve_state_and_history": True,
        "actual_replay_continuation_rewind_restart_requests": True,
        "archive_sha256": digest(canonical(archive)),
    }


def edit_export(app: Application, root: Path, source: dict, stem: str) -> dict:
    original = files_at(root)
    config = json.loads((root / "continue-job.json").read_bytes())
    config.update(input=stem + "-program.json", output=stem)
    save(root / config["input"], source)
    save(root / (stem + "-job.json"), config)
    result = run(app, root, config, stem + "-job.json")
    assert all((root / name).read_bytes() == raw for name, raw in original.items())
    return result


def rotate(state: dict) -> dict:
    height = len(state["grid"])
    return {
        "grid": ["".join(reversed(column)) for column in zip(*state["grid"])],
        "robot": [state["robot"][1], height - 1 - state["robot"][0]],
        "boxes": sorted([[column, height - 1 - row] for row, column in state["boxes"]]),
        "history_depth": state["history_depth"],
    }


def generated(app: Application, root: Path) -> dict:
    rng = random.Random(109)
    hashes = []
    steps = 0
    moves = {"up": "right", "right": "down", "down": "left", "left": "up", "undo": "undo"}
    for batch in range(24):
        height, width = 3 + batch % 6, 3 + (batch * 3) % 5
        cells = [["#" if rng.randrange(5) == 0 else "." for _ in range(width)] for _ in range(height)]
        free = [(row, column) for row in range(height) for column in range(width) if cells[row][column] == "."]
        rng.shuffle(free)
        if not free:
            cells[0][0] = "."
            free = [(0, 0)]
        row, column = free.pop()
        cells[row][column] = "@"
        for row, column in free[: min(len(free), 1 + batch % 7)]:
            cells[row][column] = "$"
        words = [rng.choice(list(moves)) for _ in range(128 + 32 * (batch % 4))]
        source = program(["".join(row) for row in cells], words, "Generated 倉庫 " + str(batch))
        work = root / str(batch)
        first = run(app, work, fixture(work, source))
        hashes.append(digest(canonical(first)))
        steps += len(words)
        exported_programs(app, work / "output", first)
        turned = program(rotate(first["results"]["initial"])["grid"], [moves[word] for word in words], source["title"])
        other = run(app, work / "rotated", fixture(work / "rotated", turned))
        assert other["results"]["final"] == rotate(first["results"]["final"])
        assert other["results"]["summary"] == first["results"]["summary"]
        for left, right in zip(first["results"]["trace"], other["results"]["trace"]):
            assert left["action"] == right["action"] and left["reason"] == right["reason"]
            assert rotate(left["state"]) == right["state"]
        changed = json.loads((work / "output/continuation.json").read_bytes())
        depth = len(changed["commands"])
        changed["commands"] += ["undo"] * depth + ["right", "down", "left", "up"]
        edited = edit_export(app, work / "output", changed, "edited")
        if depth:
            assert edited["results"]["trace"][2 * depth - 1]["state"] == first["results"]["initial"]
        assert consume(app, work / "output/edited", "replay.json") == edited
        hashes.append(digest(canonical(edited)))
    return {
        "seed": 109,
        "programs": 24,
        "primary_trace_steps": steps,
        "rotated_trace_steps": steps,
        "rotations_checked": 24,
        "exported_program_sets_checked": 24,
        "edited_continuations_replayed": 24,
        "independent_coordinate_sets_and_snapshot_undo": True,
        "walls_boxes_robot_and_history_invariants": True,
        "archives_sha256": digest("\n".join(hashes).encode()),
    }


def invalid(app: Application, root: Path) -> dict:
    sources = []
    for field, values in [
        ("version", [0, 2, True, 1.0, "1", None]),
        (
            "title",
            [None, 1, False, [], {}, "", " \n\t ", "x" * 101, "\ufb01" * 51, "x\x00y", "x\x7fy", "x\x80y", "x\x9fy"],
        ),
        (
            "grid",
            [
                None,
                1,
                False,
                {},
                "@",
                [],
                [""],
                [".."],
                ["@@"],
                ["@.", "."],
                ["@", ".."],
                [None],
                [1],
                [False],
                [["@"]],
                ["@ "],
                ["@\n"],
                ["@\x00"],
                ["@😀"],
                ["@＠"],
                ["@*"],
                ["@"] + ["."] * 32,
                ["@" + "." * 32],
            ],
        ),
        (
            "commands",
            [
                None,
                False,
                1,
                {},
                "up",
                [None],
                [1],
                [True],
                [{}],
                [[]],
                [""],
                ["UP"],
                ["up "],
                ["left\n"],
                ["jump"],
                ["↑"],
            ],
        ),
    ]:
        for value in values:
            source = document()
            source[field] = value
            sources.append(source)
    for field in ["version", "title", "grid", "commands"]:
        source = document()
        del source[field]
        sources.append(source)
    sources += [None, [], 42, True, {}, dict(document(), extra=True)]
    for index, source in enumerate(sources):
        work = root / ("source-" + str(index))
        fixture(work)
        save(work / "program.json", source)
        reject(app, work)
    valid = {"version": 1, "mode": "simulate", "input": "program.json", "output": "output"}
    configs = [
        dict(valid, **{key: value})
        for key, value in [
            ("version", True),
            ("version", 1.0),
            ("version", 2),
            ("mode", "unknown"),
            ("mode", 1),
            ("input", None),
            ("input", ""),
            ("input", "missing"),
            ("output", None),
            ("output", ""),
        ]
    ]
    configs += [{key: value for key, value in valid.items() if key != "mode"}, dict(valid, extra=True)]
    for index, config in enumerate(configs):
        work = root / ("request-" + str(index))
        fixture(work)
        save(work / "warehouse-job.json", config)
        reject(app, work)
    malformed = [
        b"",
        b"{",
        b"{}{}",
        b"[] trailing",
        b'{"version":1,"version":1}',
        b'{"x":NaN}',
        b'{"x":Infinity}',
        b'{"x":1e9999}',
        b"\xff",
        b'{"x":"\\ud800"}',
    ]
    for slot in ["request", "source", "archive"]:
        for index, raw in enumerate(malformed):
            work = root / (slot + "-json-" + str(index))
            config = fixture(work)
            name = "warehouse-job.json" if slot == "request" else "program.json"
            if slot == "archive":
                name = "archive.json"
                config.update(mode="verify", input=name)
                save(work / "warehouse-job.json", config)
            (work / name).write_bytes(raw)
            reject(app, work)
    archive = {"version": 1, "source": document(), "results": expected(document())}
    changes = [
        (("version",), 1.0),
        (("results", "summary", "walks"), 6.0),
        (("results", "summary", "history_depth"), 0),
        (("results", "trace", 0, "index"), False),
        (("results", "trace", 0, "state", "history_depth"), False),
        (("results", "trace", 0, "action"), "move"),
        (("results", "trace", 0, "reason"), "wall"),
        (("results", "final", "robot"), [1, 1]),
        (("results", "final", "boxes"), list(reversed(archive["results"]["final"]["boxes"]))),
        (("results", "active_commands"), []),
        (("results", "initial", "grid", 0), "........"),
        (("source", "commands", 0), "undo"),
        (("results", "trace"), list(reversed(archive["results"]["trace"]))),
    ]
    for index, (path, value) in enumerate(changes):
        changed = copy.deepcopy(archive)
        target = changed
        for key in path[:-1]:
            target = target[key]
        target[path[-1]] = value
        work = root / ("tampered-" + str(index))
        config = fixture(work)
        config.update(mode="verify", input="archive.json")
        save(work / "warehouse-job.json", config)
        save(work / "archive.json", changed)
        reject(app, work)
    return {
        "invalid_sources": len(sources),
        "invalid_requests": len(configs),
        "invalid_json_per_input": len(malformed),
        "tampered_archives": len(changes),
        "strict_cached_numeric_types": True,
    }


def limits(app: Application, root: Path) -> dict:
    cells = [["."] * 32 for _ in range(32)]
    cells[0][0] = "@"
    cells[0][1] = "#"
    cells[1] = ["$"] * 32
    cells[2] = ["$"] * 32
    source = program(["".join(row) for row in cells], ["up", "right", "down", "left"] * 512, "😀" * 100)
    work = root / "maximum-trace"
    archive = run(app, work, fixture(work, source))
    assert archive["results"]["summary"] == {
        "commands": 2048,
        "walks": 0,
        "pushes": 0,
        "undos": 0,
        "blocked": 2048,
        "history_depth": 0,
    }
    assert len(archive["results"]["final"]["boxes"]) == 64
    maximum_bytes = len((work / "output/archive.json").read_bytes())
    assert maximum_bytes < 16777216
    exported_programs(app, work / "output", archive)
    work = root / "maximum-history"
    source = program(["@."], ["right", "left"] * 512)
    archive = run(app, work, fixture(work, source))
    assert archive["results"]["summary"]["history_depth"] == 1024
    exported_programs(app, work / "output", archive)
    rewind = json.loads((work / "output/rewind.json").read_bytes())
    assert len(rewind["commands"]) == 2048
    restored = json.loads((work / "output/rewound/archive.json").read_bytes())
    assert restored["results"]["summary"]["undos"] == 1024
    assert restored["results"]["final"] == archive["results"]["initial"]
    work = root / "over-history"
    fixture(work, program(["@."], ["right", "left"] * 512 + ["right"]))
    reject(app, work, "undo history limit")
    work = root / "over-commands"
    fixture(work, program(["@"], ["undo"] * 2049))
    reject(app, work)
    cells[3][0] = "$"
    work = root / "over-boxes"
    fixture(work, program(["".join(row) for row in cells], []))
    reject(app, work, "box count limit")
    for index, grid in enumerate([["@"], ["@"] + ["."] * 31, ["@" + "." * 31]]):
        work = root / ("dimensions-" + str(index))
        run(app, work, fixture(work, program(grid, [])))
    work = root / "exact-bytes"
    config = fixture(work)
    for name, size in [("warehouse-job.json", 65536), ("program.json", 2097152)]:
        path = work / name
        path.write_bytes(path.read_bytes().ljust(size, b" "))
    archive = run(app, work, config)
    for name, size in [("warehouse-job.json", 65536), ("program.json", 2097152)]:
        work = root / ("over-" + name)
        fixture(work)
        path = work / name
        path.write_bytes(path.read_bytes().ljust(size + 1, b" "))
        reject(app, work)
    for over in [False, True]:
        work = root / ("archive-over" if over else "archive-limit")
        config = fixture(work)
        config.update(mode="verify", input="archive.json")
        save(work / "warehouse-job.json", config)
        (work / "archive.json").write_bytes(canonical(archive).ljust(16777216 + int(over), b" "))
        if over:
            reject(app, work)
        else:
            run(app, work, config)
    return {
        "rows": 32,
        "columns": 32,
        "boxes": 64,
        "commands": 2048,
        "undo_history": 1024,
        "full_history_rewind_commands": 2048,
        "title_characters": 100,
        "maximum_trace_archive_bytes": maximum_bytes,
        "request_bytes": 65536,
        "source_bytes": 2097152,
        "archive_bytes": 16777216,
    }


def publication(app: Application, root: Path) -> dict:
    rows = document()
    for stage in ["staged", "published"]:
        work = root / ("fault-" + stage)
        config = fixture(work, rows)
        result = app.run(work, {"WAREHOUSE_FAULT": stage})
        assert result.returncode == 2 and result.stderr and not result.stdout
        assert not list(work.glob(".warehouse-*")) and (work / "output").exists() == (stage == "published")
        if stage == "published":
            inspect(work, config)
    for mutation in ["request", "source", "competitor", "kill-staged", "kill-published"]:
        work = root / mutation
        config = fixture(work, rows)
        release = work / "release"
        stage = "published" if mutation == "kill-published" else "staged"
        process = subprocess.Popen(
            app.command,
            cwd=work,
            env=app.environment({"WAREHOUSE_PAUSE": stage, "WAREHOUSE_RELEASE": str(release), "PYTHONUNBUFFERED": "1"}),
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
                assert len(list(work.glob(".warehouse-*"))) == (1 if stage == "staged" else 0)
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
                    name = "warehouse-job.json" if mutation == "request" else "program.json"
                    with (work / name).open("ab") as stream:
                        stream.write(b" ")
                release.touch()
                stdout, stderr = process.communicate(timeout=10)
                assert process.returncode == 2 and stderr and not stdout and not list(work.glob(".warehouse-*"))
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
        ["warehouse-job.json", "program.json"], ["symlink", "hardlink", "fifo", "directory", "unreadable"]
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
            output.symlink_to(work / "warehouse-job.json")
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
        ("generated", generated),
        ("invalid", invalid),
        ("limits", limits),
        ("publication", publication),
        ("filesystem", filesystem),
    ]:
        observations[name] = test(app, directory / name)
        print(app.engine + " warehouse simulator " + name + ": passed", flush=True)
    return observations
