"""Independent JSON/regex INI reading, expansion graphs, edits and publication checks for 075."""

# ruff: noqa: PLR1711 - explicit repository returns
from __future__ import annotations

import hashlib
import json
import random
import re
import selectors
import subprocess
from dataclasses import dataclass
from graphlib import CycleError, TopologicalSorter
from itertools import pairwise
from pathlib import Path

from .common import Application
from .csv_json import canonical


def sample() -> tuple[bytes, list[dict]]:
    text = '# Global fallback\r\nhost = "localhost"\r\n\r\n[server] ; network\r\nport = "8080" # keep\r\nurl = "http://${host}:${port}/"\r\nlabel = "世界 \\"notes\\""\r\nliteral = "$${host} costs $$5"\r\n'
    edits = [
        {"op": "set", "section": "server", "key": "port", "value": "9090"},
        {"op": "set", "section": "client", "key": "endpoint", "value": "${server.url}"},
    ]
    return text.encode(), edits


@dataclass
class Fixture:
    work: Path
    config: dict

    @property
    def path(self) -> Path:
        return self.work / "ini-job.json"

    @property
    def output(self) -> Path:
        return self.work / self.config["output"]

    def save(self) -> None:
        self.path.write_text(json.dumps(self.config))
        return

    def settings(self, mode: str = "write", **extra: str) -> dict:
        return {
            "INI_CONFIG": str(self.path),
            "INI_MODE": mode,
            "INI_FAIL": "",
            "INI_PAUSE": "",
            "INI_CONTINUE": "",
            **extra,
        }


def fixture(directory: Path, name: str, raw_source: bytes, operations: list[dict], **changes: str) -> Fixture:
    work = directory / name
    work.mkdir(parents=True)
    fix = Fixture(work, {"source": "input.ini", "edits": "changes.json", "output": "edited", **changes})
    (work / "input.ini").write_bytes(raw_source)
    (work / "changes.json").write_text(json.dumps(operations, ensure_ascii=False))
    fix.save()
    return fix


def decoded(source: bytes) -> tuple[dict[str, str], list[str]]:
    values = {}
    section = ""
    comments = []
    for line in source.decode().splitlines():
        stripped = line.strip(" \t")
        if not stripped or stripped.startswith(("#", ";")):
            comments.append(line)
            continue
        match = re.fullmatch(r"\[\s*([A-Za-z_][A-Za-z0-9_-]*)\s*\]\s*([#;].*)?", stripped)
        if match:
            section = match[1]
            continue
        match = re.fullmatch(r"([A-Za-z_][A-Za-z0-9_-]*)\s*=\s*(.*)", stripped)
        assert match, (line, source)
        value, end = json.JSONDecoder().raw_decode(match[2])
        assert isinstance(value, str)
        assert not match[2][end:].strip() or match[2][end:].strip().startswith(("#", ";"))
        key = section + "." + match[1]
        assert key not in values
        values[key] = value
    return values, comments


def reference(values: dict[str, str]) -> dict[str, str]:
    cache = {}
    active = []

    def resolve(name: str) -> str:
        if name in cache:
            return cache[name]
        assert name not in active
        active.append(name)

        def replace(match: re.Match) -> str:
            if match[0] == "$$":
                return "$"
            if match[0] == "$":
                return "$"
            target = match[1]
            if "." not in target:
                local = name.split(".")[0] + "." + target
                target = local if local in values else "." + target
            return resolve(target)

        value = re.sub(r"\$\$|\$\{([^}]*)\}|\$", replace, values[name])
        active.pop()
        cache[name] = value
        return value

    for name in values:
        resolve(name)
    return cache


def expected(fix: Fixture) -> dict:
    raw, _comments = decoded((fix.work / fix.config["source"]).read_bytes())
    for edit in json.loads((fix.work / fix.config["edits"]).read_bytes()):
        key = edit["section"] + "." + edit["key"]
        if edit["op"] == "set":
            raw[key] = edit["value"]
        else:
            del raw[key]
    return {"version": 1, "raw": raw, "expanded": reference(raw), "keys": len(raw)}


def outputs(fix: Fixture, report: dict, golden: bytes | None = None) -> dict[str, bytes]:
    files = {path.name: path.read_bytes() for path in fix.output.iterdir()}
    assert set(files) == {"settings.ini", "values.json", "report.json", "input.ini", "edits.json", "manifest.json"}
    assert files["input.ini"] == (fix.work / fix.config["source"]).read_bytes()
    assert files["edits.json"] == (fix.work / fix.config["edits"]).read_bytes()
    assert files["values.json"] == (canonical(report["expanded"]) + "\n").encode()
    assert files["report.json"] == (canonical(report) + "\n").encode()
    assert decoded(files["settings.ini"])[0] == report["raw"]
    assert json.loads(files["manifest.json"]) == {
        "version": 1,
        "files": {
            name: {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}
            for name, raw in files.items()
            if name != "manifest.json"
        },
    }
    if golden is not None:
        assert files["settings.ini"] == golden, (files["settings.ini"], golden)
    return files


def success(app: Application, fix: Fixture, golden: bytes | None = None, mode: str = "write") -> dict:
    paths = [fix.path, fix.work / fix.config["source"], fix.work / fix.config["edits"]]
    original = {path: path.read_bytes() for path in paths}
    result = app.run(fix.work, fix.settings(mode), timeout=90)
    assert result.returncode == 0 and not result.stderr, (fix.work, result)
    report = json.loads(result.stdout)
    assert report == expected(fix), (fix.work, report, expected(fix))
    assert result.stdout == canonical(report) + "\n"
    assert original == {path: path.read_bytes() for path in paths}
    if mode == "write":
        outputs(fix, report, golden)
    else:
        assert not fix.output.exists()
    assert not list(fix.output.parent.glob(".ini-*"))
    return report


def failure(app: Application, fix: Fixture, message: str = "", **extra: str) -> str:
    inputs = [fix.path, fix.work / "input.ini", fix.work / "changes.json"]
    original = {path: path.read_bytes() for path in inputs if path.is_file()}
    existed = fix.output.exists() or fix.output.is_symlink()
    before = fix.output.read_bytes() if fix.output.is_file() else None
    result = app.run(fix.work, fix.settings(**extra), timeout=90)
    assert result.returncode == 2 and result.stderr and message in result.stderr and not result.stdout, (
        fix.work,
        result,
        message,
    )
    assert (fix.output.exists() or fix.output.is_symlink()) == existed
    if before is not None:
        assert fix.output.read_bytes() == before
    assert original == {path: path.read_bytes() for path in original}
    assert not list(fix.output.parent.glob(".ini-*"))
    return result.stderr


def scenarios(app: Application, directory: Path) -> dict:
    fix = fixture(directory, "sample", *sample())
    golden = '# Global fallback\nhost = "localhost"\n\n[server] ; network\nport = "9090" # keep\nurl = "http://${host}:${port}/"\nlabel = "世界 \\"notes\\""\nliteral = "$${host} costs $$5"\n\n[client]\nendpoint = "${server.url}"\n'.encode()
    reports = [success(app, fix, golden)]
    cases = [
        (b"", [], b""),
        (b" \t\n# keep  \n", [], b" \t\n# keep  \n"),
        (b'x="\\n\\t\\u0000\\u4e16\\u754c" ; note', [], 'x = "\\n\\t\\u0000世界" ; note\n'.encode()),
        (b'[s]\nx="a" # remove\n; retained\n', [{"op": "delete", "section": "s", "key": "x"}], b"[s]\n; retained\n"),
        (
            b'[s]\nx="a"\n',
            [
                {"op": "set", "section": "new", "key": "x", "value": "n"},
                {"op": "set", "section": "", "key": "global", "value": "g"},
            ],
            b'global = "g"\n[s]\nx = "a"\n\n[new]\nx = "n"\n',
        ),
        (
            b'a="x"\n[s]\nb="z"\n[t]\nz="1"\n',
            [{"op": "set", "section": "s", "key": "new", "value": "v"}],
            b'a = "x"\n[s]\nb = "z"\nnew = "v"\n[t]\nz = "1"\n',
        ),
        (
            b'[s]\nx="old" # retain\n',
            [{"op": "set", "section": "s", "key": "x", "value": 'a"\\b\n'}],
            b'[s]\nx = "a\\"\\\\b\\n" # retain\n',
        ),
        (b'a="${missing}"\n', [{"op": "set", "section": "", "key": "a", "value": "fixed"}], b'a = "fixed"\n'),
    ]
    for index, (source, edits, golden) in enumerate(cases):
        reports.append(success(app, fixture(directory, f"golden-{index}", source, edits), golden))
    source = 'x = "global"\n[s]\nx = "local"\na = "${x}|${.x}|${s.x}"\nb = "$$${x}|$${missing}|$x|$"\n[t]\na = "${x}|${s.a}"\n'
    reports.append(success(app, fixture(directory, "scope", source.encode(), [])))
    rng = random.Random(750075)
    for index in range(60):
        rows = [
            "# generated document " + str(index),
            "base = "
            + json.dumps(rng.choice(["root", "世界", "<&>", '"\\\n\t']), ensure_ascii=rng.choice([True, False])),
        ]
        edits = []
        for number in range(5):
            section = f"s{number}"
            rows.extend(["", f"[{section}] ; section note"])
            for key in ["name", "link", "unused"]:
                value = (
                    rng.choice(["literal", "世界😀", "${base}", "$${escaped}", "$$$"])
                    if key != "link"
                    else "${base}/" + section
                )
                rows.append(
                    "  " + key + " = " + json.dumps(value, ensure_ascii=rng.choice([True, False])) + " # " + key
                )
            edits.extend(
                [
                    {
                        "op": "set",
                        "section": section,
                        "key": "name",
                        "value": rng.choice(["updated", "${link}", "${.base}"]),
                    },
                    {"op": "delete", "section": section, "key": "unused"},
                ]
            )
        edits.extend(
            [
                {"op": "set", "section": "new", "key": "value", "value": "${s4.name}"},
                {"op": "set", "section": "", "key": "late", "value": "global added last"},
            ]
        )
        fix = fixture(directory, f"generated-{index}", ("\r\n".join(rows) + "\r\n").encode(), edits)
        report = success(app, fix)
        reports.append(report)
        original_comments = decoded((fix.work / "input.ini").read_bytes())[1]
        rewritten_comments = decoded((fix.output / "settings.ini").read_bytes())[1]
        assert rewritten_comments == original_comments + [""]
        # Reparse the actual emitted file with no edits; canonical text must be stable.
        replay = fixture(directory, f"reparsed-{index}", b"", [], source=str(fix.output / "settings.ini"))
        assert success(app, replay) == report
        assert (replay.output / "settings.ini").read_bytes() == (fix.output / "settings.ini").read_bytes()
    return {
        "hand_labeled_documents": len(cases) + 2,
        "generated_edit_round_trips": 60,
        "reports_sha256": hashlib.sha256(canonical(reports).encode()).hexdigest(),
    }


def graphs(app: Application, directory: Path) -> dict:
    names = ["a", "b", "c"]
    edges = [(a, b) for a in names for b in names]
    acyclic = 0
    cyclic = 0
    for mask in range(512):
        graph = {name: [b for bit, (a, b) in enumerate(edges) if a == name and mask & (1 << bit)] for name in names}
        source = "".join(
            name + " = " + json.dumps(name + "".join("${" + target + "}" for target in children)) + "\n"
            for name, children in graph.items()
        ).encode()
        fix = fixture(directory, f"graph-{mask}", source, [])
        try:
            list(TopologicalSorter(graph).static_order())
            cycle = False
        except CycleError:
            cycle = True
        if cycle:
            error = failure(app, fix, "variable cycle: ")
            cyclic += 1
            chain = error.split("variable cycle: ", 1)[1].strip().split(" -> ")
            assert chain[-1] in chain[:-1]
            assert all(b[1:] in graph[a[1:]] for a, b in pairwise(chain))
        else:
            success(app, fix)
            acyclic += 1
    assert (acyclic, cyclic) == (25, 487)
    return {"dependency_graphs": 512, "acyclic_graphs": acyclic, "cycle_witnesses": cyclic}


def invalid_inputs(app: Application, directory: Path) -> int:
    count = 0
    base = {"source": "input.ini", "edits": "changes.json", "output": "edited"}
    configs = [None, [], {}, {**base, "extra": 1}]
    for field in base:
        configs.append({key: value for key, value in base.items() if key != field})
        configs += [{**base, field: value} for value in [None, True, 1, [], {}, "", "missing/item", "a\0b"]]
    for index, value in enumerate(configs):
        fix = fixture(directory, f"config-{index}", *sample())
        fix.path.write_text(json.dumps(value))
        result = app.run(fix.work, fix.settings())
        assert result.returncode == 2 and result.stderr and not result.stdout and not fix.output.exists()
        count += 1
    edits = [None, {}, True, 1, "set", [None], [[]], [{}], [{"op": "other", "section": "", "key": "x"}]]
    set_edit = {"op": "set", "section": "", "key": "x", "value": "test"}
    for field in set_edit:
        edits.append([{key: value for key, value in set_edit.items() if key != field}])
        bad = [None, True, 1, [], {}]
        if field in ["key", "section"]:
            bad += ["1x", "a.b", "x" * 65, "é", "a\0"]
        if field == "key":
            bad += [""]
        edits += [[{**set_edit, field: value}] for value in bad]
    edits += [
        [{**set_edit, "extra": 1}],
        [{"op": "delete", "section": "", "key": "missing"}],
        [{"op": "delete", "section": "", "key": "host", "value": "extra"}],
    ]
    for index, value in enumerate(edits):
        fix = fixture(directory, f"edits-{index}", *sample())
        (fix.work / "changes.json").write_text(json.dumps(value))
        failure(app, fix)
        count += 1
    for filename in ["ini-job.json", "changes.json"]:
        for index, raw in enumerate([b"\xff", b"{", b'[{"x":"\\ud800"}]']):
            fix = fixture(directory, f"json-{filename}-{index}", *sample())
            (fix.work / filename).write_bytes(raw)
            failure(app, fix)
            count += 1
    for index, raw in enumerate([b"\xff", b"# bare\rreturn", b"# control\x00", b"# control\x1c", b"# control\x7f"]):
        failure(app, fixture(directory, f"raw-{index}", raw, []))
        count += 1
    failure(app, fixture(directory, "mode", *sample()), "invalid INI mode", INI_MODE="other")
    edits = [
        {"op": "set", "section": "", "key": "host", "value": "changed"},
        {"op": "delete", "section": "", "key": "missing"},
    ]
    failure(app, fixture(directory, "transaction-failure", sample()[0], edits), "cannot delete missing key")
    edits = [{"op": "set", "section": "", "key": "host", "value": "${host}"}]
    failure(app, fixture(directory, "edit-introduces-cycle", sample()[0], edits), "variable cycle")
    return count + 3


def located_errors(app: Application, directory: Path) -> int:
    cases = [
        ("x = plain", "value must be a quoted string"),
        ("x = 'value'", "value must be a quoted string"),
        ('x = "unfinished', "unclosed quoted string"),
        ('x = "\\q"', "invalid quoted string"),
        ('x = "\\ud800"', "invalid quoted string"),
        ('x = "a" trailing', "expected comment or end of line"),
        ('x "a"', "expected key = quoted string"),
        ('= "a"', "expected key = quoted string"),
        ('1key = "a"', "invalid key name"),
        ('a.b = "a"', "invalid key name"),
        ("[ ]", "invalid section name"),
        ("[]", "invalid section header"),
        ("[section", "invalid section header"),
        ("[a.b]", "invalid section name"),
        ("[s] trailing", "expected comment or end of line"),
    ]
    for index, (line, message) in enumerate(cases):
        failure(
            app, fixture(directory, f"syntax-{index}", ("# Unicode 世界\r\n" + line).encode(), []), "line 2: " + message
        )
    cases2 = [
        ('x="1"\nx="2"', "line 2: duplicate key: .x"),
        ('[s]\nx="1"\nx="2"', "line 3: duplicate key: s.x"),
        ("[s]\n[s]", "line 2: duplicate section: s"),
        ('x="${missing}"', ".x: unknown variable: missing"),
        ('[s]\nx="${t.x}"', "s.x: unknown variable: t.x"),
        ('x="${}"', ".x: invalid variable reference"),
        ('x="${x.y.z}"', ".x: invalid variable reference"),
        ('x="${x.}"', ".x: invalid variable reference"),
        ('x="${unclosed"', ".x: unclosed variable reference"),
        ('x="${x}"', "variable cycle: .x -> .x"),
        ('x="${y}"\ny="${x}"', "variable cycle: .x -> .y -> .x"),
    ]
    for index, (text, message) in enumerate(cases2):
        failure(app, fixture(directory, f"semantic-{index}", text.encode(), []), message)
    source = b'a="ok"\nb="${a}"\n'
    failure(
        app,
        fixture(directory, "dangling-delete", source, [{"op": "delete", "section": "", "key": "a"}]),
        ".b: unknown variable: a",
    )
    # All edits form one transaction; an initially cyclic reference can be repaired before expansion.
    fix = fixture(
        directory, "repair-cycle", b'x="${y}"\ny="${x}"', [{"op": "set", "section": "", "key": "y", "value": "fixed"}]
    )
    assert success(app, fix)["expanded"] == {".x": "fixed", ".y": "fixed"}
    return len(cases) + len(cases2) + 1


def limits(app: Application, directory: Path) -> dict:
    for filename in ["ini-job.json", "changes.json"]:
        for size in [65536, 65537]:
            fix = fixture(directory, f"bytes-{filename}-{size}", *sample())
            p = fix.work / filename
            p.write_bytes(p.read_bytes().ljust(size, b" "))
            if size == 65536:
                success(app, fix)
            else:
                failure(app, fix, "input byte limit")
    source = (b"#" + b"x" * 2046 + b"\n") * 512
    assert len(source) == 1048576
    for extra in [0, 1]:
        fix = fixture(directory, f"input-size-{extra}", source + b"#" * extra, [])
        if not extra:
            success(app, fix, source)
        else:
            failure(app, fix, "input byte limit")
    for count in [2048, 2049]:
        fix = fixture(directory, f"lines-{count}", b"#\n" * count, [])
        if count == 2048:
            success(app, fix)
        else:
            failure(app, fix, "INI exceeds 2048 lines")
    for size in [65536, 65537]:
        fix = fixture(directory, f"line-bytes-{size}", b"#" + b"x" * (size - 1) + b"\n", [])
        if size == 65536:
            success(app, fix)
        else:
            failure(app, fix, "line exceeds 65536 bytes")
    for count in [64, 65]:
        fix = fixture(directory, f"sections-{count}", "".join(f"[s{n}]\n" for n in range(count)).encode(), [])
        if count == 64:
            success(app, fix)
        else:
            failure(app, fix, "more than 64 sections")
    for count in [256, 257]:
        source = "".join(f'k{n}=""\n' for n in range(count)).encode()
        fix = fixture(directory, f"keys-{count}", source, [])
        if count == 256:
            success(app, fix)
        else:
            failure(app, fix, "more than 256 keys")
        edits = [{"op": "set", "section": "", "key": "x", "value": str(n)} for n in range(count)]
        fix = fixture(directory, f"edit-count-{count}", b"", edits)
        if count == 256:
            assert success(app, fix)["raw"] == {".x": "255"}
        else:
            failure(app, fix, "more than 256 edits")
    source = "".join(f"[s{n}]\n" for n in range(64)).encode()
    failure(
        app,
        fixture(directory, "edit-section-over", source, [{"op": "set", "section": "new", "key": "x", "value": "v"}]),
        "more than 64 sections",
    )
    source = "".join(f'k{n}=""\n' for n in range(256)).encode()
    failure(
        app,
        fixture(directory, "edit-key-over", source, [{"op": "set", "section": "", "key": "new", "value": "v"}]),
        "more than 256 keys",
    )
    for count in [64, 65]:
        for kind, source in [("key", ("x" * count) + '="v"'), ("section", "[" + "x" * count + "]")]:
            fix = fixture(directory, f"{kind}-name-{count}", source.encode(), [])
            if count == 64:
                success(app, fix)
            else:
                failure(app, fix, "invalid " + kind + " name")
    for count in [2048, 2049]:
        value = "😀" * count
        source = ("x=" + json.dumps(value)).encode()
        fix = fixture(directory, f"value-bytes-{count}", source, [])
        if count == 2048:
            assert success(app, fix)["raw"] == {".x": value}
        else:
            failure(app, fix, "value exceeds 8192 bytes")
        fix = fixture(
            directory, f"edit-value-bytes-{count}", b"", [{"op": "set", "section": "", "key": "x", "value": value}]
        )
        if count == 2048:
            success(app, fix)
        else:
            failure(app, fix, "edit value exceeds 8192 bytes")
    for count in [512, 513]:
        for kind, value in [("dollars", "$x" * count), ("escaped", "$$" * count), ("references", "${x}" * count)]:
            fix = fixture(directory, f"{kind}-{count}", ('x="v"\ny=' + json.dumps(value)).encode(), [])
            if count == 512:
                success(app, fix)
            else:
                failure(app, fix, "more than 512 dollar tokens")
    base = "x=" + json.dumps("x" * 8192) + "\n"
    for count in [8, 9]:
        fix = fixture(directory, f"expanded-value-{count}", (base + "y=" + json.dumps("${x}" * count)).encode(), [])
        if count == 8:
            assert len(success(app, fix)["expanded"][".y"]) == 65536
        else:
            failure(app, fix, "expanded value exceeds 65536 bytes")
    many = "".join("v" + str(n) + "=" + json.dumps("${x}" * 8) + "\n" for n in range(15))
    for extra in [0, 1]:
        fix = fixture(
            directory,
            f"expanded-total-{extra}",
            (base + many + "last=" + json.dumps("${x}" * 7 + "z" * extra)).encode(),
            [],
        )
        if not extra:
            assert sum(len(v.encode()) for v in success(app, fix)["expanded"].values()) == 1048576
        else:
            failure(app, fix, "expanded values exceed 1 MiB")
    source = (
        "x="
        + json.dumps("\0" * 8192)
        + "\n"
        + "".join("v" + str(n) + "=" + json.dumps("${x}" * 8) + "\n" for n in range(11))
    )
    failure(app, fixture(directory, "export-escape-budget", source.encode(), []), "exports exceed 8 MiB")
    # The longest allowed acyclic variable chain must resolve without recursive application calls.
    source = "".join(f'k{n}="${{k{n+1}}}"\n' for n in range(255)) + 'k255="end"\n'
    assert set(success(app, fixture(directory, "chain-256", source.encode(), []))["expanded"].values()) == {"end"}
    return {
        "config_and_edits_bytes": 65536,
        "source_and_rewritten_bytes": 1048576,
        "lines": 2048,
        "line_bytes": 65536,
        "sections": 64,
        "keys": 256,
        "edits": 256,
        "identifier_characters": 64,
        "raw_value_bytes": 8192,
        "dollar_tokens_per_value": 512,
        "expanded_value_bytes": 65536,
        "total_expanded_bytes": 1048576,
        "export_bytes": 8388608,
        "acyclic_chain_keys": 256,
    }


def paused(app: Application, fix: Fixture) -> subprocess.Popen:
    process = subprocess.Popen(
        app.command,
        cwd=fix.work,
        env=app.environment(fix.settings(INI_PAUSE="ready", INI_CONTINUE=str(fix.work / "continue"))),
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
        "settings.ini",
        "values.json",
        "report.json",
        "input.ini",
        "edits.json",
        "manifest.json",
        "ready",
        "published",
    ]
    for point in points:
        fix = fixture(directory, "fault-" + point, *sample())
        reference = success(app, fix, mode="preview")
        result = app.run(fix.work, fix.settings(INI_FAIL=point))
        assert result.returncode == 2 and "injected failure: " + point in result.stderr and not result.stdout
        assert not list(fix.work.glob(".ini-*"))
        if point == "published":
            outputs(fix, reference)
        else:
            assert not fix.output.exists()
            success(app, fix)
    for name in ["input.ini", "changes.json", "config", "destination"]:
        fix = fixture(directory, "changed-" + name, *sample())
        process = paused(app, fix)
        try:
            if name == "destination":
                fix.output.mkdir()
                (fix.output / "keep").write_bytes(b"another writer")
            else:
                path = fix.path if name == "config" else fix.work / name
                with path.open("ab") as stream:
                    stream.write(b" ")
            (fix.work / "continue").touch()
            output, error = process.communicate(timeout=20)
            assert process.returncode == 2 and error and not output
            assert not list(fix.work.glob(".ini-*"))
            if name == "destination":
                assert list(fix.output.iterdir()) == [fix.output / "keep"]
                assert (fix.output / "keep").read_bytes() == b"another writer"
            else:
                assert "input changed before publication" in error and not fix.output.exists()
        finally:
            stop(process)
    fix = fixture(directory, "killed", *sample())
    reference = success(app, fix, mode="preview")
    process = paused(app, fix)
    stop(process)
    assert not fix.output.exists()
    abandoned = list(fix.work.glob(".ini-*"))
    assert len(abandoned) == 1
    old = {path.name: path.read_bytes() for path in abandoned[0].iterdir()}
    result = app.run(fix.work, fix.settings())
    assert result.returncode == 0 and not result.stderr
    outputs(fix, reference)
    assert {path.name: path.read_bytes() for path in abandoned[0].iterdir()} == old
    return len(points) + 5


def paths(app: Application, directory: Path) -> int:
    names = ["input.ini", "changes.json", "ini-job.json"]
    for name in ["file", "directory", "symlink", "dangling", *names]:
        fix = fixture(directory, "destination-" + name, *sample())
        if name == "file":
            fix.output.write_bytes(b"preserve")
        elif name == "directory":
            fix.output.mkdir()
            (fix.output / "keep").write_bytes(b"preserve")
        elif name in ["symlink", "dangling"]:
            fix.output.symlink_to(fix.work / ("changes.json" if name == "symlink" else "missing"))
        else:
            fix.config["output"] = name
            fix.save()
        failure(app, fix, "output directory already exists")
        if name == "directory":
            assert list(fix.output.iterdir()) == [fix.output / "keep"]
            assert (fix.output / "keep").read_bytes() == b"preserve"
        elif name in ["symlink", "dangling"]:
            assert fix.output.is_symlink()
            assert fix.output.readlink() == fix.work / ("changes.json" if name == "symlink" else "missing")
    for name in names:
        fix = fixture(directory, "symlink-" + name, *sample())
        path = fix.work / name
        path.rename(fix.work / "original")
        path.symlink_to(fix.work / "original")
        original = (fix.work / "original").read_bytes()
        failure(app, fix, "regular file")
        assert path.is_symlink() and (fix.work / "original").read_bytes() == original
    fix = fixture(directory, "readonly", *sample())
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
    fix = fixture(directory, "nested-inputs", *sample())
    nested = fix.work / "nested"
    nested.mkdir()
    (fix.work / "input.ini").rename(nested / "input.ini")
    (fix.work / "changes.json").rename(nested / "changes.json")
    fix.config.update(source="nested/input.ini", edits="nested/../nested/changes.json")
    fix.save()
    success(app, fix)
    return 12


def check(app: Application, directory: Path) -> dict:
    result = scenarios(app, directory / "scenarios")
    result.update(graphs(app, directory / "graphs"))
    print(app.engine + " INI editor: quoted values, comment/edit round trips and dependency graphs passed", flush=True)
    result["located_errors"] = located_errors(app, directory / "locations")
    result["invalid_inputs"] = invalid_inputs(app, directory / "invalid")
    result["limits"] = limits(app, directory / "limits")
    result["publication_cases"] = publication(app, directory / "publication")
    result["path_cases"] = paths(app, directory / "paths")
    print(app.engine + " INI editor: source errors, capacities, publication and path checks passed", flush=True)
    return result
