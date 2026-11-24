"""Exhaustive temporal walks and chronological connection scans for timetable acceptance."""

# ruff: noqa: PLR1711 - explicit repository returns

from __future__ import annotations

import copy
import datetime as dt
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


def instant(seconds: int = 0, microseconds: int = 0) -> str:
    return (
        dt.datetime(2026, 10, 12, 23, 30, tzinfo=dt.timezone.utc)
        + dt.timedelta(seconds=seconds, microseconds=microseconds)
    ).isoformat(timespec="microseconds")


def timestamp(text: str) -> dt.datetime:
    return dt.datetime.fromisoformat(text.replace("Z", "+00:00")).astimezone(dt.timezone.utc)


def utc(text: str) -> str:
    return timestamp(text).isoformat(timespec="microseconds")


def connection(identifier: str, origin: str, destination: str, departure: str, arrival: str) -> dict:
    return {"id": identifier, "from": origin, "to": destination, "departure": departure, "arrival": arrival}


def timetable(stations: dict, connections: list) -> dict:
    return {
        "version": 1,
        "stations": [{"id": name, "transfer_seconds": delay} for name, delay in stations.items()],
        "connections": connections,
    }


def request(identifier: str, origin: str, destination: str, departure: str) -> dict:
    return {"id": identifier, "from": origin, "to": destination, "depart_after": departure}


def sample() -> dict:
    return timetable(
        {"A": 100, "B": 300, "C": 600, "D": 0, "Island": 0},
        [
            connection("ab", "A", "B", "2026-10-12T23:50:00Z", "2026-10-13T00:10:00Z"),
            connection("bc-missed", "B", "C", "2026-10-13T00:14:59Z", "2026-10-13T00:30:00Z"),
            connection("bc", "B", "C", "2026-10-13T00:15:00Z", "2026-10-13T00:40:00Z"),
            connection("direct", "A", "C", "2026-10-12T23:55:00Z", "2026-10-13T01:30:00Z"),
            connection("ab-late", "A", "B", "2026-10-13T00:05:00Z", "2026-10-13T00:20:00Z"),
            connection("cd-missed", "C", "D", "2026-10-13T00:45:00Z", "2026-10-13T01:00:00Z"),
            connection("cd", "C", "D", "2026-10-13T00:50:00Z", "2026-10-13T01:05:00Z"),
        ],
    )


def jobs() -> list:
    return [
        request("overnight", "A", "D", "2026-10-12T23:40:00Z"),
        request("missed", "A", "C", "2026-10-13T00:06:00Z"),
        request("same", "B", "B", "2026-10-13T00:10:00Z"),
        request("island", "A", "Island", "2026-10-12T23:40:00Z"),
        request("exact", "B", "C", "2026-10-13T00:14:59Z"),
    ]


def normalized(value: dict) -> dict:
    result = copy.deepcopy(value)
    result["stations"].sort(key=lambda row: row["id"])
    for row in result["connections"]:
        for field in ["departure", "arrival"]:
            row[field] = utc(row[field])
    result["connections"].sort(key=lambda row: (row["departure"], row["arrival"], row["id"]))
    return result


def normalized_jobs(rows: list) -> list:
    return [{**row, "depart_after": utc(row["depart_after"])} for row in rows]


@dataclass
class Fixture:
    work: Path
    config: dict

    @property
    def path(self) -> Path:
        return self.work / "timetable-job.json"

    @property
    def output(self) -> Path:
        return self.work / self.config["output"]

    def save(self) -> None:
        self.path.write_text(json.dumps(self.config, ensure_ascii=False))
        return

    def settings(self, mode: str = "write", **extra: str) -> dict:
        return {
            "TIMETABLE_CONFIG": str(self.path),
            "TIMETABLE_MODE": mode,
            "TIMETABLE_FAIL": "",
            "TIMETABLE_PAUSE": "",
            "TIMETABLE_CONTINUE": "",
            **extra,
        }


def fixture(directory: Path, name: str, value: dict, rows: list, **changes: object) -> Fixture:
    work = directory / name
    work.mkdir(parents=True)
    fix = Fixture(
        work, {"timetable": "timetable.json", "requests": "requests.json", "output": "journey-plan", **changes}
    )
    (work / "timetable.json").write_text(json.dumps(value, ensure_ascii=False))
    (work / "requests.json").write_text(json.dumps(rows, ensure_ascii=False))
    fix.save()
    return fix


def earliest(value: dict, query: dict) -> dict:
    transfers = {row["id"]: row["transfer_seconds"] for row in value["stations"]}
    connections = [
        {**row, "departure": timestamp(row["departure"]), "arrival": timestamp(row["arrival"])}
        for row in value["connections"]
    ]
    origin, beginning = query["from"], timestamp(query["depart_after"])
    found = {origin: beginning}
    if len(connections) <= 12:
        # Enumerate all feasible temporal walks, including returns to a station; time strictly increases.
        pending = [(origin, beginning, True)]
        while pending:
            station, time, first = pending.pop()
            board = time + dt.timedelta(seconds=0 if first else transfers[station])
            for edge in connections:
                if edge["from"] == station and edge["departure"] >= board:
                    target, arrival = edge["to"], edge["arrival"]
                    found[target] = min(found.get(target, arrival), arrival)
                    pending.append((target, arrival, False))
    else:
        # A single chronological connection scan, independent of the application's station heap.
        for edge in sorted(connections, key=lambda row: (row["departure"], row["arrival"], row["id"])):
            source, target = edge["from"], edge["to"]
            if source not in found:
                continue
            ready = found[source] + dt.timedelta(seconds=0 if source == origin else transfers[source])
            if edge["departure"] >= ready:
                found[target] = min(found.get(target, edge["arrival"]), edge["arrival"])
    return {name: time.isoformat(timespec="microseconds") for name, time in found.items()}


def validate(value: dict, rows: list, report: dict) -> None:
    value = normalized(value)
    rows = normalized_jobs(rows)
    hashes = {
        name: hashlib.sha256((canonical(data) + "\n").encode()).hexdigest()
        for name, data in [("timetable.json", value), ("requests.json", rows)]
    }
    assert set(report) == {"version", "input_sha256", "counts", "journeys"}
    assert report["version"] == 1 and report["input_sha256"] == hashes and len(report["journeys"]) == len(rows)
    transfers = {row["id"]: row["transfer_seconds"] for row in value["stations"]}
    connections = {row["id"]: row for row in value["connections"]}
    found_count = 0
    for query, observed in zip(rows, report["journeys"], strict=True):
        assert set(observed) == {
            "id",
            "from",
            "to",
            "depart_after",
            "status",
            "arrival",
            "legs",
            "transfers",
            "reachable",
            "stats",
        }
        assert {key: observed[key] for key in query} == query
        expected = earliest(value, query)
        assert observed["reachable"] == [{"station": name, "arrival": expected[name]} for name in sorted(expected)]
        arrival = expected.get(query["to"])
        assert observed["arrival"] == arrival and observed["status"] == ("found" if arrival else "unreachable")
        assert observed["transfers"] == max(0, len(observed["legs"]) - 1)
        current, time = query["from"], timestamp(query["depart_after"])
        visited = {current}
        for index, leg in enumerate(observed["legs"]):
            assert set(leg) == {"id", "from", "to", "departure", "arrival", "transfer_seconds", "ready_at"}
            assert {key: leg[key] for key in connections[leg["id"]]} == connections[leg["id"]]
            assert leg["from"] == current and leg["to"] not in visited
            delay = transfers[current] if index else 0
            ready = time + dt.timedelta(seconds=delay)
            assert leg["transfer_seconds"] == delay and leg["ready_at"] == ready.isoformat(timespec="microseconds")
            assert timestamp(leg["departure"]) >= ready and timestamp(leg["arrival"]) > timestamp(leg["departure"])
            current, time = leg["to"], timestamp(leg["arrival"])
            visited.add(current)
        if arrival:
            found_count += 1
            assert current == query["to"] and time == timestamp(arrival)
        else:
            assert observed["legs"] == []
        stats = observed["stats"]
        assert set(stats) == {"settled", "pushed", "popped", "stale", "connections_considered", "missed_connections"}
        assert all(type(n) is int and n >= 0 for n in stats.values())
        assert (
            stats["settled"] == len(expected)
            and stats["pushed"] == stats["popped"] == stats["settled"] + stats["stale"]
        )
        considered = [edge for edge in value["connections"] if edge["from"] in expected]
        missed = [
            edge
            for edge in considered
            if timestamp(edge["departure"])
            < timestamp(expected[edge["from"]])
            + dt.timedelta(seconds=0 if edge["from"] == query["from"] else transfers[edge["from"]])
        ]
        assert stats["connections_considered"] == len(considered) and stats["missed_connections"] == len(missed)
        assert 1 <= stats["pushed"] <= len(considered) - len(missed) + 1
    assert report["counts"] == {"requests": len(rows), "found": found_count, "unreachable": len(rows) - found_count}
    return


def outputs(fix: Fixture, report: dict) -> dict:
    value = json.loads((fix.work / fix.config["timetable"]).read_bytes())
    rows = json.loads((fix.work / fix.config["requests"]).read_bytes())
    text = []
    for result in report["journeys"]:
        lines = [
            "Journey " + canonical(result["id"]) + ": " + result["status"],
            canonical(result["from"]) + " -> " + canonical(result["to"]) + " after " + result["depart_after"],
        ]
        for leg in result["legs"]:
            lines.append(
                canonical(leg["id"])
                + ": "
                + canonical(leg["from"])
                + " "
                + leg["departure"]
                + " -> "
                + canonical(leg["to"])
                + " "
                + leg["arrival"]
                + "; ready "
                + leg["ready_at"]
            )
        lines.append("Arrival: " + canonical(result["arrival"]))
        text.append("\n".join(lines) + "\n")
    expected = {
        "timetable.json": (canonical(normalized(value)) + "\n").encode(),
        "requests.json": (canonical(normalized_jobs(rows)) + "\n").encode(),
        "journeys.json": (canonical(report) + "\n").encode(),
        "journeys.jsonl": "".join(canonical(row) + "\n" for row in report["journeys"]).encode(),
        "itineraries.txt": "\n".join(text).encode(),
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
    paths = [fix.path, fix.work / fix.config["timetable"], fix.work / fix.config["requests"]]
    original = [path.read_bytes() for path in paths]
    result = app.run(fix.work, fix.settings(mode), timeout=180)
    assert result.returncode in [0, 1] and not result.stderr, (fix.work, result)
    report = json.loads(result.stdout)
    validate(json.loads(original[1]), json.loads(original[2]), report)
    assert result.returncode == int(report["counts"]["unreachable"] > 0)
    assert result.stdout == canonical(report) + "\n" and original == [path.read_bytes() for path in paths]
    if mode == "write":
        outputs(fix, report)
    else:
        assert not fix.output.exists()
    assert not list(fix.work.glob(".timetable-*"))
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
    assert not list(fix.work.glob(".timetable-*"))
    return


def scenarios(app: Application, directory: Path) -> dict:
    options = [
        connection("ab", "A", "B", instant(0), instant(10)),
        connection("ab-fast", "A", "B", instant(5), instant(8)),
        connection("bc", "B", "C", instant(10), instant(20)),
        connection("bc-fast", "B", "C", instant(12), instant(15)),
        connection("ac", "A", "C", instant(2), instant(30)),
        connection("ca", "C", "A", instant(25), instant(35)),
    ]
    rows = [
        request(str(i), a, b, instant(start)) for i, (a, b, start) in enumerate(itertools.product("ABC", "ABC", [0, 6]))
    ]
    observations = []
    for mask in range(64):
        for delay in [0, 2, 5]:
            value = timetable({"A": 0, "B": delay, "C": 2}, [row for i, row in enumerate(options) if mask & (1 << i)])
            observations.append(success(app, fixture(directory, "exhaustive-" + str(len(observations)), value, rows)))
    print(app.engine + " timetable: exhaustive subsets, transfer thresholds and all endpoint pairs passed", flush=True)
    cases = [
        (sample(), jobs()),
        (timetable({}, []), []),
        (timetable({"A": 86400}, []), [request("same", "A", "A", instant())]),
        (timetable({"A": 0, "B": 0}, []), [request("none", "A", "B", instant())]),
        (
            timetable(
                {"A": 0, "B": 0},
                [
                    connection("loop", "A", "A", instant(), instant(1)),
                    connection("ab", "A", "B", instant(2), instant(3)),
                    connection("back", "B", "A", instant(4), instant(5)),
                ],
            ),
            [request("cycle", "A", "B", instant())],
        ),
        (
            timetable(
                {"A": 0, "B": 300, "C": 0},
                [
                    connection("ab", "A", "B", instant(), instant(10, 1)),
                    connection("almost", "B", "C", instant(310), instant(400)),
                    connection("exact", "B", "C", instant(310, 1), instant(400)),
                ],
            ),
            [request("transfer", "A", "C", instant()), request("initial", "B", "C", instant(310))],
        ),
        (
            timetable(
                {"A": 0, "B": 86400, "C": 0},
                [
                    connection("ab", "A", "B", "2028-02-28T23:59:59Z", "2028-02-29T00:00:00Z"),
                    connection("bc", "B", "C", "2028-03-01T00:00:00Z", "2028-03-01T00:00:01Z"),
                ],
            ),
            [request("leap", "A", "C", "2028-02-28T23:59:59Z")],
        ),
        (
            timetable(
                {"A": 0, "B": 0, "C": 0, "X": 0},
                [
                    connection("ax", "A", "X", instant(), instant(2)),
                    connection("xb", "X", "B", instant(2), instant(5)),
                    connection("ab", "A", "B", instant(), instant(6)),
                    connection("bc", "B", "C", instant(10), instant(20)),
                ],
            ),
            [request("earliest-not-fewest", "A", "C", instant())],
        ),
        (
            timetable(
                {"S": 0, "A": 0, "B": 0, "T": 0},
                [
                    connection("sa", "S", "A", instant(), instant(5)),
                    connection("sb", "S", "B", instant(), instant(5)),
                    connection("z", "A", "T", instant(5), instant(10)),
                    connection("a", "B", "T", instant(5), instant(10)),
                ],
            ),
            [request("tie", "S", "T", instant())],
        ),
        (
            timetable(
                {"Rīga": 86400, "京都": 0},
                [connection('leg\n"id', "Rīga", "京都", "2026-10-13T03:00:00+05:30", "2026-10-12T15:00:00-07:00")],
            ),
            [request('query\n"id', "Rīga", "京都", "2026-10-12T21:30:00Z")],
        ),
    ]
    randomizer = random.Random(69069)
    for case in range(40):
        names = ["s" + str(i) for i in range(randomizer.randint(2, 10))]
        stations = {name: randomizer.randrange(16) for name in names}
        edges = []
        for i in range(randomizer.randrange(41)):
            departure = randomizer.randrange(301)
            arrival = departure + randomizer.randint(1, 90)
            edges.append(
                connection(
                    "e" + str(i),
                    randomizer.choice(names),
                    randomizer.choice(names),
                    instant(departure, case % 2),
                    instant(arrival, case % 2),
                )
            )
        queries = [
            request(str(i), randomizer.choice(names), randomizer.choice(names), instant(randomizer.randrange(181)))
            for i in range(8)
        ]
        cases.append((timetable(stations, edges), queries))
    for index, (value, queries) in enumerate(cases):
        fix = fixture(directory, "case-" + str(index), value, queries)
        report = success(app, fix)
        if index == 0:
            assert [leg["id"] for leg in report["journeys"][0]["legs"]] == ["ab", "bc", "cd"]
            assert report["journeys"][0]["stats"]["stale"] == 1
        if index == 5:
            assert [leg["id"] for leg in report["journeys"][0]["legs"]] == ["ab", "exact"]
            assert [leg["id"] for leg in report["journeys"][1]["legs"]] == ["almost"]
        if index == 7:
            assert [leg["id"] for leg in report["journeys"][0]["legs"]] == ["ax", "xb", "bc"]
        if index == 8:
            assert [leg["id"] for leg in report["journeys"][0]["legs"]] == ["sa", "z"]
        altered = copy.deepcopy(value)
        randomizer.shuffle(altered["stations"])
        randomizer.shuffle(altered["connections"])
        zone = dt.timezone(dt.timedelta(minutes=330 if index % 2 else -420))
        for edge in altered["connections"]:
            for field in ["departure", "arrival"]:
                edge[field] = timestamp(edge[field]).astimezone(zone).isoformat(timespec="microseconds")
        other_queries = [
            {**q, "depart_after": timestamp(q["depart_after"]).astimezone(zone).isoformat(timespec="microseconds")}
            for q in queries
        ]
        other = fixture(directory, "permuted-" + str(index), altered, other_queries)
        assert success(app, other) == report and outputs(other, report) == outputs(fix, report)
        observations.append(report)
    first = success(app, fixture(directory, "split-first", sample(), jobs()[:2]))
    second = success(app, fixture(directory, "split-second", sample(), jobs()[2:]))
    assert first["journeys"] + second["journeys"] == observations[192]["journeys"]
    return {
        "exhaustive_timetables": 192,
        "exhaustive_queries": 3456,
        "other_timetables": len(cases),
        "generated_timetables": 40,
        "timezone_and_order_permutations": len(cases),
        "split_batches": 2,
        "reports_sha256": hashlib.sha256(canonical(observations).encode()).hexdigest(),
    }


def invalid_inputs(app: Application, directory: Path) -> int:
    base = timetable({"A": 0, "B": 0}, [connection("ab", "A", "B", instant(), instant(1))])
    variants = [None, [], {}, True, {**base, "extra": 1}]
    variants += [{k: v for k, v in base.items() if k != missing} for missing in base]
    variants += [{**base, "version": value} for value in [0, 2, True, 1.0, "1", None]]
    for collection in ["stations", "connections"]:
        variants += [{**base, collection: value} for value in [None, {}, True, ""]]
        row = base[collection][0]
        malformed = [None, [], {}, True, {**row, "extra": 1}]
        malformed += [{k: v for k, v in row.items() if k != missing} for missing in row]
        malformed += [{**row, "id": value} for value in ["", "a\x00", "x" * 129, "🙂" * 129, None, True, 1, [], {}]]
        variants += [{**base, collection: [value]} for value in malformed]
        variants.append({**base, collection: [row, row]})
    variants += [
        {**base, "stations": [{"id": "A", "transfer_seconds": value}, {"id": "B", "transfer_seconds": 0}]}
        for value in [-1, 86401, True, 1.0, "1", None, [], {}]
    ]
    times = [
        None,
        True,
        1,
        [],
        {},
        "",
        "2026-10-12",
        "2026-10-12T00:00:00",
        "2026-10-12 00:00:00Z",
        "2026-10-12T00:00:00.0000001Z",
        "2026-02-29T00:00:00Z",
        "2026-13-01T00:00:00Z",
        "2026-10-12T24:00:00Z",
        "2026-10-12T23:59:60Z",
        "2026-10-12T00:00:00+24:00",
        "2026-10-12T00:00:00+00:60",
        "1999-12-31T23:59:59Z",
        "2100-01-01T00:00:00Z",
        "2000-01-01T00:00:00+00:01",
        "2099-12-31T23:59:59-00:01",
    ]
    for field in ["from", "to"]:
        variants += [
            {**base, "connections": [{**base["connections"][0], field: value}]}
            for value in ["unknown", "", "x\x00", None, True, 1, [], {}]
        ]
    for field in ["departure", "arrival"]:
        variants += [{**base, "connections": [{**base["connections"][0], field: value}]} for value in times]
    variants += [
        {**base, "connections": [{**base["connections"][0], "arrival": value}]} for value in [instant(), instant(-1)]
    ]
    for index, value in enumerate(variants):
        failure(app, fixture(directory, "timetable-" + str(index), value, []))
    row = request("q", "A", "B", instant())
    bad_jobs = [None, {}, True, "", [None], [[]], [{}], [{**row, "extra": 1}], [row, row]]
    bad_jobs += [[{k: v for k, v in row.items() if k != missing}] for missing in row]
    bad_jobs += [[{**row, "id": value}] for value in ["", "a\x00", "x" * 129, "🙂" * 129, None, True, 1, [], {}]]
    for field in ["from", "to"]:
        bad_jobs += [[{**row, field: value}] for value in ["unknown", "", "x\x00", None, True, 1, [], {}]]
    bad_jobs += [[{**row, "depart_after": value}] for value in times]
    for index, value in enumerate(bad_jobs):
        failure(app, fixture(directory, "requests-" + str(index), base, value))
    count = len(variants) + len(bad_jobs)
    for key in ["timetable", "requests", "output"]:
        for index, value in enumerate(["", "\x00", None, True, 1, [], {}]):
            fix = fixture(directory, f"config-{key}-{index}", base, [])
            fix.path.write_text(json.dumps({**fix.config, key: value}))
            failure(app, fix)
            count += 1
        fix = fixture(directory, "missing-" + key, base, [])
        fix.path.write_text(json.dumps({k: v for k, v in fix.config.items() if k != key}))
        failure(app, fix)
        count += 1
    fix = fixture(directory, "extra-config", base, [])
    fix.path.write_text(json.dumps({**fix.config, "extra": 1}))
    failure(app, fix)
    failure(app, fixture(directory, "mode", base, []), "invalid timetable mode", TIMETABLE_MODE="bad")
    count += 2
    for name in ["timetable.json", "requests.json", "timetable-job.json"]:
        for index, raw in enumerate([b"\xff", b"{", b"[] trailing", b"[NaN]", b"[Infinity]", b'{"a":1,"a":2}']):
            fix = fixture(directory, f"raw-{name}-{index}", base, [])
            (fix.work / name).write_bytes(raw)
            failure(app, fix)
            count += 1
    return count


def limits(app: Application, directory: Path) -> dict:
    names = ["s" + str(i).zfill(3) for i in range(256)]
    edges = [connection("c" + str(i), names[i], names[i + 1], instant(2 * i), instant(2 * i + 1)) for i in range(255)]
    value = timetable(dict.fromkeys(names, 0), edges)
    report = success(app, fixture(directory, "long-chain", value, [request("q", names[0], names[-1], instant())]))
    assert len(report["journeys"][0]["legs"]) == 255 and report["journeys"][0]["arrival"] == instant(509)
    edges += [
        connection("extra" + str(i), names[0], names[-1], instant(10000 + i), instant(20000 + i)) for i in range(3841)
    ]
    value = timetable(dict.fromkeys(names, 0), edges)
    queries = [request(str(i), names[0], names[-1], instant()) for i in range(64)]
    report = success(app, fixture(directory, "combined-capacity", value, queries))
    assert len(report["journeys"]) == 64 and all(len(row["legs"]) == 255 for row in report["journeys"])
    failure(
        app,
        fixture(directory, "stations-above", timetable(dict.fromkeys([*names, "extra"], 0), []), []),
        "timetable capacity",
    )
    failure(
        app,
        fixture(
            directory,
            "connections-above",
            timetable(
                dict.fromkeys(names, 0), [*edges, connection("above", names[0], names[1], instant(), instant(1))]
            ),
            [],
        ),
        "timetable capacity",
    )
    failure(
        app,
        fixture(directory, "requests-above", value, [*queries, request("extra", names[0], names[-1], instant())]),
        "request count",
    )
    success(
        app,
        fixture(
            directory,
            "name-exact",
            timetable({"🙂" * 128: 86400}, []),
            [request("🙂" * 128, "🙂" * 128, "🙂" * 128, "2000-01-01T00:00:00Z")],
        ),
    )
    success(
        app,
        fixture(
            directory,
            "last-microsecond",
            timetable(
                {"A": 86400, "B": 0},
                [connection("boundary", "A", "B", "2099-12-31T23:59:59.999998Z", "2099-12-31T23:59:59.999999Z")],
            ),
            [request("q", "A", "B", "2099-12-31T23:59:59.999998Z")],
        ),
    )
    long_names = [str(i).zfill(3) + "🙂" * 125 for i in range(256)]
    long_edges = [
        connection("c" + str(i), long_names[i], long_names[i + 1], instant(i * 2), instant(i * 2 + 1))
        for i in range(255)
    ]
    failure(
        app,
        fixture(
            directory,
            "records-above",
            timetable(dict.fromkeys(long_names, 0), long_edges),
            [request(str(i), long_names[0], long_names[-1], instant()) for i in range(64)],
        ),
        "records exceed 8 MiB",
    )
    for name, maximum in [("timetable-job.json", 65536), ("timetable.json", 4194304), ("requests.json", 1048576)]:
        fix = fixture(directory, "bytes-" + name, sample(), jobs())
        path = fix.work / name
        raw = path.read_bytes()
        path.write_bytes(raw + b" " * (maximum - len(raw)))
        success(app, fix, "preview")
        path.write_bytes(raw + b" " * (maximum + 1 - len(raw)))
        failure(app, fix, "byte limit")
        path.write_bytes(raw)
    return {
        "stations": 256,
        "connections": 4096,
        "requests": 64,
        "transfer_seconds": 86400,
        "name_characters": 128,
        "name_bytes": 512,
        "longest_journey_legs": 255,
        "config_bytes": 65536,
        "timetable_bytes": 4194304,
        "requests_bytes": 1048576,
        "journey_record_bytes": 8388608,
        "timestamp_precision_microseconds": 1,
    }


def paused(app: Application, fix: Fixture) -> subprocess.Popen:
    process = subprocess.Popen(
        app.command,
        cwd=fix.work,
        env=app.environment(fix.settings(TIMETABLE_PAUSE="ready", TIMETABLE_CONTINUE=str(fix.work / "continue"))),
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
        "timetable.json",
        "requests.json",
        "journeys.json",
        "journeys.jsonl",
        "itineraries.txt",
        "manifest.json",
        "ready",
        "published",
    ]
    for point in points:
        fix = fixture(directory, "fault-" + point, sample(), jobs())
        reference = success(app, fix, "preview")
        result = app.run(fix.work, fix.settings(TIMETABLE_FAIL=point))
        assert result.returncode == 2 and "injected failure: " + point in result.stderr and not result.stdout
        assert not list(fix.work.glob(".timetable-*"))
        if point == "published":
            outputs(fix, reference)
        else:
            assert not fix.output.exists()
            success(app, fix)
    for name in ["timetable", "requests", "config", "destination"]:
        fix = fixture(directory, "changed-" + name, sample(), jobs())
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
            assert not list(fix.work.glob(".timetable-*"))
            if name == "destination":
                assert list(fix.output.iterdir()) == [fix.output / "keep"]
                assert (fix.output / "keep").read_bytes() == b"another writer"
            else:
                assert "input changed before publication" in error and not fix.output.exists()
        finally:
            stop(process)
    fix = fixture(directory, "killed", sample(), jobs())
    reference = success(app, fix, "preview")
    process = paused(app, fix)
    stop(process)
    assert not fix.output.exists()
    abandoned = list(fix.work.glob(".timetable-*"))
    assert len(abandoned) == 1
    old = {path.name: path.read_bytes() for path in abandoned[0].iterdir()}
    result = app.run(fix.work, fix.settings())
    assert result.returncode == 1 and not result.stderr
    outputs(fix, reference)
    assert {path.name: path.read_bytes() for path in abandoned[0].iterdir()} == old
    return len(points) + 5


def paths(app: Application, directory: Path) -> int:
    names = ["timetable.json", "requests.json", "timetable-job.json"]
    for name in ["file", "directory", "symlink", "dangling", *names]:
        fix = fixture(directory, "destination-" + name, sample(), jobs())
        if name == "file":
            fix.output.write_bytes(b"preserve")
        elif name == "directory":
            fix.output.mkdir()
            (fix.output / "keep").write_bytes(b"preserve")
        elif name in ["symlink", "dangling"]:
            fix.output.symlink_to(fix.work / ("timetable.json" if name == "symlink" else "missing"))
        else:
            fix.config["output"] = name
            fix.save()
        failure(app, fix, "output directory already exists")
    for name in names:
        fix = fixture(directory, "symlink-" + name, sample(), jobs())
        path = fix.work / name
        path.rename(fix.work / "original")
        path.symlink_to(fix.work / "original")
        original = (fix.work / "original").read_bytes()
        failure(app, fix, "regular file")
        assert path.is_symlink() and (fix.work / "original").read_bytes() == original
    fix = fixture(directory, "readonly", sample(), jobs())
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
    return 11


def check(app: Application, directory: Path) -> dict:
    cases = scenarios(app, directory / "scenarios")
    print(app.engine + " timetable: independent arrivals, itineraries and timezone normalization passed", flush=True)
    invalid = invalid_inputs(app, directory / "invalid")
    bounds = limits(app, directory / "limits")
    faults = publication(app, directory / "publication")
    path_cases = paths(app, directory / "paths")
    print(app.engine + " timetable: validation, limits, publication and path checks passed", flush=True)
    return {**cases, "invalid_inputs": invalid, "limits": bounds, "publication_cases": faults, "path_cases": path_cases}
