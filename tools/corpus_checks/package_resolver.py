"""Whole-project process tests with independent exhaustive dependency and conflict oracles."""

from __future__ import annotations

import copy
import hashlib
import json
import os
import select
import subprocess
import time
from pathlib import Path

from .common import Application
from .resolver_fixture import (
    INDEX,
    ROOTS,
    SELECTED,
    binary_tree,
    matches,
    repositories,
    solutions,
    valid,
    witness,
)


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def save(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False) + "\n")
    return  # noqa: PLR1711


def fixture(root: Path, index: dict | None = None, roots: dict | None = None, **options: object) -> dict:
    root.mkdir(parents=True, exist_ok=True)
    save(root / "index.json", INDEX if index is None else index)
    config = {
        "version": 1,
        "mode": "resolve",
        "index": "index.json",
        "output": "result",
        "roots": ROOTS if roots is None else roots,
        "max_steps": 1000,
        "max_conflicts": 32,
        **options,
    }
    save(root / "resolver-job.json", config)
    return config


def inspect_bundle(root: Path, config: dict) -> dict:
    output = root / config["output"]
    raw_index = (root / config["index"]).read_bytes()
    index = json.loads(raw_index)
    report = json.loads((output / "report.json").read_bytes())
    outcome = report["outcome"]
    assert set(report) == {"version", "index_sha256", "roots", "outcome"}
    assert report["version"] == 1 and report["index_sha256"] == digest(raw_index)
    assert (output / "index.json").read_bytes() == raw_index
    assert set(outcome) == {"status", "selected", "statistics", "conflicts", "next_state", "errors"}
    names = {"index.json", "report.json", "report.txt", "replay.json"}
    replay = json.loads((output / "replay.json").read_bytes())
    if config["mode"] == "resolve":
        assert report["roots"] == config["roots"] and not outcome["errors"]
        assert replay == dict(config, index="index.json", output="replayed")
        stats = outcome["statistics"]
        assert 1 <= stats["states"] <= config["max_steps"]
        assert (
            stats["recorded_conflicts"] == len(outcome["conflicts"]) == min(stats["conflicts"], config["max_conflicts"])
        )
        for item in outcome["conflicts"]:
            witness(index, config["roots"], item)
        if outcome["status"] == "resolved":
            assert valid(index, config["roots"], outcome["selected"]) and outcome["next_state"] is None
        else:
            assert outcome["selected"] == {}
            if outcome["status"] == "budget_exhausted":
                assert stats["states"] == config["max_steps"] and stats["pending_states"] > 0
                assert isinstance(outcome["next_state"], dict)
            else:
                assert outcome["status"] == "unsatisfiable" and stats["pending_states"] == 0
                assert outcome["next_state"] is None
    else:
        original_lock = (root / config["lock"]).read_bytes()
        lock = json.loads(original_lock)
        assert report["roots"] == lock["roots"] and outcome["selected"] == lock["packages"]
        expected = valid(index, lock["roots"], lock["packages"]) and lock["index_sha256"] == digest(raw_index)
        assert (outcome["status"] == "valid_lock") == expected
        assert bool(outcome["errors"]) != expected
        assert outcome["statistics"] == {"states": 0, "conflicts": 0, "recorded_conflicts": 0, "pending_states": 0}
        assert not outcome["conflicts"] and outcome["next_state"] is None
        if not expected:
            names.add("input-lock.json")
            assert (output / "input-lock.json").read_bytes() == original_lock
        assert replay == {
            "version": 1,
            "mode": "verify",
            "index": "index.json",
            "output": "replayed",
            "lock": "lock.json" if expected else "input-lock.json",
        }
    if outcome["status"] in {"resolved", "valid_lock"}:
        names.update(["lock.json", "verify.json"])
        lock = json.loads((output / "lock.json").read_bytes())
        assert lock == {
            "version": 1,
            "index_sha256": digest(raw_index),
            "roots": report["roots"],
            "packages": outcome["selected"],
        }
        assert json.loads((output / "verify.json").read_bytes()) == {
            "version": 1,
            "mode": "verify",
            "index": "index.json",
            "output": "verified",
            "lock": "lock.json",
        }
    manifest = json.loads((output / "manifest.json").read_bytes())
    assert set(manifest) == names and {p.name for p in output.iterdir()} == names | {"manifest.json"}
    for name in names:
        data = (output / name).read_bytes()
        assert manifest[name] == {"bytes": len(data), "sha256": digest(data)}
    text = (output / "report.txt").read_text()
    assert text.startswith("Package constraint resolver: " + outcome["status"] + "\n")
    assert "not claimed to be a minimal unsatisfiable core" in text
    return report


def run(app: Application, root: Path, config: dict, timeout: int = 30) -> dict:
    result = app.run(root, {}, timeout=timeout)
    report = inspect_bundle(root, config)
    status = report["outcome"]["status"]
    code = 0 if status in {"resolved", "valid_lock"} else 3 if status == "budget_exhausted" else 1
    assert result.returncode == code and result.stdout == status + "\n" and not result.stderr, result
    return report


def semantics(app: Application, root: Path) -> dict:
    work = root / "hand"
    hand = run(app, work, fixture(work))
    assert hand["outcome"]["selected"] == SELECTED
    assert hand["outcome"]["statistics"] == {"states": 8, "conflicts": 2, "recorded_conflicts": 2, "pending_states": 1}
    permuted = {
        "version": 1,
        "packages": {name: list(reversed(entries)) for name, entries in reversed(list(INDEX["packages"].items()))},
    }
    work = root / "permuted"
    other = run(app, work, fixture(work, permuted, dict(reversed(list(ROOTS.items())))))
    assert other["outcome"] == hand["outcome"] and other["index_sha256"] != hand["index_sha256"]
    work = root / "retained"
    capped = run(app, work, fixture(work, max_conflicts=1))
    assert capped["outcome"]["conflicts"] == hand["outcome"]["conflicts"][:1]
    assert capped["outcome"]["statistics"]["conflicts"] == 2
    versions = ["0.0.0", "0.0.3", "0.0.4", "0.2.3", "0.3.0", "1.9.0", "1.10.0", "2.0.0"]
    index = {"version": 1, "packages": {"A": [{"version": v, "dependencies": {}} for v in reversed(versions)]}}
    requirements = [
        "*",
        "1.9.0",
        "=1.10.0",
        ">1.9.0",
        ">=1.9.0",
        "<0.0.3",
        "<=0.0.3",
        "^0.0.0",
        "^0.0.3",
        "^0.2.3",
        "^1.0.0",
        "~1.9.0",
        "~0.2.0",
        ">=1.0.0 <2.0.0",
        "0.0.3 || 1.9.0",
        ">2.0.0",
        " >=1.0.0  <2.0.0 ",
        "* * * * || 0.0.0 || ^0.0.3 || ~0.2.3",
    ]
    for number, requirement in enumerate(requirements):
        work = root / f"grammar-{number}"
        report = run(app, work, fixture(work, index, {"A": requirement}))["outcome"]
        allowed = [v for v in versions if matches(v, requirement)]
        assert report["selected"] == ({"A": allowed[-1]} if allowed else {})
        assert report["status"] == ("resolved" if allowed else "unsatisfiable")
    cases = [
        ({"version": 1, "packages": {}}, {}, "resolved"),
        ({"version": 1, "packages": {}}, {"Absent": "*"}, "unsatisfiable"),
        ({"version": 1, "packages": {"A": []}}, {"A": "*"}, "unsatisfiable"),
        (
            {"version": 1, "packages": {"A": [{"version": "1.0.0", "dependencies": {"A": "^1.0.0"}}]}},
            {"A": "*"},
            "resolved",
        ),
        (
            {
                "version": 1,
                "packages": {
                    "A": [{"version": "1.0.0", "dependencies": {"B": "*"}}],
                    "B": [{"version": "1.0.0", "dependencies": {"A": "*"}}],
                },
            },
            {"A": "*"},
            "resolved",
        ),
        (
            {
                "version": 1,
                "packages": {
                    "A": [
                        {"version": "1.0.0", "dependencies": {"A": "^2.0.0"}},
                        {"version": "2.0.0", "dependencies": {"A": "^1.0.0"}},
                    ]
                },
            },
            {"A": "*"},
            "unsatisfiable",
        ),
    ]
    for number, (index, roots, status) in enumerate(cases):
        work = root / f"graph-{number}"
        report = run(app, work, fixture(work, index, roots))["outcome"]
        assert report["status"] == status
        assert bool(solutions(index, roots)) == (status == "resolved")
    counts = {"resolved": 0, "unsatisfiable": 0}
    for number, (index, roots) in enumerate(repositories()):
        work = root / f"exhaustive-{number}"
        report = run(app, work, fixture(work, index, roots))["outcome"]
        expected = solutions(index, roots)
        assert report["status"] == ("resolved" if expected else "unsatisfiable"), (index, roots, report, expected)
        if expected:
            assert report["selected"] in expected
        counts[report["status"]] += 1
    assert all(counts.values())
    return {
        "hand_backtracking_states": 8,
        "grammar_cases": len(requirements),
        "graph_cases": len(cases),
        "exhaustive_repositories": counts,
        "order_invariant_outcome": True,
        "every_conflict_independently_checked": True,
    }


def lock_fixture(root: Path, choices: dict | None = None, **changes: object) -> dict:
    fixture(root)
    lock = {
        "version": 1,
        "index_sha256": digest((root / "index.json").read_bytes()),
        "roots": ROOTS,
        "packages": SELECTED if choices is None else choices,
        **changes,
    }
    save(root / "lock.json", lock)
    config = {"version": 1, "mode": "verify", "index": "index.json", "output": "result", "lock": "lock.json"}
    save(root / "resolver-job.json", config)
    return config


def lock_cases(app: Application, root: Path) -> dict:
    variants = [
        (SELECTED, {}, []),
        ({"Client": "1.0.0", "Extension": "2.0.0"}, {}, ["missing_package"]),
        (dict(SELECTED, Http="2.0.0"), {}, ["constraint"]),
        (dict(SELECTED, Http="9.0.0"), {}, ["unknown_release"]),
        (dict(SELECTED, Unknown="1.0.0"), {}, ["unknown_release"]),
        (dict(SELECTED, Unused="1.0.0"), {}, ["missing_package", "unreachable_package"]),
        (SELECTED, {"index_sha256": "0" * 64}, ["index_digest"]),
        ({}, {"roots": {}}, []),
    ]
    for number, (choices, changes, kinds) in enumerate(variants):
        work = root / str(number)
        config = lock_fixture(work, choices, **changes)
        report = run(app, work, config)
        assert [e["kind"] for e in report["outcome"]["errors"]] == kinds
    work = root / "disconnected-cycle"
    config = lock_fixture(work, dict(SELECTED, X="1.0.0", Y="1.0.0"))
    index = copy.deepcopy(INDEX)
    for a, b in [("X", "Y"), ("Y", "X")]:
        index["packages"][a] = [{"version": "1.0.0", "dependencies": {b: "*"}}]
    save(work / "index.json", index)
    lock = json.loads((work / "lock.json").read_bytes())
    lock["index_sha256"] = digest((work / "index.json").read_bytes())
    save(work / "lock.json", lock)
    assert run(app, work, config)["outcome"]["errors"] == [
        {"kind": "unreachable_package", "package": "X"},
        {"kind": "unreachable_package", "package": "Y"},
    ]
    work = root / "identity"
    config = lock_fixture(work)
    save(work / "index.json", dict(reversed(list(INDEX.items()))))
    assert run(app, work, config)["outcome"]["errors"] == [{"kind": "index_digest"}]
    return {"lock_variants": len(variants) + 2, "exact_index_identity": True, "disconnected_cycles_rejected": True}


def reject(app: Application, root: Path) -> None:
    result = app.run(root, {}, timeout=10)
    assert result.returncode == 2 and result.stderr and not result.stdout, (root, result)
    assert not (root / "result").exists()
    return  # noqa: PLR1711


def invalid(app: Application, root: Path) -> dict:
    variants = [
        ("version", True),
        ("version", 2),
        ("mode", "install"),
        ("roots", []),
        ("roots", {"1bad": "*"}),
        ("roots", {"A" * 33: "*"}),
        ("roots", {f"P{i}": "*" for i in range(17)}),
        ("roots", {"A": True}),
        ("index", ""),
        ("index", "\x00"),
        ("index", "missing"),
        ("output", ""),
        ("output", "\x00"),
        ("extra", 1),
    ]
    for key in ["max_steps", "max_conflicts"]:
        variants += [(key, value) for value in [0, -1, True, 1.5, 10001 if key == "max_steps" else 129]]
    for number, (key, value) in enumerate(variants):
        work = root / f"config-{number}"
        config = fixture(work)
        config[key] = value
        save(work / "resolver-job.json", config)
        reject(app, work)
    invalid_versions = [
        "1",
        "1.2",
        "v1.2.3",
        "01.2.3",
        "1.02.3",
        "1.2.03",
        "-1.2.3",
        "1.2.3-alpha",
        "1.2.3+build",
        "2147483648.0.0",
        "99999999999.0.0",
        "1.2.3.4",
        "１.2.3",
        "1.2.3\n",
    ]
    invalid_ranges = [
        "",
        " ",
        "1.2",
        "x",
        "1.x",
        "!=1.0.0",
        "=>1.0.0",
        "1.0.0 - 2.0.0",
        "1.0.0,2.0.0",
        "1.0.0\t<2.0.0",
        "1.0.0\n",
        "* | *",
        "* ||",
        "|| *",
        "* * * * *",
        "*||*||*||*||*",
        "*" + " " * 256,
        *invalid_versions,
    ]
    for number, value in enumerate(invalid_ranges):
        work = root / f"range-{number}"
        fixture(work, roots={"A": value})
        reject(app, work)
    indexes = [
        {},
        {"version": True, "packages": {}},
        {"version": 1, "packages": []},
        {"version": 1, "packages": {"A": {}}},
        {"version": 1, "packages": {"bad.name": []}},
        {"version": 1, "packages": {f"P{i}": [] for i in range(17)}},
    ]
    entries = [{"version": value, "dependencies": {}} for value in [*invalid_versions, 1, True]]
    entries += [
        {"version": "1.0.0", "dependencies": []},
        {"version": "1.0.0", "dependencies": {"A": "x"}},
        {"version": "1.0.0", "dependencies": {f"P{i}": "*" for i in range(9)}},
        {"version": "1.0.0"},
        {"version": "1.0.0", "dependencies": {}, "extra": 1},
    ]
    indexes += [{"version": 1, "packages": {"Unused": [entry]}} for entry in entries]
    indexes += [
        {"version": 1, "packages": {"Unused": [{"version": "1.0.0", "dependencies": {}}] * 2}},
        {"version": 1, "packages": {"Unused": [{"version": f"{i}.0.0", "dependencies": {}} for i in range(9)]}},
    ]
    for number, index in enumerate(indexes):
        work = root / f"index-{number}"
        fixture(work, index, {})
        reject(app, work)
    locks = [
        ("version", True),
        ("version", 2),
        ("index_sha256", "A" * 64),
        ("index_sha256", "f" * 63),
        ("roots", []),
        ("packages", []),
        ("packages", {"A": "1"}),
        ("packages", {"1bad": "1.0.0"}),
        ("packages", {f"P{i}": "1.0.0" for i in range(17)}),
        ("extra", 1),
    ]
    for number, (key, value) in enumerate(locks):
        work = root / f"lock-{number}"
        lock_fixture(work, **{key: value})
        reject(app, work)
    malformed = [b"{", b"\xff", b'{"version":1,"version":1}', b"[]", b"null"]
    document_cases = 0
    for name, limit in [("resolver-job.json", 65536), ("index.json", 524288), ("lock.json", 65536)]:
        for number, data in enumerate([*malformed, b" " * (limit + 1)]):
            work = root / f"raw-{name}-{number}"
            lock_fixture(work)
            (work / name).write_bytes(data)
            reject(app, work)
            document_cases += 1
    return {
        "configurations": len(variants),
        "invalid_ranges": len(invalid_ranges),
        "invalid_indexes": len(indexes),
        "invalid_locks": len(locks),
        "malformed_or_oversized_documents": document_cases,
    }


def limits(app: Application, root: Path) -> dict:
    index = {"version": 1, "packages": {"A": [{"version": "1.0.0", "dependencies": {}}]}}
    for budget, status in [(1, "budget_exhausted"), (2, "resolved")]:
        work = root / f"budget-{budget}"
        report = run(app, work, fixture(work, index, {"A": "*"}, max_steps=budget))["outcome"]
        assert report["status"] == status
        if budget == 1:
            assert report["next_state"] == {"A": "1.0.0"}
    work = root / "exact-unsatisfiable"
    config = fixture(work, {"version": 1, "packages": {}}, {"Missing": "*"}, max_steps=1)
    assert run(app, work, config)["outcome"]["status"] == "unsatisfiable"
    for count, budget, status, states, conflicts in [
        (7, 1000, "unsatisfiable", 511, 256),
        (13, 10000, "budget_exhausted", 10000, None),
    ]:
        work = root / f"tree-{count}"
        index, roots = binary_tree(count)
        config = fixture(work, index, roots, max_steps=budget, max_conflicts=128)
        report = run(app, work, config, 120)["outcome"]
        assert report["status"] == status and report["statistics"]["states"] == states
        assert report["statistics"]["recorded_conflicts"] == 128
        if conflicts is not None:
            assert report["statistics"]["conflicts"] == conflicts
    names = ["P" + str(i).zfill(31) for i in range(16)]
    max_version = "2147483647.2147483647.2147483647"
    requirement = ("* * * * || * * * * || * * * * || * * * *").ljust(256)
    index = {
        "version": 1,
        "packages": {
            name: [
                {"version": f"{j}.0.0", "dependencies": {other: requirement for other in names[:8]}} for j in range(7)
            ]
            + [{"version": max_version, "dependencies": {other: requirement for other in names[:8]}}]
            for name in names
        },
    }
    work = root / "maximum"
    config = fixture(work, index, dict.fromkeys(names, "^" + max_version), max_steps=10000, max_conflicts=128)
    for name, limit in [("resolver-job.json", 65536), ("index.json", 524288)]:
        path = work / name
        assert len(path.read_bytes()) <= limit
        path.write_bytes(path.read_bytes().ljust(limit, b" "))
    report = run(app, work, config, 120)
    assert report["outcome"]["selected"] == dict.fromkeys(names, max_version)
    exported = work / "result"
    config = json.loads((exported / "verify.json").read_bytes())
    (exported / "lock.json").write_bytes((exported / "lock.json").read_bytes().ljust(65536, b" "))
    save(exported / "resolver-job.json", config)
    assert run(app, exported, config)["outcome"]["status"] == "valid_lock"
    for number, value in enumerate(["^0.2147483647.2147483647", "^0.0.2147483647", "~2147483647.2147483647.0"]):
        text = value[1:]
        index = {"version": 1, "packages": {"A": [{"version": text, "dependencies": {}}]}}
        work = root / f"upper-bound-{number}"
        assert run(app, work, fixture(work, index, {"A": value}))["outcome"]["selected"] == {"A": text}
    return {
        "search_states": 10000,
        "retained_conflicts": 128,
        "complete_unsatisfiable_tree_states": 511,
        "packages_and_roots": 16,
        "releases_per_package": 8,
        "dependencies_per_release": 8,
        "requirement_characters": 256,
        "alternatives": 4,
        "terms_per_alternative": 4,
        "name_characters": 32,
        "version_component": 2147483647,
        "configuration_bytes": 65536,
        "index_bytes": 524288,
        "lock_bytes": 65536,
    }


def paused(app: Application, root: Path, label: str) -> subprocess.Popen:
    process = subprocess.Popen(
        app.command,
        cwd=root,
        env=app.environment({"RESOLVER_PAUSE": label, "RESOLVER_RELEASE": str(root.parent / (root.name + "-release"))}),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        ready, _, _ = select.select([process.stdout], [], [], 0.05)
        if ready:
            line = process.stdout.readline()
            if line.strip() == "PAUSED " + label:
                return process
            if not line:
                break
    process.kill()
    raise AssertionError(("pause failed", process.communicate()))


def publication(app: Application, root: Path) -> dict:
    for label in ["staged", "published"]:
        for mode in ["fault", "kill"]:
            work = root / (label + "-" + mode)
            config = fixture(work)
            if mode == "fault":
                result = app.run(work, {"RESOLVER_FAULT": label})
                assert result.returncode == 2 and "injected failure" in result.stderr
                assert not list(work.glob(".resolver-*"))
            else:
                process = paused(app, work, label)
                process.kill()
                process.communicate(timeout=5)
                assert process.returncode == -9
            if label == "published":
                inspect_bundle(work, config)
            else:
                assert not (work / "result").exists()
            if label == "staged" and mode == "fault":
                run(app, work, config)
    changes = ["index.json", "resolver-job.json", "lock.json", "removed", "replaced", "competitor"]
    for change in changes:
        work = root / change
        lock_fixture(work)
        process = paused(app, work, "staged")
        try:
            if change == "competitor":
                (work / "result").mkdir()
                (work / "result/sentinel").write_bytes(b"keep")
            elif change == "removed":
                (work / "index.json").unlink()
            elif change == "replaced":
                target = work / "index.json"
                target.rename(work / "old-index.json")
                target.symlink_to(work / "old-index.json")
            else:
                (work / change).write_bytes(b"{}")
            (work.parent / (work.name + "-release")).touch()
            stdout, stderr = process.communicate(timeout=10)
            assert process.returncode == 2 and stderr and not stdout
            if change == "competitor":
                assert (work / "result/sentinel").read_bytes() == b"keep"
                assert len(list((work / "result").iterdir())) == 1
            else:
                assert not (work / "result").exists()
            assert not list(work.glob(".resolver-*"))
        finally:
            if process.poll() is None:
                process.kill()
                process.communicate()
    return {"atomic_fault_or_kill_boundaries": 4, "input_changes_or_output_races": len(changes)}


def filesystem(app: Application, root: Path) -> dict:
    cases = [
        (name, kind)
        for name in ["resolver-job.json", "index.json", "lock.json"]
        for kind in ["symlink", "hardlink", "fifo", "unreadable"]
    ]
    for number, (name, kind) in enumerate(cases):
        work = root / str(number)
        lock_fixture(work)
        target = work / name
        sentinel = work / "sentinel"
        sentinel.write_bytes(b"keep")
        if kind == "unreadable":
            assert os.getuid() != 0
            target.chmod(0)
        else:
            target.unlink()
            if kind == "symlink":
                target.symlink_to(sentinel)
            elif kind == "hardlink":
                os.link(sentinel, target)
            else:
                os.mkfifo(target)
        try:
            reject(app, work)
            assert sentinel.read_bytes() == b"keep"
        finally:
            if kind == "unreadable":
                target.chmod(0o600)
    for kind in ["file", "directory", "symlink", "permission"]:
        work = root / kind
        fixture(work)
        target = work / "result"
        sentinel = work / "sentinel"
        sentinel.write_bytes(b"keep")
        if kind == "file":
            target.write_bytes(b"original")
        elif kind == "directory":
            target.mkdir()
        elif kind == "symlink":
            target.symlink_to(sentinel)
        else:
            work.chmod(0o500)
        try:
            result = app.run(work, {}, timeout=10)
            assert result.returncode == 2 and result.stderr and not result.stdout
            assert sentinel.read_bytes() == b"keep"
            if kind == "file":
                assert target.read_bytes() == b"original"
            if kind == "directory":
                assert not list(target.iterdir())
            if kind == "symlink":
                assert target.is_symlink()
            if kind == "permission":
                assert not target.exists()
        finally:
            work.chmod(0o700)
    return {"guarded_paths_and_permissions": len(cases) + 4}


def check(app: Application, directory: Path) -> dict:
    return {
        "semantics": semantics(app, directory / "semantics"),
        "locks": lock_cases(app, directory / "locks"),
        "invalid": invalid(app, directory / "invalid"),
        "limits": limits(app, directory / "limits"),
        "publication": publication(app, directory / "publication"),
        "filesystem": filesystem(app, directory / "filesystem"),
        "independent_exhaustive_and_interval_oracles": True,
    }
