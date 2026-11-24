"""Independent template trees, include graphs, located failures and durable publication checks for 073."""

# ruff: noqa: PLR1711 - explicit repository returns

from __future__ import annotations

import hashlib
import html
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


def sample() -> tuple[dict[str, bytes], list[tuple[str, str, bytes, int]]]:
    templates = {
        "page": b"<h1>{{ title }}</h1>\n{% if items %}<ul>{% for item in items %}{% include item %}{% endfor %}</ul>{% else %}<p>Empty</p>{% endif %}\n{{ item }}\n",
        "item": b"<li>{{ item.name }}: {% if item.done %}done{% else %}pending{% endif %}</li>",
    }
    data = {
        "title": "Notes <&>",
        "items": [{"name": "First", "done": True}, {"name": "世界", "done": False}],
        "item": "outer binding preserved",
    }
    return templates, [("index", "page", json.dumps(data, ensure_ascii=False).encode(), 1000)]


def sample_expected() -> dict[str, tuple[str, int]]:
    return {
        "index": (
            "<h1>Notes &lt;&amp;&gt;</h1>\n<ul><li>First: done</li><li>世界: pending</li></ul>\nouter binding preserved\n",
            26,
        )
    }


@dataclass
class Fixture:
    work: Path
    config: dict

    @property
    def path(self) -> Path:
        return self.work / "template-job.json"

    @property
    def manifest(self) -> Path:
        return self.work / self.config["project"]

    @property
    def output(self) -> Path:
        return self.work / self.config["output"]

    def save(self) -> None:
        self.path.write_text(json.dumps(self.config, ensure_ascii=False))
        return

    def settings(self, mode: str = "write", **extra: str) -> dict:
        return {
            "TEMPLATE_CONFIG": str(self.path),
            "TEMPLATE_MODE": mode,
            "TEMPLATE_FAIL": "",
            "TEMPLATE_PAUSE": "",
            "TEMPLATE_CONTINUE": "",
            **extra,
        }


def fixture(
    directory: Path, name: str, templates: dict[str, bytes], jobs: list[tuple[str, str, bytes, int]], **changes: object
) -> Fixture:
    work = directory / name
    work.mkdir(parents=True)
    fix = Fixture(work, {"project": "project.json", "output": "rendered", **changes})
    entries = []
    for index, (identifier, raw) in enumerate(templates.items()):
        filename = f"input-{index}.txt"
        (work / filename).write_bytes(raw)
        entries.append({"id": identifier, "source": filename})
    tasks = []
    for index, (identifier, target, raw, steps) in enumerate(jobs):
        filename = f"input-data-{index}.json"
        (work / filename).write_bytes(raw)
        tasks.append({"id": identifier, "template": target, "data": filename, "steps": steps})
    (work / "project.json").write_text(
        json.dumps({"version": 1, "templates": entries, "jobs": tasks}, ensure_ascii=False)
    )
    fix.save()
    return fix


def inputs(fix: Fixture) -> tuple[dict, dict[str, bytes], dict[str, bytes]]:
    project = json.loads(fix.manifest.read_bytes())
    templates = {row["id"]: (fix.manifest.parent / row["source"]).read_bytes() for row in project["templates"]}
    data = {row["id"]: (fix.manifest.parent / row["data"]).read_bytes() for row in project["jobs"]}
    return project, templates, data


def outputs(fix: Fixture, report: dict, expected: dict[str, tuple[str, int]] | None = None) -> dict[str, bytes]:
    project, templates, data = inputs(fix)
    files = {p.name: p.read_bytes() for p in fix.output.iterdir()}
    names = {"project.json", "report.json", "manifest.json"}
    names |= {f"source-{index}.txt" for index in range(len(templates))}
    names |= {f"data-{index}.json" for index in range(len(data))}
    names |= {row["id"] + ".html" for row in project["jobs"]}
    assert set(files) == names
    for index, row in enumerate(project["templates"]):
        assert files[f"source-{index}.txt"] == templates[row["id"]]
    for index, (row, observed) in enumerate(zip(project["jobs"], report["jobs"], strict=True)):
        assert files[f"data-{index}.json"] == data[row["id"]]
        raw = files[row["id"] + ".html"]
        assert observed == {
            "id": row["id"],
            "template": row["template"],
            "steps": observed["steps"],
            "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest(),
        }
        assert 0 <= observed["steps"] <= row["steps"]
        if expected is not None:
            text, steps = expected[row["id"]]
            assert raw == text.encode() and observed["steps"] == steps, (fix.work, row["id"], raw, text, observed)
    exported = {
        "version": 1,
        "templates": [{**row, "source": f"source-{index}.txt"} for index, row in enumerate(project["templates"])],
        "jobs": [{**row, "data": f"data-{index}.json"} for index, row in enumerate(project["jobs"])],
    }
    assert files["project.json"] == (canonical(exported) + "\n").encode()
    assert files["report.json"] == (canonical(report) + "\n").encode()
    assert json.loads(files["manifest.json"]) == {
        "version": 1,
        "files": {
            name: {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}
            for name, raw in files.items()
            if name != "manifest.json"
        },
    }
    return files


def success(
    app: Application, fix: Fixture, expected: dict[str, tuple[str, int]] | None = None, mode: str = "write"
) -> dict:
    project, _templates, _data = inputs(fix)
    paths = [fix.path, fix.manifest]
    paths += [fix.manifest.parent / row["source"] for row in project["templates"]]
    paths += [fix.manifest.parent / row["data"] for row in project["jobs"]]
    original = {path: path.read_bytes() for path in paths}
    result = app.run(fix.work, fix.settings(mode), timeout=180)
    assert result.returncode == 0 and not result.stderr, (fix.work, result)
    report = json.loads(result.stdout)
    assert set(report) == {"version", "templates", "jobs"}
    assert report["version"] == 1 and report["templates"] == len(project["templates"])
    assert len(report["jobs"]) == len(project["jobs"])
    assert result.stdout == canonical(report) + "\n"
    assert original == {path: path.read_bytes() for path in paths}
    if expected is not None:
        for row, observed in zip(project["jobs"], report["jobs"], strict=True):
            text, steps = expected[row["id"]]
            assert observed == {
                "id": row["id"],
                "template": row["template"],
                "steps": steps,
                "bytes": len(text.encode()),
                "sha256": hashlib.sha256(text.encode()).hexdigest(),
            }, (fix.work, observed, text, steps)
    if mode == "write":
        outputs(fix, report, expected)
    else:
        assert not fix.output.exists()
    assert not list(fix.output.parent.glob(".template-*"))
    return report


def failure(app: Application, fix: Fixture, message: str = "", **extra: str) -> str:
    existed = fix.output.exists() or fix.output.is_symlink()
    before = fix.output.read_bytes() if fix.output.is_file() else None
    result = app.run(fix.work, fix.settings(**extra), timeout=180)
    assert result.returncode == 2 and result.stderr and message in result.stderr and not result.stdout, (
        fix.work,
        result,
        message,
    )
    assert (fix.output.exists() or fix.output.is_symlink()) == existed
    if before is not None:
        assert fix.output.read_bytes() == before
    assert not list(fix.output.parent.glob(".template-*"))
    return result.stderr


def normalized(nodes: list[tuple]) -> list[tuple]:
    result = []
    for node in nodes:
        if node[0] == "text":
            if not node[1]:
                continue
            if result and result[-1][0] == "text":
                result[-1] = ("text", result[-1][1] + node[1])
                continue
        if node[0] == "if":
            node = (*node[:2], normalized(node[2]), normalized(node[3]))
        elif node[0] == "for":
            node = (*node[:3], normalized(node[3]))
        result.append(node)
    return result


def encode_nodes(nodes: list[tuple]) -> str:
    result = []
    for node in nodes:
        kind = node[0]
        if kind == "text":
            result.append(node[1])
        elif kind == "value":
            result.append("{{ " + node[1] + " }}")
        elif kind == "include":
            result.append("{% include " + node[1] + " %}")
        elif kind == "if":
            result.append(
                "{% if "
                + node[1]
                + " %}"
                + encode_nodes(node[2])
                + "{% else %}"
                + encode_nodes(node[3])
                + "{% endif %}"
            )
        else:
            result.append("{% for " + node[1] + " in " + node[2] + " %}" + encode_nodes(node[3]) + "{% endfor %}")
    return "".join(result)


def lookup(path: str, scope: dict) -> object:
    value = scope
    for field in path.split("."):
        value = value[field]
    return value


def reference(nodes: list[tuple], templates: dict[str, list[tuple]], scope: dict) -> tuple[str, int]:
    output = []
    steps = 0
    for node in nodes:
        kind = node[0]
        steps += 1
        if kind == "text":
            output.append(node[1])
        elif kind == "value":
            value = lookup(node[1], scope)
            assert value is None or type(value) in [str, int, float, bool]
            raw = "" if value is None else value if isinstance(value, str) else canonical(value)
            output.append(html.escape(raw, quote=True).replace("&#x27;", "&#39;"))
        elif kind == "include":
            text, count = reference(templates[node[1]], templates, scope)
            output.append(text)
            steps += count
        elif kind == "if":
            branch = node[2] if lookup(node[1], scope) else node[3]
            text, count = reference(branch, templates, scope)
            output.append(text)
            steps += count
        else:
            for value in lookup(node[2], scope):
                text, count = reference(node[3], templates, {**scope, node[1]: value})
                output.append(text)
                steps += 1 + count
    return "".join(output), steps


def random_nodes(rng: random.Random, depth: int, bound: bool = False) -> list[tuple]:
    result = []
    for _index in range(rng.randrange(1, 4)):
        kind = rng.choice(["text", "value", "include", *(["if", "for"] if depth else [])])
        if kind == "text":
            result.append(("text", rng.choice(["<p>é & raw</p>", "\r\nprefix\t", "}", ""])))
        elif kind == "value":
            result.append(("value", rng.choice(["title", "value", "amount", *(["entry.name"] if bound else [])])))
        elif kind == "include":
            result.append(("include", "snippet"))
        elif kind == "if":
            result.append(("if", "flag", random_nodes(rng, depth - 1, bound), random_nodes(rng, depth - 1, bound)))
        else:
            result.append(("for", "entry", "rows", random_nodes(rng, depth - 1, True)))
    return normalized(result)


def render_cases(app: Application, directory: Path) -> dict:
    seen = []
    fix = fixture(directory, "sample", *sample())
    seen.append(success(app, fix, sample_expected()))
    cases = [
        (b"", {}, "", 0),
        (b"literal {{x}}", {"x": None}, "literal ", 2),
        (b"{{ value }}", {"value": "<script>&\"'"}, "&lt;script&gt;&amp;&quot;&#39;", 1),
        ("é😀\r\n{{ value }}\r\n".encode(), {"value": "世界"}, "é😀\r\n世界\r\n", 3),
        (b"{% if yes %}{{ missing }}{% else %}okay{% endif %}", {"yes": False}, "okay", 2),
        (b"{% if yes %}okay{% else %}{{ missing }}{% endif %}", {"yes": True}, "okay", 2),
        (b"{% if yes %}{% endif %}", {"yes": False}, "", 1),
        (b"{% for x in values %}{{ missing }}{% endfor %}", {"values": []}, "", 1),
        (b"{{ \n x \t }}", {"x": "okay"}, "okay", 1),
        (b"{%  if   yes  %}yes{%  else  %}no{% endif %}", {"yes": []}, "no", 2),
        (b"}} %} { ordinary }", {}, "}} %} { ordinary }", 1),
        (b"{{ _root._field }}", {"_root": {"_field": 42}}, "42", 1),
    ]
    for index, (text, data, expected, steps) in enumerate(cases):
        fix = fixture(
            directory,
            f"golden-{index}",
            {"page": text},
            [("index", "page", json.dumps(data, ensure_ascii=False).encode(), steps)],
        )
        seen.append(success(app, fix, {"index": (expected, steps)}))
    fix = fixture(directory, "duplicate-data-key", {"page": b"{{x}}"}, [("index", "page", b'{"x":1,"x":2}', 1)])
    seen.append(success(app, fix, {"index": ("2", 1)}))
    templates = {
        "page": [
            ("text", "<main>"),
            ("value", "title"),
            ("text", "|"),
            ("if", "flag", [("text", "<b>"), ("value", "value"), ("text", "</b>")], [("text", "off")]),
            ("text", "|"),
            ("for", "row", "items", [("include", "item")]),
            ("text", "|"),
            ("value", "row"),
            ("text", "</main>"),
        ],
        "item": [
            ("text", "<i>"),
            ("value", "row.name"),
            ("text", ":"),
            ("if", "row.flag", [("text", "yes")], [("text", "no")]),
            ("text", ":"),
            ("for", "row", "row.children", [("value", "row"), ("text", ",")]),
            ("text", ":"),
            ("value", "row.name"),
            ("text", "</i>"),
        ],
    }
    truths = [None, False, True, 0, 1, -1, 0.0, -0.0, 1e-300, "", "false", [], [0], {}, {"x": 0}]
    scalars = [
        None,
        False,
        True,
        0,
        -1,
        9223372036854775807,
        -9223372036854775808,
        1.5,
        -0.0,
        "<script>&\"'",
        "世界😀",
        "é\u0301",
        "\t\n",
    ]
    rng = random.Random(73073)
    for index in range(120):
        data = {
            "title": '<Notes> & "test"',
            "flag": truths[index % len(truths)],
            "value": rng.choice(scalars),
            "row": "outer",
        }
        data["items"] = [
            {
                "name": rng.choice(["Ada", "世界", "<Bob>"]),
                "flag": rng.choice(truths),
                "children": [rng.choice(scalars) for _ in range(rng.randrange(4))],
            }
            for _ in range(rng.randrange(6))
        ]
        expected, steps = reference(templates["page"], templates, data)
        fix = fixture(
            directory,
            f"scope-{index}",
            {name: encode_nodes(nodes).encode() for name, nodes in templates.items()},
            [("index", "page", json.dumps(data, ensure_ascii=False).encode(), steps)],
        )
        seen.append(success(app, fix, {"index": (expected, steps)}))
        if index < 20:
            project = json.loads(fix.manifest.read_bytes())
            project["jobs"][0]["steps"] = steps - 1
            fix.manifest.write_text(json.dumps(project))
            fix.config["output"] = "under-budget"
            fix.save()
            failure(app, fix, "render step budget exhausted")
    for index in range(60):
        nodes = random_nodes(rng, 5)
        templates = {"page": nodes, "snippet": [("text", "<i>"), ("value", "title"), ("text", "</i>")]}
        data = {
            "flag": rng.choice(truths),
            "title": "世界 <&>",
            "amount": rng.choice(scalars),
            "value": rng.choice(scalars),
            "rows": [{"name": "A"}, {"name": "B<&>"}][: rng.randrange(3)],
        }
        expected, steps = reference(nodes, templates, data)
        assert steps <= 10000
        fix = fixture(
            directory,
            f"tree-{index}",
            {name: encode_nodes(body).encode() for name, body in templates.items()},
            [("index", "page", json.dumps(data, ensure_ascii=False).encode(), steps)],
        )
        seen.append(success(app, fix, {"index": (expected, steps)}))
    return {
        "hand_labeled_cases": len(cases),
        "scope_and_truth_cases": 120,
        "truth_values": len(truths),
        "generated_template_trees": 60,
        "one_step_short_rejections": 20,
        "render_reports_sha256": hashlib.sha256(canonical(seen).encode()).hexdigest(),
    }


def include_graphs(app: Application, directory: Path) -> dict:
    names = ["t0", "t1", "t2"]
    edges = [(a, b) for a in names for b in names]
    acyclic = 0
    cyclic = 0
    for mask in range(512):
        graph = {name: [b for bit, (a, b) in enumerate(edges) if a == name and mask & (1 << bit)] for name in names}
        templates = {
            name: (
                name
                + "\n{% if enabled %}\n"
                + "".join("{% include " + target + " %}\n" for target in targets)
                + "{% endif %}\n"
            ).encode()
            for name, targets in graph.items()
        }
        fix = fixture(directory, f"graph-{mask}", templates, [("index", "t0", b'{"enabled":false}', 100)])
        try:
            list(TopologicalSorter(graph).static_order())
            cycle = False
        except CycleError:
            cycle = True
        if cycle:
            cyclic += 1
            error = failure(app, fix, "include cycle:")
            match = re.search(r"(t[012]):([0-9]+):1: include cycle: (.*)", error)
            assert match, error
            chain = match[3].split(" -> ")
            assert len(chain) >= 2 and chain[-1] in chain[:-1]
            assert all(b in graph[a] for a, b in pairwise(chain))
            assert match[1] == chain[-2] and int(match[2]) == 3 + graph[chain[-2]].index(chain[-1])
        else:
            acyclic += 1
            success(app, fix, {"index": ("t0\n\n", 3)})
    assert (acyclic, cyclic) == (25, 487)
    return {
        "include_graphs": 512,
        "acyclic_graphs": acyclic,
        "cycle_witnesses_and_locations": cyclic,
        "inactive_include_edges_checked": True,
    }


def located_errors(app: Application, directory: Path) -> int:
    cases = [
        ("{{", "unclosed template token", "{{"),
        ("{%", "unclosed template token", "{%"),
        ("{{ }}", "invalid expression length", "{{"),
        ("{{ a..b }}", "expression requires dotted identifiers", "{{"),
        ("{{ a[0] }}", "expression requires dotted identifiers", "{{"),
        ("{{ x + y }}", "expression requires dotted identifiers", "{{"),
        ("{{ 1 }}", "expression requires dotted identifiers", "{{"),
        ('{{ "x" }}', "expression requires dotted identifiers", "{{"),
        ("{{ absent }}", "missing variable: absent", "{{"),
        ("{{ object.missing }}", "missing field: object.missing", "{{"),
        ("{{ scalar.field }}", "missing field: scalar.field", "{{"),
        ("{{ object }}", "substitution requires a scalar", "{{"),
        ("{{ values }}", "substitution requires a scalar", "{{"),
        ("{% if missing %}x{% endif %}", "missing variable: missing", "{% if"),
        ("{% for x in scalar %}x{% endfor %}", "for requires an array", "{% for"),
        ("{% else %}", "unexpected closing template command", "{% else"),
        ("{% endif %}", "unexpected closing template command", "{% endif"),
        ("{% endfor %}", "unexpected closing template command", "{% endfor"),
        ("{% if yes %}x", "if requires endif", "{% if"),
        ("{% if yes %}{% endfor %}", "if requires endif", "{% if"),
        ("{% if yes %}a{% else %}b{% else %}c{% endif %}", "if requires endif", "{% if"),
        ("{% for x in values %}x", "for requires endfor", "{% for"),
        ("{% for x in values %}{% endif %}", "for requires endfor", "{% for"),
        ("{% for x in values %}{% else %}x{% endfor %}", "for requires endfor", "{% for"),
        ("{% if %}", "invalid template command", "{% if"),
        ("{% if yes no %}x{% endif %}", "if requires one expression", "{% if"),
        ("{% for x of values %}x{% endfor %}", "invalid for command", "{% for"),
        ("{% for 1 in values %}x{% endfor %}", "invalid for command", "{% for"),
        ("{% include %}", "invalid template command", "{% include"),
        ('{% include "page" %}', "include requires a template identifier", "{% include"),
        ("{% include missing %}", "unknown included template: missing", "{% include"),
        ("{% if no %}{% include missing %}{% endif %}", "unknown included template: missing", "{% include"),
        ("{% include page %}", "include cycle: page -> page", "{% include"),
        ("{% unknown x %}", "unknown template command: unknown", "{% unknown"),
        ("{% if\tyes %}x{% endif %}", "invalid template command", "{% if"),
        ("{{ x }}", "render step budget exhausted", "{{"),
    ]
    data = {"yes": True, "no": False, "scalar": 1, "object": {}, "values": [], "x": "value"}
    for index, (body, message, marker) in enumerate(cases):
        text = "é😀\r\n\t " + body
        offset = text.index(marker)
        prefix = text[:offset]
        location = f"page:{prefix.count(chr(10)) + 1}:{len(prefix.rsplit(chr(10), 1)[-1]) + 1}: "
        fix = fixture(
            directory,
            f"located-{index}",
            {"page": text.encode()},
            [("index", "page", json.dumps(data).encode(), 0 if index == len(cases) - 1 else 100)],
        )
        # A zero budget encounters the literal prefix first, which starts at 1:1.
        if index == len(cases) - 1:
            location = "page:1:1: "
        failure(app, fix, location + message)
    return len(cases)


def invalid_inputs(app: Application, directory: Path) -> int:
    count = 0
    jobs = [
        None,
        [],
        {},
        {"project": "project.json"},
        {"output": "out"},
        {"project": "project.json", "output": "out", "extra": 1},
    ]
    jobs += [{"project": value, "output": "out"} for value in [None, 1, True, [], {}, "", "missing", "a\0b"]]
    jobs += [
        {"project": "project.json", "output": value} for value in [None, 1, True, [], {}, "", "a\0b", "absent/out"]
    ]
    for index, job in enumerate(jobs):
        fix = fixture(directory, f"config-{index}", *sample())
        fix.path.write_text(json.dumps(job))
        result = app.run(fix.work, fix.settings())
        assert result.returncode == 2 and result.stderr and not result.stdout and not fix.output.exists()
        count += 1
    base = {
        "version": 1,
        "templates": [{"id": "page", "source": "input-0.txt"}],
        "jobs": [{"id": "index", "template": "page", "data": "input-data-0.json", "steps": 100}],
    }
    values = [None, [], {}, {**base, "extra": 1}]
    values += [{key: value for key, value in base.items() if key != missing} for missing in base]
    values += [{**base, "version": value} for value in [None, True, 0, 2, "1", 1.5]]
    for field in ["templates", "jobs"]:
        values += [{**base, field: value} for value in [None, True, 1, {}, [], [None], [[]], [{}], ["x"]]]
    for field in ["templates", "jobs"]:
        row = base[field][0]
        bad = [{**row, "extra": 1}]
        bad += [{key: value for key, value in row.items() if key != missing} for missing in row]
        bad += [{**row, "id": value} for value in [None, True, 1, "", "1x", "a-b", "a/b", "..", "é", "a\0", "x" * 65]]
        path_field = "source" if field == "templates" else "data"
        bad += [{**row, path_field: value} for value in [None, True, 1, {}, "", "absent", "a\0b"]]
        if field == "jobs":
            bad += [{**row, "template": value} for value in [None, 1, True, "", "missing"]]
            bad += [{**row, "steps": value} for value in [None, True, -1, 10001, 1.5, "1", [], {}]]
        values += [{**base, field: [item]} for item in bad]
        values.append({**base, field: [row, row]})
    values.append({**base, "templates": [base["templates"][0], {"id": "other", "source": "input-0.txt"}]})
    for index, value in enumerate(values):
        fix = fixture(directory, f"manifest-{index}", {"page": b"x"}, [("index", "page", b"{}", 100)])
        fix.manifest.write_text(json.dumps(value))
        failure(app, fix)
        count += 1
    for index, raw in enumerate(
        [
            b"null",
            b"[]",
            b"true",
            b"1",
            b'"text"',
            b"{",
            b"\xff",
            b'{"x":NaN}',
            b'{"x":9223372036854775808}',
            b'{"x":"\\ud800"}',
            b'{"x":1e999}',
        ]
    ):
        fix = fixture(directory, f"data-{index}", {"page": b""}, [("index", "page", raw, 100)])
        failure(app, fix)
        count += 1
    for filename in ["template-job.json", "project.json"]:
        for index, raw in enumerate([b"\xff", b"{", b'{"x":1,"x":2}']):
            fix = fixture(directory, f"json-{filename}-{index}", *sample())
            (fix.work / filename).write_bytes(raw)
            failure(app, fix)
            count += 1
    fix = fixture(directory, "utf8-template", {"page": b"\xff"}, [("index", "page", b"{}", 100)])
    failure(app, fix)
    fix = fixture(directory, "mode", *sample())
    failure(app, fix, "invalid template mode", TEMPLATE_MODE="unknown")
    return count + 2


def limits(app: Application, directory: Path) -> dict:
    for number in [32, 33]:
        fix = fixture(
            directory, f"templates-{number}", {f"t{n}": b"" for n in range(number)}, [("index", "t0", b"{}", 0)]
        )
        if number == 32:
            success(app, fix, {"index": ("", 0)})
        else:
            failure(app, fix, "template/job count")
        fix = fixture(directory, f"jobs-{number}", {"page": b""}, [(f"j{n}", "page", b"{}", 0) for n in range(number)])
        if number == 32:
            success(app, fix, {f"j{n}": ("", 0) for n in range(number)})
        else:
            failure(app, fix, "template/job count")
    for size in [65536, 65537]:
        fix = fixture(directory, f"template-bytes-{size}", {"page": b"x" * size}, [("index", "page", b"{}", 100)])
        if size == 65536:
            success(app, fix, {"index": ("x" * size, 1)})
        else:
            failure(app, fix, "input byte limit")
    sources = {f"t{n}": b"x" * 65536 for n in range(16)}
    fix = fixture(directory, "source-combined-exact", sources, [("index", "t0", b"{}", 100)])
    success(app, fix, {"index": ("x" * 65536, 1)})
    fix = fixture(directory, "source-combined-over", {**sources, "extra": b"x"}, [("index", "t0", b"{}", 100)])
    failure(app, fix, "combined template sources")
    for size in [1048576, 1048577]:
        fix = fixture(directory, f"data-bytes-{size}", {"page": b""}, [("index", "page", b"{}".ljust(size, b" "), 0)])
        if size == 1048576:
            success(app, fix, {"index": ("", 0)})
        else:
            failure(app, fix, "input byte limit")
    jobs = [(f"j{n}", "page", b"{}".ljust(1048576, b" "), 100) for n in range(4)]
    fix = fixture(directory, "input-combined-exact", {"page": b""}, jobs)
    success(app, fix, {f"j{n}": ("", 0) for n in range(4)})
    fix = fixture(directory, "input-combined-over", {"page": b"x"}, jobs)
    failure(app, fix, "combined input bytes")
    for filename in ["template-job.json", "project.json"]:
        for size in [65536, 65537]:
            fix = fixture(directory, f"json-{filename}-{size}", *sample())
            path = fix.work / filename
            path.write_bytes(path.read_bytes().ljust(size, b" "))
            if size == 65536:
                success(app, fix, sample_expected())
            else:
                failure(app, fix, "input byte limit")
    for size in [256, 257]:
        field = "x" * size
        fix = fixture(
            directory,
            f"expression-{size}",
            {"page": ("{{ " + field + " }}").encode()},
            [("index", "page", json.dumps({field: "okay"}).encode(), 1)],
        )
        if size == 256:
            success(app, fix, {"index": ("okay", 1)})
        else:
            failure(app, fix, "invalid expression length")
    name = "x" * 64
    fix = fixture(
        directory,
        "identifiers-exact",
        {
            "page": (
                "{% for " + name + " in values %}{{ " + name + " }}{% endfor %}{% include " + name + " %}"
            ).encode(),
            name: b"!",
        },
        [(name, "page", b'{"values":[1]}', 100)],
    )
    success(app, fix, {name: ("1!", 5)})
    for keyword, body in [
        ("include", "{% include " + "x" * 65 + " %}"),
        ("for", "{% for " + "x" * 65 + " in values %}{% endfor %}"),
    ]:
        fix = fixture(
            directory, "binding-over-" + keyword, {"page": body.encode()}, [("index", "page", b'{"values":[]}', 100)]
        )
        failure(app, fix, "include requires" if keyword == "include" else "invalid for command")
    for depth in [12, 13]:
        text = b"{% if yes %}" * depth + b"x" + b"{% endif %}" * depth
        fix = fixture(directory, f"parse-depth-{depth}", {"page": text}, [("index", "page", b'{"yes":true}', 100)])
        if depth == 12:
            success(app, fix, {"index": ("x", 13)})
        else:
            failure(app, fix, "template nesting exceeds 12")
        templates = {
            f"t{n}": ("{% include t" + str(n + 1) + " %}").encode() if n < depth - 1 else b"x" for n in range(depth)
        }
        fix = fixture(directory, f"include-depth-{depth}", templates, [("index", "t0", b"{}", 100)])
        if depth == 12:
            success(app, fix, {"index": ("x", 12)})
        else:
            failure(app, fix, "include depth exceeds 12")
    for child_depth in [11, 12]:
        templates = {
            "page": b"{% if yes %}" * 12 + b"{% include child %}" + b"{% endif %}" * 12,
            "child": b"{% if yes %}" * child_depth + b"x" + b"{% endif %}" * child_depth,
        }
        fix = fixture(directory, f"render-depth-{child_depth}", templates, [("index", "page", b'{"yes":true}', 100)])
        if child_depth == 11:
            success(app, fix, {"index": ("x", 25)})
        else:
            failure(app, fix, "render recursion exceeds 24")
    for count in [4096, 4097]:
        fix = fixture(
            directory, f"syntax-nodes-{count}", {"page": b"{{x}}" * count}, [("index", "page", b'{"x":""}', 10000)]
        )
        if count == 4096:
            success(app, fix, {"index": ("", 4096)})
        else:
            failure(app, fix, "combined syntax nodes exceed 4096")
    fix = fixture(
        directory,
        "combined-syntax-nodes",
        {"page": b"{{x}}" * 4096, "other": b"x"},
        [("index", "page", b'{"x":""}', 10000)],
    )
    failure(app, fix, "other: combined syntax nodes exceed 4096")
    fix = fixture(
        directory,
        "large-tree-repeated-includes",
        {
            "page": b"{% for x in outer %}{% for y in inner %}{% include blank %}{% endfor %}{% endfor %}",
            "blank": b"",
            "unused": b"{{x}}" * 4093,
        },
        [("index", "page", json.dumps({"outer": [0] * 16, "inner": [0] * 256}).encode(), 10000)],
    )
    success(app, fix, {"index": ("", 8225)})
    for count in [256, 257]:
        fix = fixture(
            directory,
            f"loop-items-{count}",
            {"page": b"{% for x in items %}{% endfor %}"},
            [("index", "page", json.dumps({"items": [0] * count}).encode(), 10000)],
        )
        if count == 256:
            success(app, fix, {"index": ("", 257)})
        else:
            failure(app, fix, "loop exceeds 256 items")
    template = b"{% for x in items %}" + b"{{x}}," * 19 + b"{% endfor %}" + b"{{tail}}," * 7 + b"{{tail}}"
    data = json.dumps({"items": [0] * 256, "tail": ""}).encode()
    expected = "0," * 19 * 256 + "," * 7
    fix = fixture(
        directory, "all-jobs-full-budget", {"page": template}, [(f"j{n}", "page", data, 10000) for n in range(32)]
    )
    success(app, fix, {f"j{n}": (expected, 10000) for n in range(32)})
    fix = fixture(directory, "full-budget-short", {"page": template}, [("index", "page", data, 9999)])
    failure(app, fix, "render step budget exhausted")
    chunk = "😀" * 16384
    root = b"{% for x in items %}{% include chunk %}{% endfor %}"
    for count in [16, 17]:
        fix = fixture(
            directory,
            f"output-bytes-{count}",
            {"page": root, "chunk": chunk.encode()},
            [("index", "page", json.dumps({"items": [0] * count}).encode(), 10000)],
        )
        if count == 16:
            success(app, fix, {"index": (chunk * count, 1 + count * 3)})
        else:
            failure(app, fix, "rendered output exceeds 1 MiB")
    for count in [15, 16]:
        fix = fixture(
            directory,
            f"export-bytes-{count}",
            {"page": root, "chunk": chunk.encode()},
            [(f"j{n}", "page", json.dumps({"items": [0] * 16}).encode(), 10000) for n in range(count)],
        )
        if count == 15:
            success(app, fix, {f"j{n}": (chunk * 16, 49) for n in range(count)})
        else:
            failure(app, fix, "exports exceed 16 MiB")
    return {
        "templates": 32,
        "jobs": 32,
        "template_bytes": 65536,
        "combined_template_bytes": 1048576,
        "data_bytes": 1048576,
        "combined_input_bytes": 4194304,
        "config_and_manifest_bytes": 65536,
        "identifier_characters": 64,
        "expression_characters": 256,
        "parse_depth": 12,
        "include_depth": 12,
        "render_depth": 24,
        "combined_syntax_nodes": 4096,
        "loop_items": 256,
        "steps_per_job": 10000,
        "rendered_bytes_per_job": 1048576,
        "export_bytes": 16777216,
    }


def paused(app: Application, fix: Fixture) -> subprocess.Popen:
    process = subprocess.Popen(
        app.command,
        cwd=fix.work,
        env=app.environment(fix.settings(TEMPLATE_PAUSE="ready", TEMPLATE_CONTINUE=str(fix.work / "continue"))),
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
        "source-0.txt",
        "source-1.txt",
        "project.json",
        "report.json",
        "index.html",
        "data-0.json",
        "manifest.json",
        "ready",
        "published",
    ]
    for point in points:
        fix = fixture(directory, "fault-" + point, *sample())
        reference = success(app, fix, mode="preview")
        result = app.run(fix.work, fix.settings(TEMPLATE_FAIL=point))
        assert result.returncode == 2 and "injected failure: " + point in result.stderr and not result.stdout
        assert not list(fix.work.glob(".template-*"))
        if point == "published":
            outputs(fix, reference)
        else:
            assert not fix.output.exists()
            success(app, fix)
    for name in ["input-0.txt", "input-1.txt", "input-data-0.json", "project.json", "config", "destination"]:
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
            assert not list(fix.work.glob(".template-*"))
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
    abandoned = list(fix.work.glob(".template-*"))
    assert len(abandoned) == 1
    old = {path.name: path.read_bytes() for path in abandoned[0].iterdir()}
    result = app.run(fix.work, fix.settings())
    assert result.returncode == 0 and not result.stderr
    outputs(fix, reference)
    assert {path.name: path.read_bytes() for path in abandoned[0].iterdir()} == old
    return len(points) + 7


def paths(app: Application, directory: Path) -> int:
    names = ["input-0.txt", "input-1.txt", "input-data-0.json", "project.json", "template-job.json"]
    for name in ["file", "directory", "symlink", "dangling", *names]:
        fix = fixture(directory, "destination-" + name, *sample())
        if name == "file":
            fix.output.write_bytes(b"preserve")
        elif name == "directory":
            fix.output.mkdir()
            (fix.output / "keep").write_bytes(b"preserve")
        elif name in ["symlink", "dangling"]:
            fix.output.symlink_to(fix.work / ("input-0.txt" if name == "symlink" else "missing"))
        else:
            fix.config["output"] = name
            fix.save()
        failure(app, fix, "output directory already exists")
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
    fix = fixture(directory, "nested-manifest", *sample())
    nested = fix.work / "nested"
    nested.mkdir()
    old = fix.manifest
    value = json.loads(old.read_bytes())
    for row in value["templates"]:
        row["source"] = "../" + row["source"]
    for row in value["jobs"]:
        row["data"] = "../" + row["data"]
    old.unlink()
    fix.config["project"] = "nested/project.json"
    fix.manifest.write_text(json.dumps(value))
    fix.save()
    success(app, fix)
    return 16


def check(app: Application, directory: Path) -> dict:
    result = render_cases(app, directory / "render")
    result.update(include_graphs(app, directory / "graphs"))
    print(app.engine + " template renderer: independent trees, scopes and include graphs passed", flush=True)
    result["located_errors"] = located_errors(app, directory / "locations")
    result["invalid_inputs"] = invalid_inputs(app, directory / "invalid")
    result["limits"] = limits(app, directory / "limits")
    result["publication_cases"] = publication(app, directory / "publication")
    result["path_cases"] = paths(app, directory / "paths")
    print(app.engine + " template renderer: locations, bounds, publication and path checks passed", flush=True)
    return result
