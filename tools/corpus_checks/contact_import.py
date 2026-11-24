"""Independent graph/reference merge, provenance, repeat-import and publication checks."""

from __future__ import annotations

import copy
import hashlib
import itertools
import json
import os
import random
import selectors
import shutil
import subprocess
import unicodedata
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from .common import Application
from .csv_json import canonical

FIELDS = ["name", "email", "phone", "address", "organization"]
KEYS = [["email"], ["phone"], ["name", "address"]]


def digest(value: object) -> str:
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def row(identifier: str, source: str = "crm", **fields: object) -> dict:
    return {"source": source, "id": identifier, **fields}


def identifier(value: object) -> None:
    assert type(value) is str and 1 <= len(value.encode()) <= 128 and value == value.strip()
    assert not any(ord(char) < 32 or ord(char) == 127 for char in value)
    return  # noqa: PLR1711


def normalize(field: str, value: object) -> str:
    assert type(value) is str and len(value.encode()) <= 2048
    value = unicodedata.normalize("NFC", " ".join(value.split()))
    assert not any(ord(char) < 32 or ord(char) == 127 for char in value)
    if not value:
        return value
    if field == "email":
        assert value.isascii() and value.count("@") == 1
        local, domain = value.split("@")
        alphabet = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.!#$%&'*+/=?^_`{|}~-"
        assert 1 <= len(local) <= 64 and all(char in alphabet for char in local)
        assert not local.startswith(".") and not local.endswith(".") and ".." not in local
        assert 1 <= len(domain) <= 253
        for label in domain.split("."):
            assert 1 <= len(label) <= 63 and label[0].isalnum() and label[-1].isalnum()
            assert all(char.isalnum() or char == "-" for char in label)
        return local + "@" + domain.lower()
    if field == "phone":
        assert all(char in "+0123456789 ().-" for char in value)
        digits = "".join(char for char in value if char not in " ().-")
        assert digits.startswith("+") and 7 <= len(digits[1:]) <= 15
        assert digits[1] in "123456789" and all(char in "0123456789" for char in digits[1:])
        return digits
    return value


def parsed(raw: object) -> tuple[dict, list[str]]:
    if not isinstance(raw, dict):
        return {}, ["object"]
    errors = ["unknown:" + key for key in sorted(raw) if key not in [*FIELDS, "source", "id"]]
    for key in ["source", "id"]:
        try:
            identifier(raw.get(key))
        except (AssertionError, UnicodeError):
            errors.append(key)
    normalized = {}
    for field in FIELDS:
        try:
            normalized[field] = normalize(field, raw.get(field, ""))
        except (AssertionError, UnicodeError):
            errors.append(field)
    if not any(normalized.get(field) for field in FIELDS if field != "organization"):
        errors.append("empty_contact")
    return normalized, errors


@dataclass
class Fixture:
    work: Path
    config: dict

    @property
    def path(self) -> Path:
        return self.work / "contact-job.json"

    @property
    def output(self) -> Path:
        return self.work / self.config["output"]

    def save(self) -> None:
        self.path.write_text(json.dumps(self.config, ensure_ascii=False))
        return  # noqa: PLR1711

    def settings(self, mode: str = "write", **extra: str) -> dict:
        return {"CONTACT_CONFIG": str(self.path), "CONTACT_MODE": mode, **extra}


def fixture(
    directory: Path,
    name: str,
    rows: list[object],
    *,
    batches: list[list[object]] | None = None,
    prior: dict | None = None,
    **changes: object,
) -> Fixture:
    work = directory / name
    work.mkdir(parents=True)
    inputs = []
    for index, batch in enumerate([rows, *(batches or [])], 1):
        path = work / f"input-{index}.json"
        path.write_text(json.dumps(batch, ensure_ascii=False))
        inputs.append(path.name)
    config = {"inputs": inputs, "state": "", "output": "imported", "keys": copy.deepcopy(KEYS)}
    if prior is not None:
        (work / "prior.json").write_text(canonical(prior))
        config["state"] = "prior.json"
    config.update(changes)
    fix = Fixture(work, config)
    fix.save()
    return fix


def oracle(fix: Fixture) -> dict:
    rules = sorted(sorted(rule) for rule in fix.config["keys"])
    records = {}
    if fix.config["state"]:
        envelope = json.loads((fix.work / fix.config["state"]).read_bytes())
        records = {digest(raw): raw for raw in envelope["state"]["records"]}
    initial = len(records)
    rejected, sources = [], []
    total = replayed = 0
    for index, name in enumerate(fix.config["inputs"], 1):
        path = (fix.work / name).resolve()
        data = path.read_bytes()
        rows = json.loads(data)
        total += len(rows)
        sources.append({"path": str(path), "records": len(rows), "sha256": hashlib.sha256(data).hexdigest()})
        for number, raw in enumerate(rows, 1):
            _, errors = parsed(raw)
            if errors:
                rejected.append({"input": index, "record": number, "raw": raw, "errors": errors})
            elif digest(raw) in records:
                replayed += 1
            else:
                records[digest(raw)] = raw
    variants = sorted(records, key=lambda variant: (records[variant]["source"], records[variant]["id"], variant))
    normalized = {variant: parsed(records[variant])[0] for variant in variants}
    tokens = {}
    for variant in variants:
        raw = records[variant]
        tokens[variant] = {("identity", raw["source"], raw["id"])}
        for rule in rules:
            values = tuple(normalized[variant][field] for field in rule)
            if all(values):
                tokens[variant].add(("match", tuple(rule), values))
    # Pairwise adjacency and graph traversal independently check the application's hash index / disjoint sets.
    edges = {variant: set() for variant in variants}
    for left, right in itertools.combinations(variants, 2):
        if tokens[left] & tokens[right]:
            edges[left].add(right)
            edges[right].add(left)
    pending = set(variants)
    groups = []
    for start in variants:
        if start not in pending:
            continue
        members, queue = set(), [start]
        while queue:
            member = queue.pop()
            if member not in pending:
                continue
            pending.remove(member)
            members.add(member)
            queue.extend(edges[member] & pending)
        groups.append([variant for variant in variants if variant in members])
    contacts, review = [], []
    for members in groups:
        options, values, conflicts = {}, {}, []
        identities = defaultdict(list)
        references = []
        for variant in members:
            raw = records[variant]
            identities[(raw["source"], raw["id"])].append(variant)
            references.append({"source": raw["source"], "id": raw["id"], "variant": variant})
        for field in FIELDS:
            candidates = sorted({normalized[variant][field] for variant in members} - {""})
            options[field] = [
                {"value": value, "variants": [variant for variant in members if normalized[variant][field] == value]}
                for value in candidates
            ]
            if len(candidates) > 1:
                conflicts.append(field)
            else:
                values[field] = candidates[0] if candidates else ""
        reused = [
            {"source": source, "id": identifier, "variants": variants}
            for (source, identifier), variants in identities.items()
            if len(variants) > 1
        ]
        entry = {
            "id": digest(sorted(members)),
            "members": references,
            "values": values,
            "options": options,
            "conflicting_fields": conflicts,
            "reused_identities": reused,
            "review": bool(conflicts or reused),
        }
        (review if entry["review"] else contacts).append(entry)
    state = {"version": 1, "keys": rules, "records": [records[variant] for variant in variants]}
    return {
        "book.json": {"state": state, "sha256": digest(state)},
        "contacts.json": contacts,
        "review.json": review,
        "rejected.json": rejected,
        "report.json": {
            "sources": sources,
            "input_records": total,
            "added": len(records) - initial,
            "replayed": replayed,
            "rejected": len(rejected),
            "variants": len(records),
            "contacts": len(contacts),
            "review_groups": len(review),
            "state_sha256": digest(state),
        },
    }


def bundle(fix: Fixture, expected: dict) -> None:
    assert {p.name for p in fix.output.iterdir()} == set(expected)
    for name, value in expected.items():
        assert canonical(json.loads((fix.output / name).read_bytes())) == canonical(value), name
    assert (fix.output / "book.json").read_bytes() == canonical(expected["book.json"]).encode()
    return  # noqa: PLR1711


def run(app: Application, fix: Fixture, timeout: int = 45) -> dict:
    expected = oracle(fix)
    before = {p.name: p.read_bytes() for p in fix.work.iterdir() if p.is_file()}
    report = expected["report.json"]
    for mode in ["preview", "write"]:
        result = app.run(fix.work, fix.settings(mode), timeout=timeout)
        assert result.returncode == int(bool(report["review_groups"] or report["rejected"])), result.stderr
        assert json.loads(result.stdout) == report
        if mode == "preview":
            assert not fix.output.exists()
        else:
            bundle(fix, expected)
    assert all((fix.work / name).read_bytes() == value for name, value in before.items())
    assert not list(fix.work.glob(".contact-import-*"))
    repeated = app.run(fix.work, fix.settings(), timeout=timeout)
    assert repeated.returncode == 2 and "already exists" in repeated.stderr
    bundle(fix, expected)
    return expected


def reject(app: Application, fix: Fixture, message: str = "", **settings: str) -> None:
    before = {p.name: p.read_bytes() for p in fix.work.iterdir() if p.is_file() and not p.is_symlink()}
    entries = {p.name for p in fix.work.iterdir()}
    result = app.run(fix.work, fix.settings(**settings), timeout=120)
    assert result.returncode == 2 and message in result.stderr and not result.stdout, result.stderr
    assert {p.name for p in fix.work.iterdir()} == entries
    assert all((fix.work / name).read_bytes() == value for name, value in before.items())
    return  # noqa: PLR1711


def sample() -> list[dict]:
    return [
        row("1", name=" Jose\u0301  García ", email="jose@EXAMPLE.com", phone="+34 (912) 345-678"),
        row("A", "book", name="José García", email="jose@example.com", address="Calle Mayor 1"),
        row("2", name="Ada", email="ada@example.com", organization="Engines"),
        row("X", "book", name="Other Ada", email="ada@example.com"),
        row("3", name="Unmatched"),
    ]


def check_merges(app: Application, directory: Path) -> dict:
    scenarios = [
        ([], KEYS),
        (sample(), KEYS),
        ([row("1", name="A"), row("2", name="A")], [["email"]]),
        ([row("1", name="A", address="X"), row("2", name="A", address="X")], [["name", "address"]]),
        ([row("1", name="A"), row("2", name="A", address="X")], [["name", "address"]]),
        ([row("1", name="A", address="X"), row("2", name="A", address="Y")], [["name", "address"]]),
        (
            [row("1", email="a@x.test"), row("2", phone="+12345678"), row("3", email="a@x.test", phone="+12345678")],
            KEYS,
        ),
        (
            [
                row("1", name="A", email="a@x.test"),
                row("2", name="B", phone="+12345678"),
                row("3", email="a@x.test", phone="+12345678"),
            ],
            KEYS,
        ),
        ([row("same", name="A"), row("same", phone="+12345678")], KEYS),
        ([row("same", name="Jose\u0301"), row("same", name="José")], [["name"]]),
        ([row("same", name="A"), row("same", "second", name="B")], KEYS),
        ([row("1", email="ADA@EXAMPLE.COM"), row("2", email="ada@example.com")], [["email"]]),
        ([row("1", name="Å", address="가"), row("2", name="A\u030a", address="가")], [["name", "address"]]),
        ([row("1", name="ﬃ"), row("2", name="ffi")], [["name"]]),
        ([row("1", name="a\u00a0 b\t世界"), row("2", name="a b 世界")], [["name"]]),
        ([row("1", "é", name="A"), row("1", "e\u0301", name="A")], [["email"]]),
        ([row("1", name="same", email="one@x.test"), row("2", name="same", email="two@x.test")], [["name"], ["email"]]),
    ]
    for number, (rows, keys) in enumerate(scenarios):
        fix = fixture(directory, f"merge-{number}", rows, keys=keys)
        expected = run(app, fix)
        repeated = fixture(directory, f"reimport-{number}", rows, prior=expected["book.json"], keys=keys)
        again = run(app, repeated)
        for name in ["book.json", "contacts.json", "review.json"]:
            assert canonical(again[name]) == canonical(expected[name]), (number, name)
        assert again["report.json"]["added"] == 0
    original = fixture(directory, "stable-original", sample())
    baseline = run(app, original)
    rng = random.Random(48048)
    for number in range(12):
        rows, keys = sample(), copy.deepcopy(KEYS)
        rng.shuffle(rows)
        rng.shuffle(keys)
        for key in keys:
            rng.shuffle(key)
        fix = fixture(directory, f"stable-{number}", rows[:2], batches=[rows[2:], rows[:2]], keys=keys)
        result = run(app, fix)
        for name in ["book.json", "contacts.json", "review.json"]:
            assert canonical(result[name]) == canonical(baseline[name]), name
        assert result["report.json"]["replayed"] == 2
    additions = [
        row("new", name="新しい", email="new@example.com"),
        row("1", name="New name", email="jose@example.com"),
    ]
    updated = run(app, fixture(directory, "incremental", additions, prior=baseline["book.json"]))
    combined = run(app, fixture(directory, "combined", [*sample(), *additions]))
    replay = run(app, fixture(directory, "incremental-replay", additions, prior=updated["book.json"]))
    for name in ["book.json", "contacts.json", "review.json"]:
        assert canonical(updated[name]) == canonical(combined[name]) == canonical(replay[name]), name
    assert replay["report.json"]["added"] == 0 and replay["report.json"]["replayed"] == 2
    return {"scenarios": len(scenarios), "reimports": len(scenarios), "reorderings": 12, "incremental": 3}


def check_generated(app: Application, directory: Path) -> dict:
    rng = random.Random(480480)
    observations = []
    for number in range(40):
        rows = []
        for _ in range(35):
            fields = {}
            for field, options in {
                "name": ["Ada", "Bob", "Jose\u0301", "José", "世界", ""],
                "email": ["a@example.COM", "b@example.com", "c@example.com", ""],
                "phone": ["+12345678", "+23 (456) 789", ""],
                "address": ["  Road  1 ", "Road 2", ""],
                "organization": ["Org", "Other", ""],
            }.items():
                if rng.randrange(3):
                    fields[field] = rng.choice(options)
            rows.append(row(str(rng.randrange(24)), "source" + str(rng.randrange(3)), **fields))
        keys = rng.choice([KEYS, [["email"]], [["name", "address"]], [["organization", "name"], ["phone"]]])
        result = run(app, fixture(directory, f"generated-{number}", rows, keys=keys))
        observations.append(digest([result[name] for name in ["book.json", "contacts.json", "review.json"]]))
    return {"cases": 40, "sha256": digest(observations)}


def check_invalid(app: Application, directory: Path) -> int:
    rows: list[object] = [None, False, 1, "text", [], {}, row("1"), row("1", organization="only")]
    for field in ["source", "id"]:
        for value in [None, False, 1, [], {}, "", " x", "x ", "x\0y", "x\x7fy", "😀" * 33]:
            rows.append({**row("valid", name="A"), field: value})
    for field in FIELDS:
        for value in [None, False, 1, [], {}, "x" * 2049, "bad\0text"]:
            rows.append({**row("valid", name="A"), field: value})
    for value in [
        "a..b@x.test",
        ".a@x.test",
        "a.@x.test",
        "a@",
        "a",
        "a@x..test",
        "a@-x.test",
        "a@x-.test",
        "a@é.test",
        "a b@x.test",
        "a" * 65 + "@x.test",
        "a@" + "x" * 64,
        "a@" + ".".join(["x" * 63] * 4),
    ]:
        rows.append(row("invalid-email", email=value))
    for value in [
        "123456789",
        "+123456",
        "+1234567890123456",
        "+01234567",
        "++12345678",
        "+１２３４５６７",
        "+1/2345678",
        "+12345678 ext 1",
    ]:
        rows.append(row("invalid-phone", phone=value))
    rows.append({**row("unknown", name="A"), "unknown": {"preserve": [1, 1.0, -0.0, None]}})
    result = run(app, fixture(directory, "invalid-rows", rows))
    assert result["report.json"]["rejected"] == len(rows)
    assert [entry["raw"] for entry in result["rejected.json"]] == rows
    combined = {
        "source": None,
        "id": False,
        "name": 4,
        "email": "no",
        "phone": "no",
        "address": [],
        "organization": {},
        "extra": None,
    }
    result = run(app, fixture(directory, "invalid-combined", [combined]))
    assert result["rejected.json"][0]["errors"] == ["unknown:extra", "source", "id", *FIELDS, "empty_contact"]
    return len(rows) + 1


def check_configuration_state(app: Application, directory: Path) -> int:
    changes = [
        {"keys": []},
        {"keys": [["name", "name"]]},
        {"keys": [["other"]]},
        {"keys": [[]]},
        {"keys": [["name", "email"], ["email", "name"]]},
        {"keys": ["name"]},
        {"keys": [[1]]},
        {"keys": [[field] for field in FIELDS] + [["name", field] for field in FIELDS[1:]]},
        {"inputs": []},
        {"inputs": ["input-1.json"] * 17},
        {"inputs": "input-1.json"},
        {"inputs": [None]},
        {"inputs": [""]},
        {"inputs": ["missing"]},
        {"state": None},
        {"output": ""},
        {"output": None},
        {"extra": True},
    ]
    for index, change in enumerate(changes):
        reject(app, fixture(directory, f"bad-config-{index}", [], **change))
    reject(app, fixture(directory, "bad-mode", []), CONTACT_MODE="import")
    for index, data in enumerate([b"{}", b"null", b"[", b"\xff", b"[NaN]", b"[9223372036854775808]", b'["\\ud800"]']):
        fix = fixture(directory, f"bad-input-{index}", [])
        (fix.work / "input-1.json").write_bytes(data)
        reject(app, fix)
    for index, data in enumerate([b"[]", b"{", b"\xff", b"{}" + b" " * 65536]):
        fix = fixture(directory, f"bad-config-json-{index}", [])
        fix.path.write_bytes(data)
        reject(app, fix)
    baseline = run(app, fixture(directory, "prior-base", sample()))["book.json"]
    alterations = []
    for name, value in [("sha256", "wrong"), ("unknown", True)]:
        bad = copy.deepcopy(baseline)
        bad[name] = value
        alterations.append(bad)
    for name, value in [
        ("version", 2),
        ("version", True),
        ("keys", [["name"]]),
        ("records", [row("invalid")]),
        ("unknown", True),
    ]:
        bad = copy.deepcopy(baseline)
        bad["state"][name] = value
        bad["sha256"] = digest(bad["state"])
        alterations.append(bad)
    duplicate = copy.deepcopy(baseline)
    duplicate["state"]["records"].append(duplicate["state"]["records"][0])
    duplicate["sha256"] = digest(duplicate["state"])
    alterations.append(duplicate)
    for index, bad in enumerate(alterations):
        reject(app, fixture(directory, f"bad-prior-{index}", [], prior=bad))
    return len(changes) + 1 + 7 + 4 + len(alterations)


def pause(app: Application, fix: Fixture, point: str) -> subprocess.Popen:
    process = subprocess.Popen(
        app.command,
        cwd=fix.work,
        env=app.environment(fix.settings(CONTACT_PAUSE=point, CONTACT_CONTINUE=str(fix.work / "continue"))),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        with selectors.DefaultSelector() as selector:
            selector.register(process.stdout, selectors.EVENT_READ)
            assert selector.select(30), "contact importer did not pause"
        assert process.stdout.readline().rstrip() == "PAUSED " + point
        return process
    except BaseException:
        process.kill()
        process.communicate()
        raise


def resume(process: subprocess.Popen, fix: Fixture) -> subprocess.CompletedProcess:
    (fix.work / "continue").touch()
    output, error = process.communicate(timeout=45)
    return subprocess.CompletedProcess(process.args, process.returncode, output, error)


def check_publication(app: Application, directory: Path) -> int:
    points = [
        "input:1",
        "validated",
        "stage",
        "book.json",
        "contacts.json",
        "review.json",
        "rejected.json",
        "report.json",
        "ready",
        "published",
    ]
    for point in points:
        for killed in [False, True]:
            fix = fixture(directory, f"fault-{point.replace(':', '-')}-{killed}", sample())
            expected = oracle(fix)
            if killed:
                process = pause(app, fix, point)
                process.kill()
                process.communicate(timeout=10)
                assert process.returncode == -9
            else:
                result = app.run(fix.work, fix.settings(CONTACT_FAIL=point))
                assert result.returncode == 2 and "injected failure" in result.stderr
            if point == "published":
                bundle(fix, expected)
            else:
                assert not fix.output.exists()
            stages = list(fix.work.glob(".contact-import-*"))
            assert len(stages) == int(killed and point not in ["input:1", "validated", "published"])
            for stage in stages:
                shutil.rmtree(stage)
            if point != "published":
                run(app, fix)
    count = len(points) * 2
    baseline = run(app, fixture(directory, "publication-prior", sample()))["book.json"]
    for point in ["input:1", "validated", "ready"]:
        for name in ["input-1.json", "contact-job.json", "prior.json", "output"]:
            fix = fixture(directory, f"changed-{point.replace(':', '-')}-{name}", sample(), prior=baseline)
            process = pause(app, fix, point)
            try:
                if name == "output":
                    fix.output.mkdir()
                    (fix.output / "keep").write_bytes(b"untouched")
                else:
                    target = fix.work / name
                    target.write_bytes(target.read_bytes() + b" ")
                result = resume(process, fix)
                assert result.returncode == 2 and not list(fix.work.glob(".contact-import-*"))
                if name == "output":
                    assert {p.name for p in fix.output.iterdir()} == {"keep"}
                    assert (fix.output / "keep").read_bytes() == b"untouched"
                else:
                    assert "changed" in result.stderr and not fix.output.exists()
            finally:
                if process.poll() is None:
                    process.kill()
                    process.communicate()
            count += 1
    for point in ["stage", "contacts.json"]:
        fix = fixture(directory, "permission-" + point, sample())
        process = pause(app, fix, point)
        stage = next(fix.work.glob(".contact-import-*"))
        try:
            assert os.getuid() != 0
            stage.chmod(0o500)
            result = resume(process, fix)
            assert result.returncode == 2 and "Permission denied" in result.stderr and not fix.output.exists()
        finally:
            if process.poll() is None:
                process.kill()
                process.communicate()
            if stage.exists():
                stage.chmod(0o700)
                shutil.rmtree(stage)
        (fix.work / "continue").unlink()
        run(app, fix)
        count += 1
    return count


def check_paths(app: Application, directory: Path) -> int:
    for kind in ["symlink", "fifo", "directory", "output-file", "output-directory", "output-symlink", "permission"]:
        fix = fixture(directory, "paths-" + kind, sample())
        source = fix.work / "input-1.json"
        if kind == "symlink":
            source.rename(fix.work / "original")
            source.symlink_to("original")
        elif kind == "fifo":
            source.unlink()
            os.mkfifo(source)
        elif kind == "directory":
            source.unlink()
            source.mkdir()
        elif kind == "output-file":
            fix.output.write_bytes(b"keep")
        elif kind == "output-directory":
            fix.output.mkdir()
            (fix.output / "keep").write_bytes(b"keep")
        elif kind == "output-symlink":
            fix.output.symlink_to("missing")
        else:
            fix.work.chmod(0o500)
        try:
            result = app.run(fix.work, fix.settings(), timeout=20)
            assert result.returncode == 2 and not list(fix.work.glob(".contact-import-*"))
            if kind == "output-file":
                assert fix.output.read_bytes() == b"keep"
            elif kind == "output-directory":
                assert {p.name for p in fix.output.iterdir()} == {"keep"}
                assert (fix.output / "keep").read_bytes() == b"keep"
            elif kind == "output-symlink":
                assert fix.output.is_symlink() and os.readlink(fix.output) == "missing"
        finally:
            fix.work.chmod(0o700)
    return 7


def padded(path: Path, size: int) -> None:
    data = path.read_bytes()
    assert len(data) <= size
    path.write_bytes(data + b" " * (size - len(data)))
    return  # noqa: PLR1711


def check_limits(app: Application, directory: Path) -> dict:
    limited = Application(["/usr/bin/prlimit", "--as=268435456", "--", *app.command], app.engine)
    rows = [row(str(index), name=f"Name {index}", email=f"person{index}@example.com") for index in range(2000)]
    complete = run(limited, fixture(directory, "records-exact", rows), timeout=120)
    assert complete["report.json"]["variants"] == complete["report.json"]["contacts"] == 2000
    reject(limited, fixture(directory, "records-above", [rows[0]] * 2001), "import record limit")
    reject(
        limited,
        fixture(directory, "book-records-above", [row("new", name="New")], prior=complete["book.json"]),
        "book record limit",
    )
    prior = copy.deepcopy(complete["book.json"])
    prior["state"]["records"].append(row("new", name="New"))
    prior["sha256"] = digest(prior["state"])
    reject(limited, fixture(directory, "prior-records-above", [], prior=prior), "state record limit")
    together = [row(str(index), email="same@example.com", organization=f"Org {index}") for index in range(2000)]
    grouped = run(limited, fixture(directory, "one-group-exact", together), timeout=120)
    assert len(grouped["review.json"]) == 1 and len(grouped["review.json"][0]["members"]) == 2000
    boundary = row(
        "😀" * 32,
        "s" * 128,
        name="x" * 2048,
        phone="+123456789012345",
        email="x" * 64 + "@" + ".".join(["a" * 63] * 3 + ["b" * 61]),
    )
    run(limited, fixture(directory, "field-bounds", [boundary, row("short-phone", phone="+1234567")]))
    run(limited, fixture(directory, "files-exact", [], batches=[[] for _ in range(15)]))
    rules = [[field] for field in FIELDS] + [["name", field] for field in ["email", "phone", "address"]]
    run(limited, fixture(directory, "rules-exact", sample(), keys=rules))
    fix = fixture(directory, "input-bytes-exact", sample(), batches=[sample()])
    for name in fix.config["inputs"]:
        padded(fix.work / name, 4194304)
    run(limited, fix, timeout=120)
    fix = fixture(directory, "input-bytes-above", [])
    padded(fix.work / "input-1.json", 4194305)
    reject(limited, fix, "input byte limit")
    fix = fixture(directory, "total-bytes-above", [], batches=[[], []])
    for name in fix.config["inputs"][:2]:
        padded(fix.work / name, 4194304)
    reject(limited, fix, "total input")
    tiny = run(limited, fixture(directory, "tiny-prior", [rows[0]]))["book.json"]
    fix = fixture(directory, "prior-bytes-exact", [], prior=tiny)
    padded(fix.work / "prior.json", 8388608)
    run(limited, fix, timeout=120)
    fix = fixture(directory, "prior-bytes-above", [], prior=tiny)
    padded(fix.work / "prior.json", 8388609)
    reject(limited, fix, "input byte limit")
    # Both inputs and the compact book fit; duplicated human-readable value/provenance fields do not.
    wide = [row(str(index), name=str(index).ljust(2048, "x"), address="y" * 1900) for index in range(2000)]
    fix = fixture(directory, "report-overflow", wide[:1000], batches=[wide[1000:]], keys=[["email"]])
    assert all((fix.work / name).stat().st_size <= 4194304 for name in fix.config["inputs"])
    reject(limited, fix, "output exceeds 16 MiB")
    stored = {"version": 1, "keys": [["email"]], "records": wide[:1000]}
    additions = [{**record, "organization": "z" * 1000} for record in wide[1000:]]
    fix = fixture(
        directory,
        "book-bytes-above",
        additions[:500],
        batches=[additions[500:]],
        prior={"state": stored, "sha256": digest(stored)},
        keys=[["email"]],
    )
    reject(limited, fix, "book exceeds 8 MiB")
    # Rejection preserves nested raw data without unbounded pretty-print indentation expansion.
    nested: object = [0] * 100000
    for _ in range(20):
        nested = [nested]
    run(limited, fixture(directory, "large-invalid-record", [nested]), timeout=120)
    return {
        "memory_limit": 268435456,
        "records": 2000,
        "rules": 8,
        "inputs": 16,
        "field_bytes": 2048,
        "total_input_bytes": 8388608,
        "state_bytes": 8388608,
    }


def check(app: Application, directory: Path) -> dict:
    return {
        "merges": check_merges(app, directory),
        "generated": check_generated(app, directory),
        "invalid_records": check_invalid(app, directory),
        "configuration_state_cases": check_configuration_state(app, directory),
        "publication_cases": check_publication(app, directory),
        "path_cases": check_paths(app, directory),
        "limits": check_limits(app, directory),
    }
