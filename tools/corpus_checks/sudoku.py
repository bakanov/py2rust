"""Exhaustive 4x4 completions and independent exact-cover acceptance for Sudoku batches."""

# ruff: noqa: PLR1711 - explicit repository returns

from __future__ import annotations

import copy
import functools
import hashlib
import itertools
import json
import random
import selectors
import subprocess
from dataclasses import dataclass
from pathlib import Path

from corpus_checks.common import Application
from corpus_checks.csv_json import canonical


def board(identifier: str, rows: list, budget: int = 10000) -> dict:
    return {"id": identifier, "box_size": 2 if len(rows) == 4 else 3, "rows": rows, "budget": budget}


def batch(boards: list) -> dict:
    return {"version": 1, "boards": boards}


def solved(base: int) -> list:
    side = base * base
    return [[(row * base + row // base + column) % side + 1 for column in range(side)] for row in range(side)]


def sample() -> dict:
    return batch(
        [
            board("unique", [[1, 0, 3, 4], [3, 4, 0, 2], [2, 1, 4, 0], [0, 3, 2, 1]], 1000),
            board("multiple", [[0] * 4 for _ in range(4)], 1000),
            board("invalid", [[1, 1, 0, 0], [0] * 4, [0] * 4, [0] * 4], 1000),
            board("limited", [[0] * 4 for _ in range(4)], 1),
            board(
                "classic",
                [
                    [int(ch) for ch in row]
                    for row in [
                        "530070000",
                        "600195000",
                        "098000060",
                        "800060003",
                        "400803001",
                        "700020006",
                        "060000280",
                        "000419005",
                        "000080079",
                    ]
                ],
            ),
            board("unsatisfiable", [[1, 2, 3, 0], [0, 0, 0, 4], [0] * 4, [0] * 4], 1000),
        ]
    )


def conflicts(rows: list, base: int) -> list:
    side = base * base
    units = [
        ("row", [[(r, c) for c in range(side)] for r in range(side)]),
        ("column", [[(r, c) for r in range(side)] for c in range(side)]),
        (
            "box",
            [
                [(r, c) for r in range(br, br + base) for c in range(bc, bc + base)]
                for br in range(0, side, base)
                for bc in range(0, side, base)
            ],
        ),
    ]
    result = []
    for kind, groups in units:
        for number, positions in enumerate(groups):
            by_value = {}
            for r, c in positions:
                if rows[r][c]:
                    by_value.setdefault(rows[r][c], []).append({"row": r, "column": c})
            result.extend(
                {"kind": kind, "unit": number, "value": value, "cells": by_value[value]}
                for value in sorted(by_value)
                if len(by_value[value]) > 1
            )
    return result


@functools.lru_cache(maxsize=1)
def all_four() -> tuple:
    permutations = list(itertools.permutations(range(1, 5)))
    partial = [()]
    for row in range(4):
        following = []
        for previous in partial:
            for candidate in permutations:
                if any(candidate[c] in [prior[c] for prior in previous] for c in range(4)):
                    continue
                if row % 2 and any(
                    set(candidate[start : start + 2]) & set(previous[-1][start : start + 2]) for start in [0, 2]
                ):
                    continue
                following.append((*previous, candidate))
        partial = following
    assert len(partial) == 288
    return tuple(partial)


def exact_cover(rows: list, base: int) -> list:
    side = base * base
    columns = {}
    choices = {}
    for row in range(side):
        for column in range(side):
            for value in ([rows[row][column]] if rows[row][column] else range(1, side + 1)):
                key = (row, column, value)
                constraints = (
                    ("cell", row, column),
                    ("row", row, value),
                    ("column", column, value),
                    ("box", (row // base) * base + column // base, value),
                )
                choices[key] = constraints
                for constraint in constraints:
                    columns.setdefault(constraint, set()).add(key)
    # Missing constraints still matter when every candidate for a digit is blocked by givens.
    for kind in ["cell", "row", "column", "box"]:
        for unit in range(side):
            for value in (range(side) if kind == "cell" else range(1, side + 1)):
                columns.setdefault((kind, unit, value), set())
    results = []

    def visit(remaining: dict, selected: list) -> None:
        if not remaining:
            solution = [[0] * side for _ in range(side)]
            for r, c, value in selected:
                solution[r][c] = value
            results.append(solution)
            return
        constraint = min(remaining, key=lambda key: (len(remaining[key]), key))
        for candidate in sorted(remaining[constraint]):
            occupied = choices[candidate]
            excluded = set().union(*(remaining[key] for key in occupied))
            following = {key: options - excluded for key, options in remaining.items() if key not in occupied}
            visit(following, [*selected, candidate])
            if len(results) == 2:
                return
        return

    visit(columns, [])
    return results


@functools.lru_cache(maxsize=2048)
def reference(encoded: str) -> tuple:
    row = json.loads(encoded)
    source, base = row["rows"], row["box_size"]
    errors = conflicts(source, base)
    if errors:
        return errors, []
    if base == 2:
        matches = [
            candidate
            for candidate in all_four()
            if all(
                not value or candidate[r][c] == value
                for r, values in enumerate(source)
                for c, value in enumerate(values)
            )
        ]
        return [], matches
    return [], exact_cover(source, base)


def validate(value: dict, report: dict) -> None:
    assert set(report) == {"version", "boards_sha256", "counts", "results"} and report["version"] == 1
    assert report["boards_sha256"] == hashlib.sha256((canonical(value) + "\n").encode()).hexdigest()
    assert len(report["results"]) == len(value["boards"])
    counts = dict.fromkeys(["invalid", "unsatisfiable", "unique", "multiple", "search_limit"], 0)
    for source, result in zip(value["boards"], report["results"], strict=True):
        assert set(result) == {
            "id",
            "box_size",
            "status",
            "budget",
            "complete_search",
            "solutions_found",
            "solutions",
            "diagnostics",
            "stats",
        }
        assert all(result[key] == source[key] for key in ["id", "box_size", "budget"])
        errors, expected = reference(canonical({"box_size": source["box_size"], "rows": source["rows"]}))
        assert result["diagnostics"] == errors
        assert result["solutions_found"] == len(result["solutions"]) <= 2
        side = source["box_size"] ** 2
        for solution in result["solutions"]:
            assert len(solution) == side and all(len(row) == side for row in solution)
            assert all(type(value) is int and 1 <= value <= side for row in solution for value in row)
            assert not conflicts(solution, source["box_size"])
            assert all(
                not value or solution[r][c] == value
                for r, row in enumerate(source["rows"])
                for c, value in enumerate(row)
            )
            if side == 4:
                assert tuple(tuple(row) for row in solution) in expected
        assert len({canonical(solution) for solution in result["solutions"]}) == len(result["solutions"])
        stats = result["stats"]
        assert set(stats) == {"visited", "expanded", "dead_ends", "max_depth", "remaining_frontier"}
        assert all(type(number) is int and number >= 0 for number in stats.values())
        assert (
            stats["visited"] == stats["expanded"] + stats["dead_ends"] + result["solutions_found"] <= source["budget"]
        )
        empty = sum(value == 0 for row in source["rows"] for value in row)
        assert stats["max_depth"] <= empty and stats["remaining_frontier"] <= 1 + empty * (side - 1)
        assert result["complete_search"] is (not errors and stats["remaining_frontier"] == 0)
        status = result["status"]
        counts[status] += 1
        if errors:
            assert status == "invalid" and not result["solutions"] and not any(stats.values())
        elif status == "unique":
            assert len(expected) == len(result["solutions"]) == 1 and result["complete_search"]
        elif status == "unsatisfiable":
            assert not expected and not result["solutions"] and result["complete_search"]
        elif status == "multiple":
            assert len(expected) >= 2 and len(result["solutions"]) == 2
        else:
            assert status == "search_limit" and not result["complete_search"] and len(result["solutions"]) < 2
            assert stats["visited"] == source["budget"] and stats["remaining_frontier"] > 0
        assert len(expected) >= result["solutions_found"]
    assert report["counts"] == counts
    return


@dataclass
class Fixture:
    work: Path
    config: dict

    @property
    def path(self) -> Path:
        return self.work / "sudoku-job.json"

    @property
    def output(self) -> Path:
        return self.work / self.config["output"]

    def save(self) -> None:
        self.path.write_text(json.dumps(self.config, ensure_ascii=False))
        return

    def settings(self, mode: str = "write", **extra: str) -> dict:
        return {
            "SUDOKU_CONFIG": str(self.path),
            "SUDOKU_MODE": mode,
            "SUDOKU_FAIL": "",
            "SUDOKU_PAUSE": "",
            "SUDOKU_CONTINUE": "",
            **extra,
        }


def fixture(directory: Path, name: str, value: dict, **changes: object) -> Fixture:
    work = directory / name
    work.mkdir(parents=True)
    fix = Fixture(work, {"boards": "boards.json", "output": "sudoku-results", **changes})
    (work / "boards.json").write_text(json.dumps(value, ensure_ascii=False))
    fix.save()
    return fix


def outputs(fix: Fixture, report: dict) -> dict:
    value = json.loads((fix.work / fix.config["boards"]).read_bytes())
    text = []
    for result in report["results"]:
        lines = [
            f"Board {canonical(result['id'])}: {result['status']}",
            f"Visited {result['stats']['visited']} of {result['budget']} permitted nodes",
        ]
        lines.extend(canonical(error) for error in result["diagnostics"])
        for index, solution in enumerate(result["solutions"], 1):
            lines.append("Solution " + str(index))
            lines.extend(" ".join(str(number) for number in row) for row in solution)
        text.append("\n".join(lines) + "\n")
    files = {
        "boards.json": (canonical(value) + "\n").encode(),
        "results.json": (canonical(report) + "\n").encode(),
        "results.jsonl": "".join(canonical(row) + "\n" for row in report["results"]).encode(),
        "diagnostics.txt": "\n".join(text).encode(),
    }
    actual = {path.name: path.read_bytes() for path in fix.output.iterdir()}
    assert set(actual) == {*files, "manifest.json"}
    for name, expected in files.items():
        assert actual[name] == expected
    manifest = json.loads(actual["manifest.json"])
    assert manifest == {
        "version": 1,
        "files": {name: {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()} for name, raw in files.items()},
    }
    return actual


def success(app: Application, fix: Fixture, mode: str = "write") -> dict:
    paths = [fix.path, fix.work / fix.config["boards"]]
    original = [path.read_bytes() for path in paths]
    result = app.run(fix.work, fix.settings(mode), timeout=180)
    assert result.returncode in [0, 1] and not result.stderr, (fix.work, result)
    report = json.loads(result.stdout)
    validate(json.loads(original[1]), report)
    assert result.returncode == int(report["counts"]["unique"] != len(report["results"]))
    assert result.stdout == canonical(report) + "\n" and original == [path.read_bytes() for path in paths]
    if mode == "write":
        outputs(fix, report)
    else:
        assert not fix.output.exists()
    assert not list(fix.work.glob(".sudoku-*"))
    return report


def failure(app: Application, fix: Fixture, message: str = "", **extra: str) -> None:
    existed = fix.output.exists() or fix.output.is_symlink()
    before = fix.output.read_bytes() if fix.output.is_file() else None
    result = app.run(fix.work, fix.settings(**extra), timeout=90)
    assert result.returncode == 2 and result.stderr and message in result.stderr and not result.stdout, (
        result,
        message,
    )
    assert (fix.output.exists() or fix.output.is_symlink()) == existed
    if before is not None:
        assert fix.output.read_bytes() == before
    assert not list(fix.work.glob(".sudoku-*"))
    return


def scenarios(app: Application, directory: Path) -> dict:
    digest = hashlib.sha256()
    initial = success(app, fixture(directory, "sample", sample()))
    assert initial["counts"] == {"unique": 2, "multiple": 1, "invalid": 1, "search_limit": 1, "unsatisfiable": 1}
    digest.update(canonical(initial).encode())
    variants = []
    for index, values in enumerate(itertools.product(range(5), repeat=4)):
        rows = [[0] * 4 for _ in range(4)]
        for position, value in zip([0, 1, 4, 5], values, strict=True):
            rows[position // 4][position % 4] = value
        variants.append(board("block-" + str(index), rows, 1000))
    for mask in range(256):
        rows = solved(2)
        for bit, position in enumerate([0, 2, 5, 7, 8, 10, 13, 15]):
            if mask & (1 << bit):
                rows[position // 4][position % 4] = 0
        variants.append(board("mask-" + str(mask), rows, 1000))
    for index in range(0, len(variants), 64):
        report = success(app, fixture(directory, "exhaustive-" + str(index), batch(variants[index : index + 64])))
        assert report["counts"]["search_limit"] == 0
        digest.update(canonical(report).encode())
    rng = random.Random(70070)
    generated = []
    for index in range(80):
        base = 2 if index < 40 else 3
        side = base * base
        rows = solved(base)
        digits = list(range(1, side + 1))
        rng.shuffle(digits)
        rows = [[digits[value - 1] for value in row] for row in rows]
        if index % 2:
            rows = [list(column) for column in zip(*rows, strict=True)]
        for position in rng.sample(range(side * side), rng.randrange(side * side + 1)):
            rows[position // side][position % side] = 0
        generated.append(board("generated-" + str(index), rows, 10000))
    for index in range(0, len(generated), 40):
        report = success(app, fixture(directory, "generated-" + str(index), batch(generated[index : index + 40])))
        assert report["counts"]["invalid"] == report["counts"]["unsatisfiable"] == report["counts"]["search_limit"] == 0
        digest.update(canonical(report).encode())
    # Each complete solution is unique; a one-hole board needs one expansion and one solution node.
    full = solved(2)
    one_hole = copy.deepcopy(full)
    one_hole[0][0] = 0
    budgets = [board("full-" + str(n), full, n) for n in [0, 1, 2]]
    budgets += [board("hole-" + str(n), one_hole, n) for n in [0, 1, 2, 3]]
    budgets += [board("blank-" + str(n), [[0] * 4 for _ in range(4)], n) for n in range(23)]
    report = success(app, fixture(directory, "budgets", batch(budgets)))
    assert [row["status"] for row in report["results"][:7]] == [
        "search_limit",
        "unique",
        "unique",
        "search_limit",
        "search_limit",
        "unique",
        "unique",
    ]
    blank = report["results"][7:]
    assert blank[16]["solutions_found"] == 0
    assert blank[17]["solutions_found"] == 1 and blank[17]["status"] == "search_limit"
    assert blank[20]["solutions_found"] == 1 and blank[21]["status"] == "multiple"
    digest.update(canonical(report).encode())
    hard_rows = [
        [int(ch) for ch in row]
        for row in [
            "100007090",
            "030020008",
            "009600500",
            "005300900",
            "010080002",
            "600004000",
            "300000010",
            "040000007",
            "007000300",
        ]
    ]
    hard_boards = [
        board("hard-" + str(budget), hard_rows, budget) for budget in [0, 1, 10, 100, 1000, 2231, 2232, 100000]
    ]
    deep_unsat = [[0, 0, 0, 0], [0, 4, 1, 0], [0, 0, 0, 2], [2, 0, 0, 0]]
    hard_boards += [board("unsat-" + str(budget), deep_unsat, budget) for budget in [0, 1, 2]]
    report = success(app, fixture(directory, "backtracking", batch(hard_boards)))
    assert all(row["status"] == "search_limit" for row in report["results"][:6])
    assert report["results"][6]["status"] == report["results"][7]["status"] == "unique"
    assert report["results"][6]["stats"] == {
        "visited": 2232,
        "expanded": 2116,
        "dead_ends": 115,
        "max_depth": 58,
        "remaining_frontier": 0,
    }
    assert report["results"][7]["stats"] == report["results"][6]["stats"]
    assert [row["status"] for row in report["results"][8:]] == ["search_limit", "search_limit", "unsatisfiable"]
    assert report["results"][-1]["stats"]["expanded"] == report["results"][-1]["stats"]["dead_ends"] == 1
    digest.update(canonical(report).encode())
    diagnostics = [
        board("row", [[1, 0, 1, 0], [0] * 4, [0] * 4, [0] * 4]),
        board("column", [[1, 0, 0, 0], [0] * 4, [1, 0, 0, 0], [0] * 4]),
        board("box", [[1, 0, 0, 0], [0, 1, 0, 0], [0] * 4, [0] * 4]),
        board("all-conflicts", [[1] * 9 for _ in range(9)], 0),
        board("unsatisfiable-nine", [[1, 2, 3, 4, 5, 6, 7, 8, 0], [0] * 8 + [9], *[[0] * 9 for _ in range(7)]], 1000),
        board("empty-nine", [[0] * 9 for _ in range(9)], 10000),
    ]
    report = success(app, fixture(directory, "diagnostics", batch(diagnostics)))
    assert [row["status"] for row in report["results"]] == ["invalid"] * 4 + ["unsatisfiable", "multiple"]
    assert len(report["results"][3]["diagnostics"]) == 27
    digest.update(canonical(report).encode())
    permuted = copy.deepcopy(sample())
    permuted["boards"].reverse()
    report = success(app, fixture(directory, "reordered", permuted))
    assert report["results"] == list(reversed(initial["results"])) and report["counts"] == initial["counts"]
    parts = []
    for index, rows in enumerate([sample()["boards"][:3], sample()["boards"][3:]]):
        parts.extend(success(app, fixture(directory, "split-" + str(index), batch(rows)))["results"])
    assert parts == initial["results"]
    success(app, fixture(directory, "empty-batch", batch([])))
    return {
        "four_by_four_completions": len(all_four()),
        "exhaustive_block_patterns": 625,
        "erased_cell_patterns": 256,
        "generated_boards": 80,
        "budget_cases": len(budgets),
        "diagnostic_boards": len(diagnostics),
        "backtracking_budget_cases": len(hard_boards),
        "split_batches": 2,
        "reports_sha256": digest.hexdigest(),
    }


def invalid_inputs(app: Application, directory: Path) -> int:
    base = batch([board("q", solved(2))])
    variants = [None, [], {}, True, {**base, "extra": 1}]
    variants += [{key: value for key, value in base.items() if key != missing} for missing in base]
    variants += [{**base, "version": value} for value in [0, 2, True, 1.0, "1", None]]
    variants += [{**base, "boards": value} for value in [None, {}, True, ""]]
    row = base["boards"][0]
    malformed = [None, [], {}, True, {**row, "extra": 1}]
    malformed += [{key: value for key, value in row.items() if key != missing} for missing in row]
    for field, values in [
        ("id", ["", "a\x00", "x" * 129, "🙂" * 129, None, True, 1, [], {}]),
        ("box_size", [-1, 0, 1, 4, True, 2.0, "2", None, [], {}]),
        ("budget", [-1, 100001, True, 1.0, "1", None, [], {}]),
        ("rows", [None, {}, True, "", [], [[0] * 4] * 3, [[0] * 4] * 5]),
    ]:
        malformed += [{**row, field: value} for value in values]
    for value in [None, {}, True, "", [], [0] * 3, [0] * 5]:
        malformed.append({**row, "rows": [value, *row["rows"][1:]]})
    for value in [-1, 5, True, 1.0, "1", None, [], {}]:
        malformed.append({**row, "rows": [[value, *row["rows"][0][1:]], *row["rows"][1:]]})
    variants += [batch([value]) for value in malformed]
    variants.append(batch([row, row]))
    for index, value in enumerate(variants):
        failure(app, fixture(directory, "boards-" + str(index), value))
    count = len(variants)
    for key in ["boards", "output"]:
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
    failure(app, fixture(directory, "mode", base), "invalid Sudoku mode", SUDOKU_MODE="bad")
    count += 2
    for name in ["boards.json", "sudoku-job.json"]:
        for index, raw in enumerate([b"\xff", b"{", b"[] trailing", b"[NaN]", b"[Infinity]", b'{"a":1,"a":2}']):
            fix = fixture(directory, f"raw-{name}-{index}", base)
            (fix.work / name).write_bytes(raw)
            failure(app, fix)
            count += 1
    return count


def limits(app: Application, directory: Path) -> dict:
    rows = [board(str(index), solved(3), 0) for index in range(64)]
    for index in range(10):
        rows[index]["budget"] = 100000
    report = success(app, fixture(directory, "combined-capacity", batch(rows)))
    assert report["counts"]["unique"] == 10 and report["counts"]["search_limit"] == 54
    too_many = [*rows, board("extra", solved(3), 0)]
    failure(app, fixture(directory, "boards-above", batch(too_many)), "board count")
    rows[10]["budget"] = 1
    failure(app, fixture(directory, "budget-above", batch(rows)), "batch budget")
    success(app, fixture(directory, "name-exact", batch([board("🙂" * 128, solved(2), 1)])))
    for name, maximum in [("sudoku-job.json", 65536), ("boards.json", 1048576)]:
        fix = fixture(directory, "bytes-" + name, sample())
        path = fix.work / name
        raw = path.read_bytes()
        path.write_bytes(raw + b" " * (maximum - len(raw)))
        success(app, fix, "preview")
        path.write_bytes(raw + b" " * (maximum + 1 - len(raw)))
        failure(app, fix, "byte limit")
        path.write_bytes(raw)
    return {
        "boards": 64,
        "box_sizes": [2, 3],
        "board_budget": 100000,
        "batch_budget": 1000000,
        "name_characters": 128,
        "name_bytes": 512,
        "config_bytes": 65536,
        "boards_bytes": 1048576,
    }


def paused(app: Application, fix: Fixture) -> subprocess.Popen:
    process = subprocess.Popen(
        app.command,
        cwd=fix.work,
        env=app.environment(fix.settings(SUDOKU_PAUSE="ready", SUDOKU_CONTINUE=str(fix.work / "continue"))),
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
        "boards.json",
        "results.json",
        "results.jsonl",
        "diagnostics.txt",
        "manifest.json",
        "ready",
        "published",
    ]
    for point in points:
        fix = fixture(directory, "fault-" + point, sample())
        reference = success(app, fix, "preview")
        result = app.run(fix.work, fix.settings(SUDOKU_FAIL=point))
        assert result.returncode == 2 and "injected failure: " + point in result.stderr and not result.stdout
        assert not list(fix.work.glob(".sudoku-*"))
        if point == "published":
            outputs(fix, reference)
        else:
            assert not fix.output.exists()
            success(app, fix)
    for name in ["boards", "config", "destination"]:
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
            assert not list(fix.work.glob(".sudoku-*"))
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
    abandoned = list(fix.work.glob(".sudoku-*"))
    assert len(abandoned) == 1
    old = {path.name: path.read_bytes() for path in abandoned[0].iterdir()}
    result = app.run(fix.work, fix.settings())
    assert result.returncode == 1 and not result.stderr
    outputs(fix, reference)
    assert {path.name: path.read_bytes() for path in abandoned[0].iterdir()} == old
    return len(points) + 4


def paths(app: Application, directory: Path) -> int:
    names = ["boards.json", "sudoku-job.json"]
    for name in ["file", "directory", "symlink", "dangling", *names]:
        fix = fixture(directory, "destination-" + name, sample())
        if name == "file":
            fix.output.write_bytes(b"preserve")
        elif name == "directory":
            fix.output.mkdir()
            (fix.output / "keep").write_bytes(b"preserve")
        elif name in ["symlink", "dangling"]:
            fix.output.symlink_to(fix.work / ("boards.json" if name == "symlink" else "missing"))
        else:
            fix.config["output"] = name
            fix.save()
        failure(app, fix, "output directory already exists")
    for name in names:
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
    print(app.engine + " Sudoku: exhaustive completions, exact-cover oracle and budget checks passed", flush=True)
    invalid = invalid_inputs(app, directory / "invalid")
    bounds = limits(app, directory / "limits")
    faults = publication(app, directory / "publication")
    path_cases = paths(app, directory / "paths")
    print(app.engine + " Sudoku: validation, limits, publication and paths passed", flush=True)
    return {**cases, "invalid_inputs": invalid, "limits": bounds, "publication_cases": faults, "path_cases": path_cases}
