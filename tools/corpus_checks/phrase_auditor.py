"""Independent character scanning and longest-common-substring checks for phrase audits."""

# ruff: noqa: PLR1711 - explicit repository returns

from __future__ import annotations

import copy
import hashlib
import itertools
import json
import random
import selectors
import subprocess
import unicodedata
from dataclasses import dataclass
from pathlib import Path

from .common import Application
from .csv_json import canonical


def document(identifier: str, text: str) -> dict:
    return {"id": identifier, "text": text}


def corpus(rows: list) -> dict:
    return {"version": 1, "documents": rows}


def sample() -> dict:
    return corpus(
        [
            document("draft", "The quick brown fox jumps over the lazy dog. Then rests."),
            document("notes", "A quick, brown fox jumps over a fence. STRASSE Café."),
            document("quote", "Quick brown fox jumps over the lazy dog! Straße cafe\u0301."),
            document("unrelated", "Network clients retry failed requests."),
        ]
    )


def normalized(value: dict) -> dict:
    return corpus(sorted(copy.deepcopy(value["documents"]), key=lambda row: row["id"]))


@dataclass
class Fixture:
    work: Path
    config: dict

    @property
    def path(self) -> Path:
        return self.work / "phrase-job.json"

    @property
    def output(self) -> Path:
        return self.work / self.config["output"]

    def save(self) -> None:
        self.path.write_text(json.dumps(self.config, ensure_ascii=False))
        return

    def settings(self, mode: str = "write", **extra: str) -> dict:
        return {
            "PHRASE_CONFIG": str(self.path),
            "PHRASE_MODE": mode,
            "PHRASE_FAIL": "",
            "PHRASE_PAUSE": "",
            "PHRASE_CONTINUE": "",
            **extra,
        }


def fixture(directory: Path, name: str, value: dict, size: int = 3, **changes: object) -> Fixture:
    work = directory / name
    work.mkdir(parents=True)
    fix = Fixture(work, {"documents": "sources.json", "ngram": size, "output": "phrase-audit", **changes})
    (work / "sources.json").write_text(json.dumps(value, ensure_ascii=False))
    fix.save()
    return fix


def tokenize(text: str) -> list:
    tokens = []
    begin = None
    # Scan character ordinals, independently of the application's regular expression/find calls.
    ranges = [(0, 47), (58, 64), (91, 96), (123, 159), (160, 160), (5760, 5760), (8192, 8303), (12288, 12351)]
    for index in range(len(text) + 1):
        separator = index == len(text) or any(low <= ord(text[index]) <= high for low, high in ranges)
        if separator and begin is not None:
            word = unicodedata.normalize("NFC", unicodedata.normalize("NFC", text[begin:index]).casefold())
            tokens.append((word, begin, index))
            begin = None
        elif not separator and begin is None:
            begin = index
    return tokens


def oracle(value: dict, size: int) -> dict:
    docs = normalized(value)["documents"]
    tokens = [tokenize(row["text"]) for row in docs]
    matches = []
    covered = [set() for _ in docs]
    pairs = set()
    for left, right in itertools.combinations(range(len(docs)), 2):
        a, b = tokens[left], tokens[right]
        following = [0] * (len(b) + 1)
        spans = []
        # Suffix-length dynamic programming finds maximal equal runs directly: no n-gram index or merging.
        for i in range(len(a) - 1, -1, -1):
            current = [0] * (len(b) + 1)
            for j in range(len(b) - 1, -1, -1):
                if a[i][0] == b[j][0]:
                    current[j] = following[j + 1] + 1
                    if current[j] >= size and (i == 0 or j == 0 or a[i - 1][0] != b[j - 1][0]):
                        spans.append((i, j, current[j]))
            following = current
        for i, j, length in sorted(spans):
            locations = []
            for number, start in [(left, i), (right, j)]:
                end = start + length
                first, last = tokens[number][start][1], tokens[number][end - 1][2]
                locations.append(
                    {
                        "document": docs[number]["id"],
                        "start_token": start,
                        "end_token": end,
                        "start_char": first,
                        "end_char": last,
                        "text": docs[number]["text"][first:last],
                    }
                )
                covered[number].update(range(start, end))
            matches.append(
                {
                    "left": locations[0],
                    "right": locations[1],
                    "length": length,
                    "tokens": [word[0] for word in a[i : i + length]],
                    "ngram_hits": length - size + 1,
                }
            )
            pairs.add((left, right))
    descriptions = []
    for number, row in enumerate(docs):
        ranges = []
        for index in sorted(covered[number]):
            if ranges and ranges[-1]["end_token"] == index:
                ranges[-1]["end_token"] = index + 1
            else:
                ranges.append({"start_token": index, "end_token": index + 1})
        descriptions.append(
            {
                "id": row["id"],
                "characters": len(row["text"]),
                "bytes": len(row["text"].encode()),
                "tokens": len(tokens[number]),
                "covered_tokens": len(covered[number]),
                "coverage": ranges,
            }
        )
    counts = {
        "documents": len(docs),
        "tokens": sum(len(t) for t in tokens),
        "ngram_windows": sum(max(0, len(t) - size + 1) for t in tokens),
        "ngram_hits": sum(m["ngram_hits"] for m in matches),
        "matches": len(matches),
        "document_pairs": len(pairs),
        "covered_tokens": sum(len(s) for s in covered),
    }
    return {
        "version": 1,
        "ngram": size,
        "tokenizer": "nfc-casefold-ranges-v1",
        "documents_sha256": hashlib.sha256((canonical(normalized(value)) + "\n").encode()).hexdigest(),
        "analysis": {"documents": descriptions, "matches": matches, "counts": counts},
    }


def invariants(value: dict, report: dict) -> None:
    documents = {row["id"]: row["text"] for row in value["documents"]}
    tokens = {key: tokenize(text) for key, text in documents.items()}
    coverage = {key: set() for key in documents}
    for phrase in report["analysis"]["matches"]:
        assert phrase["left"]["document"] < phrase["right"]["document"]
        for side in ["left", "right"]:
            location = phrase[side]
            identifier = location["document"]
            assert documents[identifier][location["start_char"] : location["end_char"]] == location["text"]
            chosen = tokens[identifier][location["start_token"] : location["end_token"]]
            assert [t[0] for t in chosen] == phrase["tokens"] and len(chosen) == phrase["length"]
            assert chosen[0][1] == location["start_char"] and chosen[-1][2] == location["end_char"]
            coverage[identifier].update(range(location["start_token"], location["end_token"]))
        assert phrase["ngram_hits"] == phrase["length"] - report["ngram"] + 1 > 0
    for row in report["analysis"]["documents"]:
        assert row["covered_tokens"] == len(coverage[row["id"]]) <= row["tokens"]
        assert sum(r["end_token"] - r["start_token"] for r in row["coverage"]) == row["covered_tokens"]
    assert report["analysis"]["counts"]["covered_tokens"] == sum(len(s) for s in coverage.values())
    return


def outputs(fix: Fixture, report: dict) -> dict:
    value = json.loads((fix.work / fix.config["documents"]).read_bytes())
    analysis = report["analysis"]
    lines = ["Repeated phrases: " + canonical(analysis["counts"])]
    for phrase in analysis["matches"]:
        left, right = phrase["left"], phrase["right"]
        lines.append(
            canonical(left["document"])
            + " ["
            + str(left["start_char"])
            + ","
            + str(left["end_char"])
            + ") and "
            + canonical(right["document"])
            + " ["
            + str(right["start_char"])
            + ","
            + str(right["end_char"])
            + "): "
            + canonical(phrase["tokens"])
        )
    expected = {
        "documents.json": (canonical(normalized(value)) + "\n").encode(),
        "audit.json": (canonical(report) + "\n").encode(),
        "matches.jsonl": "".join(canonical(row) + "\n" for row in analysis["matches"]).encode(),
        "audit.txt": ("\n".join(lines) + "\n").encode(),
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
    paths = [fix.path, fix.work / fix.config["documents"]]
    original = [path.read_bytes() for path in paths]
    value = json.loads(original[1])
    result = app.run(fix.work, fix.settings(mode), timeout=180)
    assert result.returncode == 0 and not result.stderr, (fix.work, result)
    observed = json.loads(result.stdout)
    expected = oracle(value, fix.config["ngram"])
    assert observed == expected, (fix.work, observed, expected)
    invariants(value, observed)
    assert result.stdout == canonical(observed) + "\n"
    assert original == [path.read_bytes() for path in paths]
    if mode == "write":
        outputs(fix, observed)
    else:
        assert not fix.output.exists()
    assert not list(fix.work.glob(".phrase-audit-*"))
    return observed


def failure(app: Application, fix: Fixture, message: str = "", **extra: str) -> None:
    existed = fix.output.exists() or fix.output.is_symlink()
    before = fix.output.read_bytes() if fix.output.is_file() else None
    result = app.run(fix.work, fix.settings(**extra), timeout=120)
    assert result.returncode == 2 and result.stderr and message in result.stderr and not result.stdout, (
        result,
        message,
    )
    assert (fix.output.exists() or fix.output.is_symlink()) == existed
    if before is not None:
        assert fix.output.read_bytes() == before
    assert not list(fix.work.glob(".phrase-audit-*"))
    return


def scenarios(app: Application, directory: Path) -> dict:
    observations = []
    sequences = [" ".join(words) for length in range(5) for words in itertools.product("ab", repeat=length)]
    chunks = [sequences[i : i + 8] for i in range(0, len(sequences), 8)]
    covered_pairs = set()
    count = pair_count = 0
    for first, second in itertools.combinations_with_replacement(range(len(chunks)), 2):
        texts = chunks[first] + chunks[second]
        value = corpus([document(str(i).zfill(2), text) for i, text in enumerate(texts)])
        for size in range(1, 6):
            observations.append(success(app, fixture(directory, "exhaustive-" + str(count), value, size)))
            count += 1
            pair_count += len(texts) * (len(texts) - 1) // 2
            covered_pairs.update((size, *sorted((a, b))) for a, b in itertools.combinations(texts, 2))
    assert covered_pairs == {
        (size, *sorted((a, b)))
        for size in range(1, 6)
        for a, b in itertools.combinations_with_replacement(sequences, 2)
    }
    print(app.engine + " phrase auditor: exhaustive small sequences, offsets and merging passed", flush=True)
    cases = [
        (sample(), 3),
        (corpus([]), 1),
        (corpus([document("empty", "")]), 2),
        (corpus([document("solo", "a a a a a")]), 1),
        (corpus([document("a", "a a a"), document("b", "a a a a")]), 2),
        (corpus([document("a", "red blue X red blue"), document("b", "red blue Y red blue")]), 2),
        (corpus([document("a", "a--b...c"), document("b", " A b c ")]), 2),
        (corpus([document("a", "🙂 prefix Straße, cafe\u0301 end"), document("b", "STRASSE CAFÉ")]), 2),
        (corpus([document("a", "Σ σ ς İ i\u0307 ﬀ ff"), document("b", "σ σ σ i\u0307 İ ff ﬀ")]), 2),
        (corpus([document('line\n"id', "猫、狗\x00🙂\r\nlast"), document("other", "猫 狗 🙂 last")]), 2),
        (corpus([document("a", "\u1100\u1161 가 Ꭰ ꭰ"), document("b", "가 가 ꭰ Ꭰ")]), 2),
    ]
    randomizer = random.Random(67067)
    vocabulary = ["alpha", "BETA", "Straße", "strasse", "café", "cafe\u0301", "中", "🙂"]
    for _ in range(40):
        docs = []
        for i in range(randomizer.randint(2, 6)):
            words = randomizer.choices(vocabulary, k=randomizer.randint(0, 25))
            text = randomizer.choice([" ", "\n", "--", "\u00a0", "、"]).join(words)
            docs.append(document(str(i), text))
        cases.append((corpus(docs), randomizer.randint(1, 5)))
    for index, (value, size) in enumerate(cases):
        fix = fixture(directory, "case-" + str(index), value, size)
        report = success(app, fix)
        if index == 0:
            assert report["analysis"]["counts"]["covered_tokens"] == 21
        if index == 4:
            assert report["analysis"]["counts"]["matches"] == 4
            assert report["analysis"]["counts"]["ngram_hits"] == 6
            assert report["analysis"]["counts"]["covered_tokens"] == 7
        if index == 5:
            assert report["analysis"]["counts"]["matches"] == 4
            assert report["analysis"]["counts"]["covered_tokens"] == 8
        changed = copy.deepcopy(value)
        randomizer.shuffle(changed["documents"])
        other = fixture(directory, "permuted-" + str(index), changed, size)
        assert success(app, other) == report and outputs(other, report) == outputs(fix, report)
        observations.append(report)
    return {
        "exhaustive_batches": count,
        "exhaustive_document_pairs": pair_count,
        "distinct_sequence_pair_settings": len(covered_pairs),
        "other_corpora": len(cases),
        "generated_corpora": 40,
        "document_permutations": len(cases),
        "reports_sha256": hashlib.sha256(canonical(observations).encode()).hexdigest(),
    }


def invalid_inputs(app: Application, directory: Path) -> int:
    base = corpus([document("a", "one two")])
    variants = [None, [], {}, True, {**base, "extra": 1}, {"version": 1}, {"documents": []}]
    variants += [{**base, "version": value} for value in [0, 2, True, 1.0, "1", None]]
    variants += [{**base, "documents": value} for value in [None, {}, True, ""]]
    row = base["documents"][0]
    malformed = [None, [], {}, True, {**row, "extra": 1}, {"id": "a"}, {"text": "a"}]
    malformed += [{**row, "id": value} for value in ["", "a\x00", "x" * 129, "🙂" * 129, None, True, 1, [], {}]]
    malformed += [{**row, "text": value} for value in [None, True, 1, 1.0, [], {}]]
    variants += [corpus([value]) for value in malformed]
    variants.append(corpus([row, row]))
    for index, value in enumerate(variants):
        failure(app, fixture(directory, "documents-" + str(index), value))
    count = len(variants)
    for index, value in enumerate([0, -1, 17, True, 1.0, "1", None, [], {}]):
        failure(app, fixture(directory, "ngram-" + str(index), base, value))
        count += 1
    for key in ["documents", "output"]:
        for index, value in enumerate(["", "\x00", None, True, 1, [], {}]):
            fix = fixture(directory, f"config-{key}-{index}", base)
            fix.path.write_text(json.dumps({**fix.config, key: value}))
            failure(app, fix)
            count += 1
    for key in ["documents", "ngram", "output"]:
        fix = fixture(directory, "missing-" + key, base)
        fix.path.write_text(json.dumps({k: v for k, v in fix.config.items() if k != key}))
        failure(app, fix)
        count += 1
    fix = fixture(directory, "extra-config", base)
    fix.path.write_text(json.dumps({**fix.config, "extra": 1}))
    failure(app, fix)
    failure(app, fixture(directory, "mode", base), "invalid phrase mode", PHRASE_MODE="bad")
    count += 2
    for name in ["sources.json", "phrase-job.json"]:
        for index, raw in enumerate([b"\xff", b"{", b"[] trailing", b"[NaN]", b"[Infinity]", b'{"a":1,"a":2}']):
            fix = fixture(directory, f"raw-{name}-{index}", base)
            (fix.work / name).write_bytes(raw)
            failure(app, fix)
            count += 1
    return count


def repeated(count: int, prefix: str, gap: int = 0) -> str:
    return " ".join("a" + "." * gap + "b " + prefix + str(i) if gap else "a " + prefix + str(i) for i in range(count))


def limits(app: Application, directory: Path) -> dict:
    success(app, fixture(directory, "documents-exact", corpus([document(str(i), "") for i in range(16)])))
    failure(
        app, fixture(directory, "documents-above", corpus([document(str(i), "") for i in range(17)])), "document count"
    )
    success(app, fixture(directory, "id-exact", corpus([document("🙂" * 128, "")]), 1))
    success(app, fixture(directory, "text-exact", corpus([document("a", "." * 65536)])))
    failure(app, fixture(directory, "text-above", corpus([document("a", "." * 65537)])), "document exceeds 64 KiB")
    docs = [document(str(i), " ".join(("x" if i < 2 else "y") + str(j) for j in range(2048))) for i in range(4)]
    report = success(app, fixture(directory, "combined-capacity", corpus(docs), 16))
    assert report["analysis"]["counts"] == {
        "documents": 4,
        "tokens": 8192,
        "ngram_windows": 8132,
        "ngram_hits": 4066,
        "matches": 2,
        "document_pairs": 2,
        "covered_tokens": 8192,
    }
    failure(
        app, fixture(directory, "corpus-tokens-above", corpus([*docs, document("extra", "extra")])), "corpus exceeds"
    )
    failure(app, fixture(directory, "document-tokens-above", corpus([document("a", "a " * 2049)])), "2048 tokens")
    for index, word in enumerate(["a" * 128, "ß" * 64, "e\u0301" * 64]):
        success(
            app, fixture(directory, "token-exact-" + str(index), corpus([document("a", word), document("b", word)]), 1)
        )
        failure(
            app, fixture(directory, "token-above-" + str(index), corpus([document("a", word + "a")])), "token exceeds"
        )
    report = success(
        app, fixture(directory, "hits-exact", corpus([document("a", "x " * 250), document("b", "x " * 400)]), 1)
    )
    assert report["analysis"]["counts"]["ngram_hits"] == 100000
    assert report["analysis"]["counts"]["covered_tokens"] == 650
    failure(
        app,
        fixture(directory, "hits-above", corpus([document("a", "x " * 250), document("b", "x " * 401)]), 1),
        "hits exceed",
    )
    report = success(
        app,
        fixture(
            directory,
            "matches-exact",
            corpus([document("a", repeated(64, "left")), document("b", repeated(64, "right"))]),
            1,
        ),
    )
    assert report["analysis"]["counts"]["matches"] == 4096
    assert report["analysis"]["counts"]["covered_tokens"] == 128
    failure(
        app,
        fixture(
            directory,
            "matches-above",
            corpus([document("a", repeated(64, "left")), document("b", repeated(65, "right"))]),
            1,
        ),
        "match count exceeds",
    )
    failure(
        app,
        fixture(
            directory,
            "records-above",
            corpus([document("🙂" * 128, repeated(64, "left", 500)), document("🙃" * 128, repeated(64, "right", 500))]),
            2,
        ),
        "records exceed 8 MiB",
    )
    for name, maximum in [("phrase-job.json", 65536), ("sources.json", 2097152)]:
        fix = fixture(directory, "bytes-" + name, sample())
        path = fix.work / name
        raw = path.read_bytes()
        path.write_bytes(raw + b" " * (maximum - len(raw)))
        success(app, fix, "preview")
        path.write_bytes(raw + b" " * (maximum + 1 - len(raw)))
        failure(app, fix, "byte limit")
        path.write_bytes(raw)
    return {
        "documents": 16,
        "document_bytes": 65536,
        "document_tokens": 2048,
        "corpus_tokens": 8192,
        "name_characters": 128,
        "name_bytes": 512,
        "normalized_token_bytes": 128,
        "maximum_ngram": 16,
        "cross_document_hits": 100000,
        "merged_matches": 4096,
        "match_record_bytes": 8388608,
        "config_bytes": 65536,
        "source_bytes": 2097152,
    }


def paused(app: Application, fix: Fixture) -> subprocess.Popen:
    process = subprocess.Popen(
        app.command,
        cwd=fix.work,
        env=app.environment(fix.settings(PHRASE_PAUSE="ready", PHRASE_CONTINUE=str(fix.work / "continue"))),
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
        "documents.json",
        "audit.json",
        "matches.jsonl",
        "audit.txt",
        "manifest.json",
        "ready",
        "published",
    ]
    for point in points:
        fix = fixture(directory, "fault-" + point, sample())
        reference = success(app, fix, "preview")
        result = app.run(fix.work, fix.settings(PHRASE_FAIL=point))
        assert result.returncode == 2 and "injected failure: " + point in result.stderr and not result.stdout
        assert not list(fix.work.glob(".phrase-audit-*"))
        if point == "published":
            outputs(fix, reference)
        else:
            assert not fix.output.exists()
            success(app, fix)
    for name in ["documents", "config", "destination"]:
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
            assert not list(fix.work.glob(".phrase-audit-*"))
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
    abandoned = list(fix.work.glob(".phrase-audit-*"))
    assert len(abandoned) == 1
    old = {path.name: path.read_bytes() for path in abandoned[0].iterdir()}
    result = app.run(fix.work, fix.settings())
    assert result.returncode == 0 and not result.stderr
    outputs(fix, reference)
    assert {path.name: path.read_bytes() for path in abandoned[0].iterdir()} == old
    return len(points) + 4


def paths(app: Application, directory: Path) -> int:
    names = ["sources.json", "phrase-job.json"]
    for name in ["file", "directory", "symlink", "dangling", *names]:
        fix = fixture(directory, "destination-" + name, sample())
        if name == "file":
            fix.output.write_bytes(b"preserve")
        elif name == "directory":
            fix.output.mkdir()
            (fix.output / "keep").write_bytes(b"preserve")
        elif name in ["symlink", "dangling"]:
            fix.output.symlink_to(fix.work / ("sources.json" if name == "symlink" else "missing"))
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
    print(app.engine + " phrase auditor: independent passages, Unicode offsets and coverage passed", flush=True)
    invalid = invalid_inputs(app, directory / "invalid")
    bounds = limits(app, directory / "limits")
    faults = publication(app, directory / "publication")
    path_cases = paths(app, directory / "paths")
    print(app.engine + " phrase auditor: validation, limits, publication and path checks passed", flush=True)
    return {**cases, "invalid_inputs": invalid, "limits": bounds, "publication_cases": faults, "path_cases": path_cases}
