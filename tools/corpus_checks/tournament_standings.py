"""Complete tournament acceptance against independent per-team scans and sporting-rank counts."""

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
from .tournament_fixture import canonical, digest, display, document, expected
from .tournament_fixture import fixture as match


def save(path: Path, value: object) -> None:
    path.write_bytes(canonical(value))
    return  # noqa: PLR1711


def files_at(path: Path) -> dict[str, bytes]:
    return {p.name: p.read_bytes() for p in path.iterdir() if p.is_file()}


def fixture(root: Path, source: dict | None = None) -> dict:
    root.mkdir(parents=True, exist_ok=True)
    config = {"version": 1, "mode": "rank", "input": "fixtures.json", "output": "output"}
    save(root / "tournament-job.json", config)
    save(root / "fixtures.json", document() if source is None else source)
    return config


def inspect(root: Path, config: dict) -> dict:
    imported = json.loads((root / config["input"]).read_bytes())
    source = imported["source"] if config["mode"] == "verify" else imported
    results = expected(source)
    archive = {"version": 1, "source": source, "results": results}
    counts = {key: results[key] for key in ["teams", "played", "scheduled", "leaders"]}
    lines = [display(results["title"]), "Rank\tTeam\tP\tW\tD\tL\tGF\tGA\tGD\tPts"]
    for row in results["standings"]:
        values = [str(row["rank"]), display(row["name"])]
        values += [
            str(row[key])
            for key in ["played", "won", "drawn", "lost", "goals_for", "goals_against", "difference", "points"]
        ]
        lines.append("\t".join(values))
    files = {
        "archive.json": canonical(archive),
        "fixtures.json": canonical(source),
        "standings.json": canonical(results),
        "table.txt": ("\n".join(lines) + "\n").encode(),
        "report.json": canonical(
            {"version": 1, "mode": config["mode"], "summary": counts, "archive_sha256": digest(canonical(archive))}
        ),
        "replay.json": canonical({"version": 1, "mode": "verify", "input": "archive.json", "output": "replayed"}),
        "rank.json": canonical({"version": 1, "mode": "rank", "input": "fixtures.json", "output": "ranked"}),
    }
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


def run(app: Application, root: Path, config: dict, selected: str = "tournament-job.json") -> dict:
    unchanged = {root / name: (root / name).read_bytes() for name in [selected, config["input"]]}
    result = app.run(root, {"TOURNAMENT_CONFIG": str(root / selected)}, timeout=120)
    assert result.returncode == 0 and not result.stderr, (root, result)
    archive = inspect(root, config)
    report = json.loads((root / config["output"] / "report.json").read_bytes())
    assert result.stdout == canonical(report["summary"]).decode()
    assert all(path.read_bytes() == raw for path, raw in unchanged.items())
    return archive


def consume(app: Application, root: Path, name: str) -> dict:
    return run(app, root, json.loads((root / name).read_bytes()), name)


def reject(app: Application, root: Path, needle: str = "") -> None:
    result = app.run(root, {}, timeout=30)
    assert result.returncode == 2 and result.stderr and not result.stdout, (root, result)
    assert needle in result.stderr
    assert not (root / "output").exists() and not list(root.glob(".tournament-*"))
    return  # noqa: PLR1711


def edit_export(app: Application, root: Path, source: dict, stem: str) -> dict:
    original = files_at(root)
    config = json.loads((root / "rank.json").read_bytes())
    config.update(input=stem + "-fixtures.json", output=stem)
    save(root / config["input"], source)
    save(root / (stem + "-job.json"), config)
    result = run(app, root, config, selected=stem + "-job.json")
    assert all((root / name).read_bytes() == raw for name, raw in original.items())
    return result


def metrics(archive: dict) -> list[dict]:
    return [
        {key: value for key, value in row.items() if key != "contributions"} for row in archive["results"]["standings"]
    ]


def season(ids: list[str], fixtures: list[dict]) -> dict:
    return {
        "version": 1,
        "title": "Test season",
        "teams": [{"id": name, "name": name} for name in ids],
        "fixtures": fixtures,
    }


def semantics(app: Application, root: Path) -> dict:
    archive = run(app, root, fixture(root))
    rows = archive["results"]["standings"]
    fields = ["id", "rank", "played", "won", "drawn", "lost", "goals_for", "goals_against", "difference", "points"]
    assert [tuple(row[key] for key in fields) for row in rows] == [
        ("A", 1, 2, 1, 1, 0, 3, 1, 2, 4),
        ("C", 2, 3, 1, 1, 1, 5, 4, 1, 4),
        ("B", 3, 3, 1, 1, 1, 2, 3, -1, 4),
        ("D", 4, 2, 0, 1, 1, 1, 3, -2, 1),
    ]
    exported = files_at(root / "output")
    assert consume(app, root / "output", "replay.json") == archive
    assert consume(app, root / "output", "rank.json") == archive
    assert files_at(root / "output") == exported
    changed = json.loads((root / "output/fixtures.json").read_bytes())
    changed["fixtures"][2].update(home_score=0, away_score=2)
    tied = edit_export(app, root / "output", changed, "tied")
    assert [(r["id"], r["rank"]) for r in tied["results"]["standings"]] == [("C", 1), ("A", 2), ("D", 2), ("B", 4)]
    assert consume(app, root / "output/tied", "replay.json") == tied
    changed = json.loads((root / "output/tied/fixtures.json").read_bytes())
    changed["fixtures"][0].update(home_score=0, away_score=2)
    broken = edit_export(app, root / "output/tied", changed, "broken")
    assert [(r["id"], r["rank"]) for r in broken["results"]["standings"]] == [("B", 1), ("C", 2), ("D", 3), ("A", 4)]
    changed = json.loads((root / "output/tied/broken/fixtures.json").read_bytes())
    changed["fixtures"][0].update(home_score=2, away_score=0)
    changed["fixtures"][2].update(home_score=None, away_score=None)
    assert edit_export(app, root / "output/tied/broken", changed, "restored") == archive
    cases = [
        (season([], []), []),
        (season(["A"], []), [("A", 1)]),
        (season(["z", "a", "A"], []), [("A", 1), ("a", 1), ("z", 1)]),
        (season(["A", "B"], [match("ab", "A", "B", None, None)]), [("A", 1), ("B", 1)]),
        (
            season(
                ["A", "B", "C"],
                [match("ab", "A", "B", 1, 0), match("ac", "A", "C", 0, 0), match("bc", "B", "C", 100, 0)],
            ),
            [("A", 1), ("B", 2), ("C", 3)],
        ),
        (
            season(["A", "B", "C", "D"], [match("ab", "A", "B", 2, 0), match("cd", "C", "D", 3, 1)]),
            [("C", 1), ("A", 2), ("D", 3), ("B", 4)],
        ),
        (
            season(["A", "B", "C", "D"], [match("ab", "A", "B", 2, 0), match("cd", "C", "D", 2, 0)]),
            [("A", 1), ("C", 1), ("B", 3), ("D", 3)],
        ),
        (
            season(
                ["A", "B", "C"], [match("ab", "A", "B", 0, 0), match("ac", "A", "C", 0, 0), match("bc", "B", "C", 0, 0)]
            ),
            [("A", 1), ("B", 1), ("C", 1)],
        ),
    ]
    for index, (source, ranks) in enumerate(cases):
        source["title"] = " Café\tLeague\n東京 "
        for row in source["teams"]:
            row["name"] = " Same\nＮａｍｅ "
        work = root / ("hand-" + str(index))
        current = run(app, work, fixture(work, source))
        assert [(r["id"], r["rank"]) for r in current["results"]["standings"]] == ranks
    return {
        "hand_seasons": 1 + len(cases),
        "result_edits": 3,
        "all_sporting_tie_breakers": True,
        "shared_competition_ranks": True,
        "stable_identifier_display_ties": True,
        "empty_partial_and_unplayed_seasons": True,
        "unicode_labels_and_duplicate_display_names": True,
        "actual_replay_ranking_and_edited_exports": True,
        "archive_sha256": digest(exported["archive.json"]),
    }


def generated(app: Application, root: Path) -> dict:
    rng = random.Random(108)
    hashes, fixture_count, played_count = [], 0, 0
    for batch in range(32):
        ids = ["t" + str(i) for i in range(2 + batch % 15)]
        matches = []
        for left, right in itertools.combinations(ids, 2):
            if rng.randrange(5) == 0:
                continue
            if rng.randrange(2):
                left, right = right, left
            scores = (None, None) if rng.randrange(4) == 0 else (rng.randrange(10), rng.randrange(10))
            matches.append(match("m" + str(len(matches)), left, right, *scores))
        rng.shuffle(ids)
        rng.shuffle(matches)
        source = season(ids, matches)
        work = root / str(batch)
        first = run(app, work, fixture(work, source))
        fixture_count += len(matches)
        played_count += first["results"]["played"]
        hashes.append(digest(canonical(first)))
        reordered = copy.deepcopy(source)
        rng.shuffle(reordered["teams"])
        rng.shuffle(reordered["fixtures"])
        reverse = run(app, work / "reordered", fixture(work / "reordered", reordered))
        assert metrics(reverse) == metrics(first)
        swapped = copy.deepcopy(source)
        for row in swapped["fixtures"]:
            row["home"], row["away"] = row["away"], row["home"]
            row["home_score"], row["away_score"] = row["away_score"], row["home_score"]
        reverse = run(app, work / "swapped", fixture(work / "swapped", swapped))
        assert reverse["results"] == first["results"]
        changed = json.loads((work / "output/fixtures.json").read_bytes())
        for row in changed["fixtures"]:
            row.update(home_score=rng.randrange(4), away_score=rng.randrange(4))
        edited = edit_export(app, work / "output", changed, "edited")
        assert consume(app, work / "output/edited", "replay.json") == edited
        hashes.append(digest(canonical(edited)))
    return {
        "seed": 108,
        "seasons": 32,
        "scheduled_fixtures": fixture_count,
        "played_fixtures": played_count,
        "team_and_fixture_order_invariance": 32,
        "home_away_invariance": 32,
        "exported_seasons_edited_and_replayed": 32,
        "independent_team_scan_and_rank_count_oracle": True,
        "conservation_checks": True,
        "archives_sha256": digest("\n".join(hashes).encode()),
    }


def invalid(app: Application, root: Path) -> dict:
    rejected_sources = []

    def modified(path: tuple, value: object, delete: bool = False) -> None:
        source = document()
        target = source
        for key in path[:-1]:
            target = target[key]
        if delete:
            del target[path[-1]]
        else:
            target[path[-1]] = value
        rejected_sources.append(source)
        return  # noqa: PLR1711

    for version in [0, 2, True, 1.0, "1", None]:
        modified(("version",), version)
    for path in [("title",), ("teams", 0, "name")]:
        for value in [
            None,
            1,
            True,
            [],
            {},
            "",
            " \t\n ",
            "x" * 101,
            "\ufb01" * 51,
            "x\x00y",
            "x\x7fy",
            "x\x80y",
            "x\x9fy",
        ]:
            modified(path, value)
    for path in [("teams", 0, "id"), ("fixtures", 0, "id"), ("fixtures", 0, "home"), ("fixtures", 0, "away")]:
        for value in [None, False, 1, "", "1first", "bad:name", "two words", "équipe", "a" * 33, "a\n"]:
            modified(path, value)
    for path in [("fixtures", 0, "home_score"), ("fixtures", 0, "away_score")]:
        for value in [None, True, False, 1.0, "1", [], {}, -1, 10001, 2**63]:
            modified(path, value)
    for path in [("teams",), ("fixtures",)]:
        for value in [None, True, {}, "rows", [None], [1], [[]]]:
            modified(path, value)
    for path in [
        ("version",),
        ("title",),
        ("teams",),
        ("fixtures",),
        ("teams", 0, "id"),
        ("teams", 0, "name"),
        ("fixtures", 0, "id"),
        ("fixtures", 0, "home"),
        ("fixtures", 0, "away"),
        ("fixtures", 0, "home_score"),
        ("fixtures", 0, "away_score"),
    ]:
        modified(path, None, True)
    for path in [(), ("teams", 0), ("fixtures", 0)]:
        source = document()
        target = source
        for key in path:
            target = target[key]
        target["extra"] = True
        rejected_sources.append(source)
    modified(("teams", 1, "id"), "A")
    modified(("fixtures", 0, "home"), "unknown")
    modified(("fixtures", 0, "away"), "A")
    modified(("fixtures", 1, "id"), "ab")
    source = document()
    source["fixtures"][1].update(home="B", away="A")
    rejected_sources.append(source)
    # Unplayed entries still require both registered teams and unique pairings.
    modified(("fixtures", 2, "home"), "unknown")
    modified(("fixtures", 2, "away_score"), 0)
    rejected_sources += [None, [], 42, {}, True]
    for index, source in enumerate(rejected_sources):
        work = root / ("source-" + str(index))
        fixture(work, source)
        # fixture(None) selects the sample by default, so preserve explicit JSON null here.
        save(work / "fixtures.json", source)
        reject(app, work)
    configs = []
    valid = {"version": 1, "mode": "rank", "input": "fixtures.json", "output": "output"}
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
    ]:
        configs.append(dict(valid, **{key: value}))
    configs += [{key: value for key, value in valid.items() if key != "mode"}, dict(valid, extra=True)]
    for index, config in enumerate(configs):
        work = root / ("request-" + str(index))
        fixture(work)
        save(work / "tournament-job.json", config)
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
            name = "tournament-job.json" if slot == "request" else "fixtures.json"
            if slot == "archive":
                name = "archive.json"
                config.update(mode="verify", input=name)
                save(work / "tournament-job.json", config)
            (work / name).write_bytes(raw)
            reject(app, work)
    archive = {"version": 1, "source": document(), "results": expected(document())}
    changes = [
        (("version",), 1.0),
        (("results", "played"), True),
        (("results", "standings", 0, "points"), 4.0),
        (("results", "standings", 0, "rank"), True),
        (("results", "standings", 0, "difference"), 99),
        (("results", "standings", 0, "contributions", 0, "points"), 3.0),
        (("results", "standings", 0, "contributions", 0, "goals_against"), False),
        (("results", "leaders"), ["B"]),
        (("results", "unplayed"), 0),
        (("source", "fixtures", 0, "home_score"), 5),
        (("results", "standings"), list(reversed(archive["results"]["standings"]))),
        (("results", "title"), "changed"),
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
        save(work / "tournament-job.json", config)
        save(work / "archive.json", changed)
        reject(app, work)
    return {
        "invalid_sources": len(rejected_sources),
        "invalid_requests": len(configs),
        "invalid_json_per_input": len(malformed),
        "tampered_archives": len(changes),
        "strict_cached_numeric_types": True,
    }


def limits(app: Application, root: Path) -> dict:
    ids = ["t" + str(i) for i in range(32)]
    matches = [
        match("m" + str(i), left, right, 10000, 0) for i, (left, right) in enumerate(itertools.combinations(ids, 2))
    ]
    source = season(ids, matches)
    source["title"] = "😀" * 100
    for team in source["teams"]:
        team["name"] = "界" * 100
    work = root / "maximum"
    archive = run(app, work, fixture(work, source))
    rows = archive["results"]["standings"]
    assert len(rows) == 32 and archive["results"]["played"] == 496 and archive["results"]["unscheduled"] == 0
    assert rows[0]["id"] == "t0" and rows[0]["points"] == 93 and rows[0]["goals_for"] == 310000
    assert rows[-1]["id"] == "t31" and rows[-1]["difference"] == -310000
    assert sum(len(row["contributions"]) for row in rows) == 992
    changed = json.loads((work / "output/fixtures.json").read_bytes())
    for row in changed["fixtures"]:
        row["away_score"] = 10000
    tied = edit_export(app, work / "output", changed, "all-draws")
    assert all(
        row["rank"] == 1 and row["points"] == 31 and row["goals_for"] == row["goals_against"] == 310000
        for row in tied["results"]["standings"]
    )
    assert tied["results"]["leaders"] == sorted(ids)
    for label in ["teams", "fixtures", "score"]:
        over = copy.deepcopy(source)
        if label == "teams":
            over["teams"].append({"id": "extra", "name": "Extra"})
        elif label == "fixtures":
            over["fixtures"].append(over["fixtures"][0])
        else:
            over["fixtures"][0]["home_score"] = 10001
        work = root / ("over-" + label)
        fixture(work, over)
        reject(app, work)
    work = root / "identifier-limit"
    source = season(["A" * 32, "B" * 32], [match("M" * 32, "A" * 32, "B" * 32, 0, 0)])
    run(app, work, fixture(work, source))
    work = root / "exact-bytes"
    config = fixture(work)
    for name, size in [("tournament-job.json", 65536), ("fixtures.json", 2097152)]:
        path = work / name
        path.write_bytes(path.read_bytes().ljust(size, b" "))
    archive = run(app, work, config)
    for name, size in [("tournament-job.json", 65536), ("fixtures.json", 2097152)]:
        work = root / ("over-" + name)
        fixture(work)
        path = work / name
        path.write_bytes(path.read_bytes().ljust(size + 1, b" "))
        reject(app, work)
    for over in [False, True]:
        work = root / ("archive-over" if over else "archive-limit")
        config = fixture(work)
        config.update(mode="verify", input="archive.json")
        save(work / "tournament-job.json", config)
        (work / "archive.json").write_bytes(canonical(archive).ljust(16777216 + int(over), b" "))
        if over:
            reject(app, work)
        else:
            run(app, work, config)
    return {
        "teams": 32,
        "fixtures": 496,
        "contributions": 992,
        "score": 10000,
        "team_points": 93,
        "team_goals": 310000,
        "shared_rank_leaders": 32,
        "label_characters": 100,
        "identifier_characters": 32,
        "request_bytes": 65536,
        "source_bytes": 2097152,
        "archive_bytes": 16777216,
    }


def publication(app: Application, root: Path) -> dict:
    rows = document()
    for stage in ["staged", "published"]:
        work = root / ("fault-" + stage)
        config = fixture(work, rows)
        result = app.run(work, {"TOURNAMENT_FAULT": stage})
        assert result.returncode == 2 and result.stderr and not result.stdout
        assert not list(work.glob(".tournament-*")) and (work / "output").exists() == (stage == "published")
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
            env=app.environment(
                {"TOURNAMENT_PAUSE": stage, "TOURNAMENT_RELEASE": str(release), "PYTHONUNBUFFERED": "1"}
            ),
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
                assert len(list(work.glob(".tournament-*"))) == (1 if stage == "staged" else 0)
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
                    name = "tournament-job.json" if mutation == "request" else "fixtures.json"
                    with (work / name).open("ab") as stream:
                        stream.write(b" ")
                release.touch()
                stdout, stderr = process.communicate(timeout=10)
                assert process.returncode == 2 and stderr and not stdout and not list(work.glob(".tournament-*"))
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
        ["tournament-job.json", "fixtures.json"], ["symlink", "hardlink", "fifo", "directory", "unreadable"]
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
            output.symlink_to(work / "tournament-job.json")
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
        print(app.engine + " tournament standings " + name + ": passed", flush=True)
    return observations
