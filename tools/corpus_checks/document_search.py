# ruff: noqa: PLR1711 - repository functions use explicit returns
"""A brute-force document scan independently verifies the inverted search index."""

from __future__ import annotations

import copy
import hashlib
import json
import os
import random
import selectors
import subprocess
import unicodedata
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from .common import Application
from .csv_json import canonical


def put(name: str, title: str, text: str) -> dict:
    return {"op": "PUT", "document": {"id": name, "title": title, "text": text}}


def search(query: object, offset: int = 0, limit: int = 128) -> dict:
    return {"op": "SEARCH", "query": query, "offset": offset, "limit": limit}


def envelope(state: dict) -> dict:
    return {"state": state, "sha256": hashlib.sha256(canonical(state).encode()).hexdigest()}


def fresh(capacity: int) -> dict:
    return {"version": 1, "capacity": capacity, "steps": 0, "documents": [], "postings": {}}


def words(text: str) -> list[str]:
    # Deliberately avoid the application's regex and index. Scan individual scalars.
    result, current = [], []
    for character in unicodedata.normalize("NFKC", text).casefold():
        point = ord(character)
        separator = (
            point <= 0x2F
            or 0x3A <= point <= 0x40
            or 0x5B <= point <= 0x60
            or 0x7B <= point <= 0x9F
            or point in {0xA0, 0x1680}
            or 0x2000 <= point <= 0x206F
            or 0x3000 <= point <= 0x303F
        )
        if separator:
            if current:
                result.append("".join(current))
                current = []
        else:
            current.append(character)
    if current:
        result.append("".join(current))
    return result


def counts(document: dict) -> Counter:
    result = Counter(words(document["text"]))
    for word in words(document["title"]):
        result[word] += 3
    return result


def expression_terms(expression: object) -> set[str]:
    if isinstance(expression, str):
        return set(words(expression))
    return {word for child in next(iter(expression.values())) for word in expression_terms(child)}


def matches(document: dict, expression: object) -> bool:
    if isinstance(expression, str):
        terms = words(expression)
        present = words(document["title"]) + words(document["text"])
        return bool(terms) and all(word in present for word in terms)
    operation, children = next(iter(expression.items()))
    answers = [matches(document, child) for child in children]
    return all(answers) if operation == "and" else any(answers)


def postings(documents: dict) -> dict:
    result = {}
    for name, document in documents.items():
        for term, weight in counts(document).items():
            result.setdefault(term, {})[name] = weight
    return result


def search_scan(documents: dict, instruction: dict) -> dict:
    terms = sorted(expression_terms(instruction["query"]))
    ranked = []
    for name, document in documents.items():
        if matches(document, instruction["query"]):
            weights = counts(document)
            ranked.append(
                {
                    "id": name,
                    "title": document["title"],
                    "preview": document["text"][:160],
                    "score": sum(weights[word] for word in terms),
                    "terms": [word for word in terms if weights[word]],
                }
            )
    ranked.sort(key=lambda row: (-row["score"], row["id"]))
    start, stop = instruction["offset"], instruction["offset"] + instruction["limit"]
    return {"hits": ranked[start:stop], "count": len(ranked), "more": stop < len(ranked), "terms": terms}


def oracle(fix: Fixture) -> tuple[dict, list, dict]:
    state = fresh(fix.config["capacity"])
    if fix.config["state"]:
        state = json.loads((fix.work / fix.config["state"]).read_bytes())["state"]
    documents = {value["id"]: copy.deepcopy(value) for value in state["documents"]}
    steps, before = state["steps"], state["steps"]
    events = []
    trace = json.loads((fix.work / fix.config["trace"]).read_bytes())

    def view() -> dict:
        all_postings = postings(documents)
        return {
            "documents": len(documents),
            "terms": len(all_postings),
            "postings": sum(len(members) for members in all_postings.values()),
            "capacity": state["capacity"],
        }

    for instruction in trace:
        steps += 1
        operation = instruction["op"]
        event = {"step": steps, "op": operation}
        if operation == "PUT":
            value = instruction["document"]
            name = value["id"]
            accepted = name in documents or len(documents) < state["capacity"]
            event.update(id=name, replaced=name in documents, accepted=accepted)
            if accepted:
                documents[name] = copy.deepcopy(value)
            else:
                event["reason"] = "capacity"
        elif operation in {"GET", "DELETE"}:
            name = instruction["id"]
            event.update(id=name, found=name in documents)
            if operation == "GET":
                event["document"] = copy.deepcopy(documents.get(name))
            else:
                documents.pop(name, None)
        elif operation == "SEARCH":
            event["result"] = search_scan(documents, instruction)
        else:
            assert operation == "INSPECT"
            event["index"] = view()
        events.append(copy.deepcopy(event))
    saved = {
        "version": 1,
        "capacity": state["capacity"],
        "steps": steps,
        "documents": [documents[name] for name in sorted(documents)],
        "postings": postings(documents),
    }
    report = {"before_steps": before, "after_steps": steps, "commands": len(trace), "index": view()}
    return envelope(saved), events, report


def sample() -> list:
    return [
        put("z", "HTTP Python", "Rust rust Straße CAFÉ"),
        put("a", "Rust notes", "HTTP python Σςσ İIı ﬁle"),
        put("é", "Saved messages", "cafe\u0301 Python 世界 😀"),
        search({"and": ["http", {"or": ["python", "rust"]}]}),
        search("STRASSE"),
        search("CAFÉ", 0, 1),
        put("z", "New title", "Gone old terms; JSON JSON"),
        search("strasse"),
        {"op": "DELETE", "id": "a"},
        search("rust"),
        put("a", "HTTP", "JSON café"),
        search({"or": ["JSON JSON", "CAFÉ"]}),
        {"op": "GET", "id": "z"},
        {"op": "GET", "id": "missing"},
        {"op": "DELETE", "id": "é"},
        {"op": "DELETE", "id": "é"},
        search({"and": ["", "JSON"]}),
        search({"or": ["!!!", "JSON"]}, 1, 1),
        {"op": "INSPECT"},
    ]


def invalid_commands(app: Application, directory: Path) -> int:
    bad = [None, [], {}, {"op": "search"}, {"op": True}, {"op": "UNKNOWN"}]
    valid = [
        put("a", "title", "body"),
        search("a"),
        {"op": "GET", "id": "a"},
        {"op": "DELETE", "id": "a"},
        {"op": "INSPECT"},
    ]
    for instruction in valid:
        bad.append({**instruction, "extra": 0})
        for field in instruction:
            bad.append({key: value for key, value in instruction.items() if key != field})
    for name in ["", "😀" * 33, None, True, 1]:
        bad += [put(name, "", ""), {"op": "GET", "id": name}, {"op": "DELETE", "id": name}]
    for field, values in {
        "title": [None, True, 7, "a " * 257],
        "text": [None, False, [], "a " * 8193, "a" * 129, "a " * 4097, " ".join(f"t{i}" for i in range(257))],
    }.items():
        for value in values:
            instruction = put("a", "", "")
            instruction["document"][field] = value
            bad.append(instruction)
    for value in [None, [], {}, {"id": "a", "title": "", "text": "", "extra": 1}]:
        bad.append({"op": "PUT", "document": value})
    for value in [
        None,
        False,
        1,
        [],
        {},
        {"xor": ["x"]},
        {"and": []},
        {"or": "x"},
        {"and": ["a"], "or": ["b"]},
        {"or": ["x"] * 17},
        "a " * 513,
        "x" * 129,
        " ".join(f"t{i}" for i in range(65)),
        {"and": ["missing", None]},
        {"or": ["a", None]},
    ]:
        bad.append(search(value))
    nested = "x"
    for _ in range(9):
        nested = {"and": [nested]}
    bad += [search(nested), search({"or": [{"and": ["x"] * 15}] * 4})]
    for field, values in {"offset": [-1, 129, True, 1.0, None], "limit": [0, 129, True, 1.0, None]}.items():
        for value in values:
            bad.append({**search("a"), field: value})
    for index, instruction in enumerate(bad):
        failure(app, fixture(directory, f"invalid-command-{index}", [put("ok", "", ""), instruction]), "command 2:")
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
    fix = fixture(directory, "state-origin", sample()[:6])
    initial = success(app, fix)[0]["state"]
    mutations = []
    for field, value in [
        ("version", 2),
        ("version", True),
        ("capacity", 0),
        ("capacity", 4),
        ("steps", -1),
        ("steps", True),
        ("steps", 1000000001),
        ("documents", None),
        ("postings", None),
    ]:
        mutations.append({**copy.deepcopy(initial), field: value})
    for field, value in [("id", ""), ("id", "😀" * 33), ("title", None), ("text", "a" * 129)]:
        state = copy.deepcopy(initial)
        state["documents"][0][field] = value
        mutations.append(state)
    for target_name in ["state", "document"]:
        for action in ["missing", "extra"]:
            state = copy.deepcopy(initial)
            target = state if target_name == "state" else state["documents"][0]
            if action == "missing":
                del target[next(iter(target))]
            else:
                target["extra"] = None
            mutations.append(state)
    for operation in ["duplicate", "removed", "added", "weight", "ghost", "empty", "missing", "spelling"]:
        state = copy.deepcopy(initial)
        if operation == "duplicate":
            state["documents"][0] = copy.deepcopy(state["documents"][1])
        elif operation == "removed":
            state["documents"].pop()
        elif operation == "added":
            state["documents"].append({"id": "new", "title": "", "text": ""})
        elif operation == "weight":
            state["postings"]["http"]["a"] += 1
        elif operation == "ghost":
            state["postings"]["http"]["absent"] = 1
        elif operation == "empty":
            state["postings"]["empty"] = {}
        elif operation == "missing":
            del state["postings"]["http"]
        else:
            state["postings"]["HTTP"] = state["postings"].pop("http")
        mutations.append(state)
    for value in [True, "1", None, 0, -1]:
        state = copy.deepcopy(initial)
        state["postings"]["http"]["a"] = value
        mutations.append(state)
    for index, state in enumerate(mutations):
        failure(app, fixture(directory, f"bad-state-{index}", [], prior=envelope(state)), "")
    raw = [None, [], {}, {"state": initial, "sha256": "invalid"}, {"state": initial, "sha256": 1}]
    for index, value in enumerate(raw):
        bad = fixture(directory, f"bad-envelope-{index}", [], prior=value)
        if value is None:
            bad.config["state"] = "prior.json"
            bad.save()
            (bad.work / "prior.json").write_text("null")
        failure(app, bad, "")
    permuted = copy.deepcopy(initial)
    permuted["documents"].reverse()
    shuffled = fixture(directory, "shuffled-state", sample()[6:], prior=envelope(permuted))
    restored = success(app, shuffled)
    whole = fixture(directory, "state-whole", sample())
    assert canonical(restored[0]) == canonical(success(app, whole)[0])
    return len(mutations) + len(raw) + 1


def limits(app: Application, directory: Path) -> int:
    checks = 0
    for size in [1, 128]:
        trace = [put(str(index), "tie", "same") for index in range(size)]
        trace += [
            put("overflow", "", ""),
            put("0", "replacement", "same"),
            search("same", 0, 1),
            {"op": "DELETE", "id": "0"},
            put("overflow", "", "new"),
            {"op": "INSPECT"},
        ]
        result = success(app, fixture(directory, f"full-{size}", trace, size))
        assert result[1][size]["reason"] == "capacity"
        assert result[1][size + 1]["accepted"] and result[1][size + 1]["replaced"]
        assert result[1][-2]["accepted"]
        checks += 1
    success(app, fixture(directory, "trace-max", [{"op": "INSPECT"}] * 2000))
    failure(app, fixture(directory, "trace-too-many", [{"op": "INSPECT"}] * 2001), "2000 commands")
    checks += 2
    for name, target, size in [
        ("config", "search-job.json", 65537),
        ("trace", "trace.json", 4194305),
        ("state", "prior.json", 8388609),
    ]:
        fix = fixture(directory, "bytes-" + name, [], prior=envelope(fresh(3)))
        with (fix.work / target).open("wb") as stream:
            stream.truncate(size)
        failure(app, fix, "input byte limit")
        checks += 1
    nested = "a"
    for _ in range(8):
        nested = {"and": [nested]}
    success(
        app,
        fixture(
            directory,
            "exact-bounds",
            [
                put("😀" * 32, "a " * 256, ("a " * 4096).ljust(16384)),
                put("terms", "", " ".join(f"t{i}" for i in range(256))),
                put("token", "", "😀" * 32),
                search("😀" * 32),
                search(nested),
                search({"or": [{"and": ["a"] * size} for size in [15, 15, 15, 14]]}),
                search(" ".join(f"t{i}" for i in range(64))),
                search("a ".ljust(1024)),
                search("a", 128, 128),
            ],
        ),
    )
    checks += 1
    vocabulary = [put(str(index), "", " ".join(f"t{index * 256 + n}" for n in range(256))) for index in range(16)]
    success(app, fixture(directory, "vocabulary-exact", vocabulary + [search("t4095")], 128))
    failure(
        app,
        fixture(directory, "vocabulary-overflow", vocabulary + [put("new", "", "unique")], 128),
        "4096 distinct terms",
    )
    success(app, fixture(directory, "vocabulary-replace", vocabulary + [put("0", "", "unique")], 128))
    checks += 3
    body = (("a" * 128 + " ") * 127).ljust(16384)
    trace = [put("big", "", body)] + [{"op": "GET", "id": "big"}] * 1100
    failure(app, fixture(directory, "events-too-big", trace), "events exceed 16 MiB")
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
        put("é", "Straße Σςσ", "İIı café ﬁle ＨＴＴＰ 世界 😀"),
        put("e\u0301", "", "i̇iı cafe\u0301 file http"),
        put("z", "", "😀 " * 100 + "raw preview tail"),
    ]
    unicode_trace += [search(term) for term in ["STRASSE", "ΣΣΣ", "İIı", "CAFÉ", "ﬁle", "HTTP", "世界", "😀", "!!!"]]
    unicode_trace += [search({"or": ["http", "HTTP HTTP"]}), search({"and": ["http", ""]})]
    cases.append((3, unicode_trace))
    separators = [0, 0x2F, 0x3A, 0x40, 0x5B, 0x60, 0x7B, 0x9F, 0xA0, 0x1680, 0x2000, 0x206F, 0x3000, 0x303F]
    cases.append((1, [put("separators", "", "".join("a" + chr(value) + "b " for value in separators)), search("a b")]))
    churn = [
        item
        for _ in range(100)
        for item in [put("reuse", "old", "old"), put("reuse", "new", "new"), {"op": "DELETE", "id": "reuse"}]
    ]
    cases.append((1, churn + [search({"or": ["old", "new"]}), {"op": "INSPECT"}]))
    rng = random.Random(540054)
    vocabulary = ["HTTP", "Python", "rust", "Straße", "STRASSE", "café", "cafe\u0301", "Σςσ", "世界", "😀", "fi", ""]

    def expression(depth: int) -> object:
        if depth == 0 or rng.randrange(3) == 0:
            return " ".join(rng.choices(vocabulary, k=rng.randrange(4)))
        return {rng.choice(["and", "or"]): [expression(depth - 1) for _ in range(rng.randrange(1, 4))]}

    for _ in range(32):
        trace = []
        for _index in range(160):
            operation = rng.choice(["PUT"] * 3 + ["SEARCH"] * 5 + ["DELETE", "GET", "INSPECT"])
            name = rng.choice(["a", "b", "c", "é", "e\u0301", "世界", "a\x00b"])
            if operation == "PUT":
                trace.append(put(name, " ".join(rng.choices(vocabulary, k=3)), " ".join(rng.choices(vocabulary, k=12))))
            elif operation == "SEARCH":
                trace.append(search(expression(3), rng.randrange(5), rng.randrange(1, 5)))
            else:
                trace.append({"op": operation, **({"id": name} if operation != "INSPECT" else {})})
        cases.append((rng.randrange(1, 9), trace))
    observations = []
    for index, (size, trace) in enumerate(cases):
        fix = fixture(directory, f"trace-{index}", trace, size)
        success(app, fix, "preview")
        observations.append(success(app, fix))
        resumed = fixture(directory, f"unchanged-{index}", [], size, state=str(fix.output / "state.json"))
        success(app, resumed)
        assert (resumed.output / "state.json").read_bytes() == (fix.output / "state.json").read_bytes()
    whole = fixture(directory, "full", sample())
    complete = success(app, whole)
    for split in range(len(sample()) + 1):
        prefix = fixture(directory, f"prefix-{split}", sample()[:split])
        success(app, prefix)
        suffix = fixture(directory, f"suffix-{split}", sample()[split:], state=str(prefix.output / "state.json"))
        result = success(app, suffix)
        assert canonical(result[0]) == canonical(complete[0])
        assert (prefix.output / "events.jsonl").read_bytes() + (suffix.output / "events.jsonl").read_bytes() == (
            whole.output / "events.jsonl"
        ).read_bytes()
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
        return self.work / "search-job.json"

    @property
    def output(self) -> Path:
        return self.work / self.config["output"]

    def save(self) -> None:
        self.path.write_text(json.dumps(self.config, ensure_ascii=False))
        return

    def settings(self, mode: str = "write", **extra: str) -> dict:
        return {
            "SEARCH_CONFIG": str(self.path),
            "SEARCH_MODE": mode,
            "SEARCH_FAIL": "",
            "SEARCH_PAUSE": "",
            "SEARCH_CONTINUE": "",
            **extra,
        }


def fixture(
    directory: Path, name: str, commands: list, capacity: int = 3, prior: dict | None = None, **changes: object
) -> Fixture:
    work = directory / name
    work.mkdir(parents=True)
    (work / "trace.json").write_text(json.dumps(commands, ensure_ascii=False))
    config = {"trace": "trace.json", "state": "", "capacity": capacity, "output": "search-run", **changes}
    if prior is not None:
        (work / "prior.json").write_text(canonical(prior))
        config["state"] = "prior.json"
    fix = Fixture(work, config)
    fix.save()
    return fix


def outputs(fix: Fixture, expected: tuple[dict, list, dict]) -> None:
    saved, events, report = expected
    assert sorted(path.name for path in fix.output.iterdir()) == ["events.jsonl", "report.json", "state.json"]
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
    assert not list(fix.work.glob(".document-search-*"))
    return expected


def failure(app: Application, fix: Fixture, message: str, **extra: str) -> None:
    existed = fix.output.exists() or fix.output.is_symlink()
    original = fix.output.read_bytes() if fix.output.is_file() else None
    result = app.run(fix.work, fix.settings(**extra), timeout=45)
    assert result.returncode == 2 and message in result.stderr and not result.stdout, (result, message, fix.config)
    assert (fix.output.exists() or fix.output.is_symlink()) == existed
    if original is not None:
        assert fix.output.read_bytes() == original
    assert not list(fix.work.glob(".document-search-*"))
    return


def paused(app: Application, fix: Fixture) -> subprocess.Popen:
    signal = fix.work / "continue"
    process = subprocess.Popen(
        app.command,
        cwd=fix.work,
        env=app.environment(fix.settings(SEARCH_PAUSE="ready", SEARCH_CONTINUE=str(signal))),
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
        result = app.run(fix.work, fix.settings(SEARCH_FAIL=point))
        assert result.returncode == 2 and "injected failure: " + point in result.stderr and not result.stdout
        assert not list(fix.work.glob(".document-search-*"))
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
                filename = {"trace": "trace.json", "configuration": "search-job.json", "state": "prior.json"}[name]
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
            assert not list(fix.work.glob(".document-search-*"))
        finally:
            if process.poll() is None:
                process.kill()
                process.communicate(timeout=5)
    fix = fixture(directory, "killed", sample())
    process = paused(app, fix)
    process.kill()
    process.communicate(timeout=5)
    assert not fix.output.exists()
    abandoned = list(fix.work.glob(".document-search-*"))
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
            fix.config["output"] = "trace.json" if name == "same-trace" else "search-job.json"
            fix.save()
        failure(app, fix, "output directory already exists")
    for name in ["trace.json", "search-job.json", "prior.json"]:
        fix = fixture(directory, "link-" + name, [], prior=envelope(fresh(3)))
        path = fix.work / name
        original = path.with_suffix(".original")
        path.rename(original)
        path.symlink_to(original)
        failure(app, fix, "input must be a regular file")
    return len(points) + 4 + 1 + 6 + 3
