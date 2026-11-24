"""Independent list-of-items packing oracle, conservation audits and durable bundle checks."""

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


def item(identifier: str, weight: int = 1, volume: int = 1, destination: str = "home", separate: bool = False) -> dict:
    return {
        "id": identifier,
        "destination": destination,
        "weight_g": weight,
        "volume_cm3": volume,
        "separate": separate,
    }


def box(identifier: str, weight: int = 10, volume: int = 10, **changes: int) -> dict:
    return {
        "id": identifier,
        "weight_limit_g": weight,
        "volume_limit_cm3": volume,
        "item_limit": 512,
        "tare_g": 0,
        "cost_cents": 100,
        "stock": 512,
        **changes,
    }


def problem(items: list, boxes: list, limit: int = 512) -> dict:
    return {"version": 1, "items": items, "boxes": boxes, "max_packages": limit}


def sample() -> dict:
    return problem(
        [
            item("a", 7, 4, "north"),
            item("b", 6, 4, "north"),
            item("c", 4, 5, "north"),
            item("d", 3, 2, "south"),
            item("e", 20, 25, "north"),
            item("f", 2, 2, "north", True),
            item("g", 2, 1, "north"),
        ],
        [
            box("small", 10, 8, item_limit=3, tare_g=2, cost_cents=100, stock=2),
            box("large", 20, 20, item_limit=5, tare_g=2, cost_cents=180, stock=1),
        ],
        3,
    )


def normalized(value: dict) -> dict:
    return {
        "version": 1,
        "items": sorted(copy.deepcopy(value["items"]), key=lambda row: row["id"]),
        "boxes": sorted(copy.deepcopy(value["boxes"]), key=lambda row: row["id"]),
        "max_packages": value["max_packages"],
    }


def oracle(value: dict) -> dict:
    """Recompute capacities from contents; never use the application's cached record totals."""
    value = normalized(value)
    kinds = {row["id"]: row for row in value["boxes"]}
    stock = {name: row["stock"] for name, row in kinds.items()}
    parcels, rejected = [], []
    for row in sorted(value["items"], key=lambda row: (-row["weight_g"], -row["volume_cm3"], row["id"])):
        possible = []
        for position, (kind, contents) in enumerate(parcels):
            carton = kinds[kind]
            if (
                not row["separate"]
                and not any(old["separate"] for old in contents)
                and contents[0]["destination"] == row["destination"]
                and len(contents) < carton["item_limit"]
                and sum(old["weight_g"] for old in [*contents, row]) + carton["tare_g"] <= carton["weight_limit_g"]
                and sum(old["volume_cm3"] for old in [*contents, row]) <= carton["volume_limit_cm3"]
            ):
                possible.append(position)
        if possible:
            parcels[possible[0]][1].append(row)
            continue
        fits = [
            name
            for name, carton in kinds.items()
            if row["weight_g"] + carton["tare_g"] <= carton["weight_limit_g"]
            and row["volume_cm3"] <= carton["volume_limit_cm3"]
        ]
        available = [name for name in fits if stock[name] > 0]
        reason = (
            "no_box_fits"
            if not fits
            else (
                "stock_exhausted" if not available else "package_limit" if len(parcels) == value["max_packages"] else ""
            )
        )
        if reason:
            rejected.append(
                {"item": row, "reason": reason, "eligible_box_types": fits, "available_box_types": available}
            )
            continue
        kind = min(
            available,
            key=lambda name: (
                kinds[name]["cost_cents"],
                kinds[name]["weight_limit_g"] - kinds[name]["tare_g"],
                kinds[name]["volume_limit_cm3"],
                kinds[name]["item_limit"],
                name,
            ),
        )
        stock[kind] -= 1
        parcels.append((kind, [row]))
    packages = []
    for number, (kind, contents) in enumerate(parcels, start=1):
        carton = kinds[kind]
        weight = sum(row["weight_g"] for row in contents)
        volume = sum(row["volume_cm3"] for row in contents)
        packages.append(
            {
                "id": "package-" + str(number),
                "box": kind,
                "destination": contents[0]["destination"],
                "items": contents,
                "item_weight_g": weight,
                "gross_weight_g": weight + carton["tare_g"],
                "volume_cm3": volume,
                "cost_cents": carton["cost_cents"],
                "remaining_weight_g": carton["weight_limit_g"] - carton["tare_g"] - weight,
                "remaining_volume_cm3": carton["volume_limit_cm3"] - volume,
                "remaining_slots": carton["item_limit"] - len(contents),
            }
        )
    packed = [row for _, contents in parcels for row in contents]
    return {
        "version": 1,
        "heuristic": "weight-first-first-fit-v1",
        "status": "partial" if rejected else "complete",
        "packages": packages,
        "rejected": rejected,
        "inventory": [
            {"box": name, "opened": carton["stock"] - stock[name], "remaining": stock[name]}
            for name, carton in kinds.items()
        ],
        "totals": {
            "items": len(value["items"]),
            "assigned": len(packed),
            "rejected": len(rejected),
            "packages": len(parcels),
            "item_weight_g": sum(row["weight_g"] for row in packed),
            "gross_weight_g": sum(row["weight_g"] for row in packed)
            + sum(kinds[kind]["tare_g"] for kind, _ in parcels),
            "volume_cm3": sum(row["volume_cm3"] for row in packed),
            "cost_cents": sum(kinds[kind]["cost_cents"] for kind, _ in parcels),
            "rejected_weight_g": sum(row["item"]["weight_g"] for row in rejected),
            "rejected_volume_cm3": sum(row["item"]["volume_cm3"] for row in rejected),
        },
        "problem_sha256": hashlib.sha256((canonical(value) + "\n").encode()).hexdigest(),
    }


def invariants(value: dict, report: dict) -> None:
    originals = {row["id"]: row for row in value["items"]}
    kinds = {row["id"]: row for row in value["boxes"]}
    seen = []
    assert len(report["packages"]) <= value["max_packages"]
    for package in report["packages"]:
        carton = kinds[package["box"]]
        rows = package["items"]
        assert rows and len(rows) <= carton["item_limit"]
        assert sum(row["weight_g"] for row in rows) + carton["tare_g"] <= carton["weight_limit_g"]
        assert sum(row["volume_cm3"] for row in rows) <= carton["volume_limit_cm3"]
        assert all(row["destination"] == package["destination"] for row in rows)
        assert not any(row["separate"] for row in rows) or len(rows) == 1
        for row in rows:
            assert row == originals[row["id"]]
            seen.append(row["id"])
    for rejection in report["rejected"]:
        assert rejection["reason"] in ["no_box_fits", "stock_exhausted", "package_limit"]
        assert rejection["item"] == originals[rejection["item"]["id"]]
        seen.append(rejection["item"]["id"])
    assert len(seen) == len(set(seen)) and set(seen) == set(originals)
    for name, carton in kinds.items():
        assert sum(package["box"] == name for package in report["packages"]) <= carton["stock"]
    totals = report["totals"]
    assert totals["assigned"] + totals["rejected"] == len(originals)
    assert totals["item_weight_g"] + totals["rejected_weight_g"] == sum(row["weight_g"] for row in originals.values())
    assert totals["volume_cm3"] + totals["rejected_volume_cm3"] == sum(row["volume_cm3"] for row in originals.values())
    return


@dataclass
class Fixture:
    work: Path
    config: dict

    @property
    def path(self) -> Path:
        return self.work / "parcel-job.json"

    @property
    def output(self) -> Path:
        return self.work / self.config["output"]

    def save(self) -> None:
        self.path.write_text(json.dumps(self.config, ensure_ascii=False))
        return

    def settings(self, mode: str = "write", **extra: str) -> dict:
        return {
            "PARCEL_CONFIG": str(self.path),
            "PARCEL_MODE": mode,
            "PARCEL_FAIL": "",
            "PARCEL_PAUSE": "",
            "PARCEL_CONTINUE": "",
            **extra,
        }


def fixture(directory: Path, name: str, value: dict, **changes: object) -> Fixture:
    work = directory / name
    work.mkdir(parents=True)
    fix = Fixture(work, {"problem": "packing.json", "output": "parcel-plan", **changes})
    (work / "packing.json").write_text(json.dumps(value, ensure_ascii=False))
    fix.save()
    return fix


def outputs(fix: Fixture, report: dict) -> dict:
    value = json.loads((fix.work / fix.config["problem"]).read_bytes())
    lines = ["Status: " + report["status"], "Totals: " + canonical(report["totals"])]
    for parcel in report["packages"]:
        lines.append(
            parcel["id"]
            + " box="
            + canonical(parcel["box"])
            + " destination="
            + canonical(parcel["destination"])
            + " items="
            + canonical([row["id"] for row in parcel["items"]])
        )
    lines += ["Rejected " + canonical(row["item"]["id"]) + ": " + row["reason"] for row in report["rejected"]]
    expected = {
        "problem.json": (canonical(normalized(value)) + "\n").encode(),
        "plan.json": (canonical(report) + "\n").encode(),
        "packages.jsonl": "".join(canonical(row) + "\n" for row in report["packages"]).encode(),
        "rejected.jsonl": "".join(canonical(row) + "\n" for row in report["rejected"]).encode(),
        "plan.txt": ("\n".join(lines) + "\n").encode(),
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


def success(app: Application, fix: Fixture, mode: str = "write") -> dict:
    source = fix.work / fix.config["problem"]
    before = [fix.path.read_bytes(), source.read_bytes()]
    value = json.loads(before[1])
    expected = oracle(value)
    result = app.run(fix.work, fix.settings(mode), timeout=120)
    assert result.returncode in [0, 1] and not result.stderr, (fix.work, result)
    observed = json.loads(result.stdout)
    assert observed == expected, (fix.work, observed, expected)
    invariants(value, observed)
    assert result.returncode == int(bool(expected["rejected"]))
    assert result.stdout == canonical(expected) + "\n"
    assert before == [fix.path.read_bytes(), source.read_bytes()]
    if mode == "write":
        outputs(fix, observed)
    else:
        assert not fix.output.exists()
    assert not list(fix.work.glob(".parcel-plan-*"))
    return observed


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
    assert not list(fix.work.glob(".parcel-plan-*"))
    return


def scenarios(app: Application, directory: Path) -> dict:
    rng = random.Random(64064)
    observations = []
    dimensions = [(1, 1), (1, 3), (3, 1), (3, 3)]
    count = 0
    for number, values in enumerate(itertools.product(dimensions, repeat=3)):
        rows = [item(name, weight, volume) for name, (weight, volume) in zip(["a", "b", "c"], values, strict=True)]
        for limit in range(4):
            value = problem(rows, [box("standard", 4, 4, item_limit=2, stock=3)], limit)
            observations.append(success(app, fixture(directory, f"dimensions-{number}-{limit}", value), "preview"))
            count += 1
    for separate, destination in itertools.product(range(8), repeat=2):
        rows = [
            item(name, destination="a" if destination & (1 << index) else "b", separate=bool(separate & (1 << index)))
            for index, name in enumerate(["a", "b", "c"])
        ]
        observations.append(
            success(
                app,
                fixture(
                    directory,
                    f"separation-{separate}-{destination}",
                    problem(rows, [box("standard", 4, 4, item_limit=3, stock=3)]),
                ),
                "preview",
            )
        )
    print(app.engine + " parcel planner: 256 capacity and 64 separation combinations passed", flush=True)
    cases = [
        problem([], [], 0),
        problem([], [box("unused", stock=0)]),
        problem([item("a")], []),
        problem([item("a")], [box("empty", stock=0)]),
        problem([item("a")], [box("unused")], 0),
        sample(),
        problem(
            [
                item("é", destination="世界"),
                item("e\u0301", destination="世界"),
                item("🙂", destination="line\nbreak", separate=True),
            ],
            [box("箱")],
        ),
        problem([item("exact", 8, 10), item("heavy", 9, 1), item("large", 1, 11)], [box("tare", 10, 10, tare_g=2)]),
    ]
    ties = [
        ([box("cheap", 20, cost_cents=1), box("costly", 2, cost_cents=2)], "cheap"),
        ([box("smaller", 2), box("larger", 3)], "smaller"),
        ([box("tare", 10, tare_g=8), box("light", 3)], "tare"),
        ([box("small-volume", 10, 2), box("large-volume", 10, 3)], "small-volume"),
        ([box("one-slot", item_limit=1), box("two-slots", item_limit=2)], "one-slot"),
        ([box("é"), box("e\u0301")], "e\u0301"),
    ]
    for cartons, wanted in ties:
        value = problem([item("a")], cartons)
        assert oracle(value)["packages"][0]["box"] == wanted
        cases.append(value)
    for _ in range(48):
        cartons = []
        for index in range(rng.randrange(5)):
            weight = rng.randint(1, 60)
            cartons.append(
                box(
                    "b" + str(index),
                    weight,
                    rng.randint(1, 60),
                    tare_g=rng.randrange(weight),
                    item_limit=rng.randint(1, 6),
                    cost_cents=rng.randrange(5),
                    stock=rng.randrange(8),
                )
            )
        rows = [
            item(
                "i" + str(index).zfill(2),
                rng.randint(1, 40),
                rng.randint(1, 40),
                rng.choice(["a", "b", "世界"]),
                rng.randrange(5) == 0,
            )
            for index in range(rng.randrange(37))
        ]
        cases.append(problem(rows, cartons, rng.randrange(17)))
    for index, value in enumerate(cases):
        first = fixture(directory, "case-" + str(index), value)
        report = success(app, first)
        observations.append(report)
        shuffled = copy.deepcopy(value)
        rng.shuffle(shuffled["items"])
        rng.shuffle(shuffled["boxes"])
        second = fixture(directory, "permuted-" + str(index), shuffled)
        assert success(app, second) == report
        assert {p.name: p.read_bytes() for p in first.output.iterdir()} == {
            p.name: p.read_bytes() for p in second.output.iterdir()
        }
    return {
        "exhaustive_capacity_cases": count,
        "exhaustive_separation_cases": 64,
        "other_problems": len(cases),
        "generated_problems": 48,
        "permutations": len(cases),
        "box_tie_rules": len(ties),
        "reports_sha256": hashlib.sha256(canonical(observations).encode()).hexdigest(),
    }


def heuristic_limit(app: Application, directory: Path) -> dict:
    rows = [item(name, weight) for name, weight in zip("abcdef", [6, 5, 3, 2, 2, 2], strict=True)]
    value = problem(rows, [box("ten", 10, 100, stock=2)])
    report = success(app, fixture(directory, "nonoptimal", value))
    assert [[row["id"] for row in package["items"]] for package in report["packages"]] == [["a", "c"], ["b", "d", "e"]]
    assert report["rejected"][0]["item"]["id"] == "f" and report["rejected"][0]["reason"] == "stock_exhausted"
    # A different feasible two-package partition proves that the greedy rejection is not global infeasibility.
    by_id = {row["id"]: row for row in rows}
    alternative = [["a", "d", "e"], ["b", "c", "f"]]
    assert sorted(itertools.chain.from_iterable(alternative)) == sorted(by_id)
    assert all(sum(by_id[name]["weight_g"] for name in group) == 10 for group in alternative)
    value["boxes"][0]["stock"] = 3
    larger = success(app, fixture(directory, "extra-stock", value))
    assert larger["status"] == "complete" and len(larger["packages"]) == 3
    # Existing capacity remains usable after both inventory and package-count limits have been reached.
    value = problem([item("a", 3), item("b", 2), item("c", 1)], [box("one", 6, 3, stock=1)], 1)
    assert success(app, fixture(directory, "reuse-after-limits", value))["totals"]["assigned"] == 3
    return {
        "counterexample": True,
        "alternative_package_count": 2,
        "heuristic_package_count_with_extra_stock": 3,
        "existing_capacity_after_limits": True,
    }


def invalid_inputs(app: Application, directory: Path) -> int:
    base = problem([item("a")], [box("b")])
    variants = [None, [], {}, {**base, "extra": 1}]
    variants += [{key: value for key, value in base.items() if key != missing} for missing in base]
    for key, values in {
        "version": [0, 2, True, 1.0, None],
        "max_packages": [-1, 513, True, 1.0, None],
        "items": [None, {}, "", True],
        "boxes": [None, {}, "", True],
    }.items():
        variants += [{**base, key: value} for value in values]
    for collection, row in [("items", base["items"][0]), ("boxes", base["boxes"][0])]:
        malformed = [None, [], {}, {**row, "extra": 1}]
        malformed += [{key: value for key, value in row.items() if key != missing} for missing in row]
        malformed += [{**row, "id": value} for value in ["", "a\x00", "x" * 129, "🙂" * 129, None, True, 1, [], {}]]
        variants += [{**base, collection: [value]} for value in malformed]
        variants.append({**base, collection: [row, row]})
    for field, values in {
        "destination": ["", "a\x00", "x" * 129, "🙂" * 129, None, True, 1, [], {}],
        "weight_g": [0, -1, 10**9 + 1, True, 1.0, "1", None],
        "volume_cm3": [0, -1, 10**9 + 1, True, 1.0, "1", None],
        "separate": [0, 1, "false", None, [], {}],
    }.items():
        variants += [{**base, "items": [{**base["items"][0], field: value}]} for value in values]
    for field, values in {
        "weight_limit_g": [0, -1, 10**9 + 1, True, 1.0, "1", None],
        "volume_limit_cm3": [0, -1, 10**9 + 1, True, 1.0, "1", None],
        "item_limit": [0, -1, 513, True, 1.0, None],
        "tare_g": [-1, 10, 11, 10**9 + 1, True, 1.0, None],
        "cost_cents": [-1, 10**9 + 1, True, 1.0, None],
        "stock": [-1, 513, True, 1.0, None],
    }.items():
        variants += [{**base, "boxes": [{**base["boxes"][0], field: value}]} for value in values]
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
    failure(app, fixture(directory, "mode", base), "invalid packing mode", PARCEL_MODE="bad")
    count += 1
    for name in ["packing.json", "parcel-job.json"]:
        for index, raw in enumerate([b"\xff", b"{", b"[] trailing", b"[NaN]", b"[Infinity]", b'{"a":1,"a":2}']):
            fix = fixture(directory, f"raw-{name}-{index}", base)
            (fix.work / name).write_bytes(raw)
            failure(app, fix)
            count += 1
    return count


def limits(app: Application, directory: Path) -> dict:
    rows = [item(str(index).zfill(3) + "🙂" * 125, 10**9, 10**9, "🙂" * 128) for index in range(512)]
    cartons = [box("🙂" * 128, 10**9, 10**9, cost_cents=10**9)]
    report = success(app, fixture(directory, "maximum-packages", problem(rows, cartons)))
    assert len(report["packages"]) == 512 and report["status"] == "complete"
    assert (
        report["totals"]["gross_weight_g"]
        == report["totals"]["volume_cm3"]
        == report["totals"]["cost_cents"]
        == 512 * 10**9
    )
    failure(app, fixture(directory, "items-above", problem([*rows, item("extra")], cartons)), "item count")
    cartons = [box("b" + str(index), stock=0) for index in range(16)]
    success(app, fixture(directory, "box-types-exact", problem([item("a")], cartons)))
    failure(app, fixture(directory, "box-types-above", problem([], [*cartons, box("extra")])), "box type count")
    report = success(
        app,
        fixture(
            directory, "item-slots-exact", problem([item(str(i)) for i in range(512)], [box("many", 512, 512, stock=1)])
        ),
    )
    assert len(report["packages"]) == 1 and report["packages"][0]["remaining_slots"] == 0
    report = success(
        app, fixture(directory, "tare-exact", problem([item("a")], [box("heavy", 10**9, tare_g=10**9 - 1)]))
    )
    assert report["packages"][0]["gross_weight_g"] == 10**9 and report["packages"][0]["remaining_weight_g"] == 0
    # Equality is accepted on each axis; exceeding any one axis creates another package.
    for field in ["weight", "volume", "count"]:
        carton = box(
            "test",
            2 if field == "weight" else 10,
            2 if field == "volume" else 10,
            item_limit=2 if field == "count" else 10,
        )
        report = success(
            app, fixture(directory, "boundary-" + field, problem([item("a"), item("b"), item("c")], [carton]))
        )
        assert [len(row["items"]) for row in report["packages"]] == [2, 1]
    large_items = [item(str(index).zfill(3) + "🙂" * 125, destination="🙂" * 128) for index in range(512)]
    large_boxes = [box(str(index).zfill(3) + "🙂" * 125) for index in range(16)]
    failure(app, fixture(directory, "output-above", problem(large_items, large_boxes, 0)), "output file exceeds 8 MiB")
    for name, maximum in [("parcel-job.json", 65536), ("packing.json", 4194304)]:
        fix = fixture(directory, "bytes-" + name, sample())
        path = fix.work / name
        raw = path.read_bytes()
        path.write_bytes(raw + b" " * (maximum - len(raw)))
        success(app, fix, "preview")
        path.write_bytes(raw + b" " * (maximum + 1 - len(raw)))
        failure(app, fix, "byte limit")
        path.write_bytes(raw)
    return {
        "items": 512,
        "box_types": 16,
        "packages": 512,
        "stock_per_type": 512,
        "items_per_package": 512,
        "name_characters": 128,
        "name_bytes": 512,
        "dimension_maximum": 10**9,
        "cost_per_package": 10**9,
        "maximum_aggregate": 512 * 10**9,
        "config_bytes": 65536,
        "problem_bytes": 4194304,
        "output_file_bytes": 8388608,
    }


def paused(app: Application, fix: Fixture) -> subprocess.Popen:
    process = subprocess.Popen(
        app.command,
        cwd=fix.work,
        env=app.environment(fix.settings(PARCEL_PAUSE="ready", PARCEL_CONTINUE=str(fix.work / "continue"))),
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
        "plan.json",
        "packages.jsonl",
        "rejected.jsonl",
        "plan.txt",
        "manifest.json",
        "ready",
        "published",
    ]
    for point in points:
        fix = fixture(directory, "fault-" + point, sample())
        reference = success(app, fix, "preview")
        result = app.run(fix.work, fix.settings(PARCEL_FAIL=point))
        assert result.returncode == 2 and "injected failure: " + point in result.stderr and not result.stdout
        assert not list(fix.work.glob(".parcel-plan-*"))
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
            assert not list(fix.work.glob(".parcel-plan-*"))
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
    abandoned = list(fix.work.glob(".parcel-plan-*"))
    assert len(abandoned) == 1
    old = {path.name: path.read_bytes() for path in abandoned[0].iterdir()}
    result = app.run(fix.work, fix.settings())
    assert result.returncode == 1 and not result.stderr
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
            fix.output.symlink_to(fix.work / ("packing.json" if name == "symlink" else "missing"))
        else:
            fix.config["output"] = "packing.json" if name == "same-problem" else "parcel-job.json"
            fix.save()
        failure(app, fix, "output directory already exists")
    for name in ["packing.json", "parcel-job.json"]:
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
    limitation = heuristic_limit(app, directory / "heuristic")
    print(app.engine + " parcel planner: heuristic decisions, conservation and permutations passed", flush=True)
    invalid = invalid_inputs(app, directory / "invalid")
    bounds = limits(app, directory / "limits")
    faults = publication(app, directory / "publication")
    path_cases = paths(app, directory / "paths")
    print(app.engine + " parcel planner: validation, capacity, publication and path checks passed", flush=True)
    return {
        **cases,
        "heuristic_limit": limitation,
        "invalid_inputs": invalid,
        "limits": bounds,
        "publication_cases": faults,
        "path_cases": path_cases,
    }
