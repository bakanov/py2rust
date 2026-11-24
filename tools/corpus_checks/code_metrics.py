"""Independent AST, HTML, snapshot, discovery and publication checks for the code-metrics browser."""

from __future__ import annotations

import copy
import hashlib
import json
import os
import select
import subprocess
import time
from pathlib import Path

import html5lib

from .common import Application
from .metrics_fixture import FILES, archive, expected, normalize


def fixture(root: Path, files: dict[str, bytes] | None = None, prefix: str = "") -> dict:
    root.mkdir(parents=True, exist_ok=True)
    (root / "source").mkdir()
    for name, data in (FILES if files is None else files).items():
        path = root / "source" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    config = {
        "version": 1,
        "root": "source",
        "output": "inspection",
        "package": prefix,
        "exclude": ["vendor", "__pycache__"],
        "thresholds": {"lines": 6, "statements": 5, "depth": 1},
    }
    save(root, config)
    return config


def save(root: Path, config: dict) -> None:
    (root / "metrics-job.json").write_text(json.dumps(config, ensure_ascii=False) + "\n")
    return  # noqa: PLR1711


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def check_html(output: Path, report: dict, files: dict[str, bytes]) -> None:
    trees, anchors = {}, {}
    for page in ["index.html", *(module["page"] for module in report["modules"])]:
        raw = (output / page).read_bytes()
        tree = html5lib.parse(raw, treebuilder="etree", namespaceHTMLElements=False)
        trees[page] = tree
        anchors[page] = set()
        for element in tree.iter():
            assert element.tag not in {"script", "img", "iframe", "object"}, (page, element.tag)
            assert not any(name.lower().startswith("on") for name in element.attrib)
            if "id" in element.attrib:
                assert element.attrib["id"] not in anchors[page]
                anchors[page].add(element.attrib["id"])
    for page, tree in trees.items():
        for element in tree.iter("a"):
            target, separator, anchor = element.attrib["href"].partition("#")
            target = target or page
            assert target in trees, (page, target)
            if separator:
                assert anchor in anchors[target], (page, target, anchor)
    for module in report["modules"]:
        tree = trees[module["page"]]
        spans = [s for s in tree.iter("span") if s.attrib.get("class") == "line"]
        lines = normalize(files[module["path"]]).split("\n")[: module["lines"]]
        assert len(spans) == len(lines)
        for index, (span, text) in enumerate(zip(spans, lines, strict=True), 1):
            assert span.attrib["id"] == f"L{index}"
            number = span.find("a")
            assert number.text == str(index) and (number.tail or "") == text
        table_rows = next(tree.iter("tbody")).findall("tr")
        assert len(table_rows) == len(module["definitions"])
        for row, definition in zip(table_rows, module["definitions"], strict=True):
            cells = ["".join(cell.itertext()) for cell in row.findall("td")]
            metrics = definition["metrics"]
            assert cells == [
                definition["qualified"],
                str(definition["lines"]),
                str(metrics["statements"]),
                str(metrics["control_statements"]),
                str(metrics["max_depth"]),
                ", ".join(definition["flags"]),
            ]
            assert (row.attrib.get("class") == "flag") == bool(definition["flags"])
    return  # noqa: PLR1711


def inspect_bundle(output: Path, config: dict, files: dict[str, bytes]) -> dict:
    report = json.loads((output / "report.json").read_bytes())
    wanted = expected(files, config)
    assert report == wanted, (report, wanted)
    assert json.loads((output / "sources.json").read_bytes()) == archive(files, config)
    manifest = json.loads((output / "manifest.json").read_bytes())
    names = {"index.html", "report.json", "sources.json", *(m["page"] for m in report["modules"])}
    assert set(manifest) == names and {p.name for p in output.iterdir()} == names | {"manifest.json"}
    for name, info in manifest.items():
        raw = (output / name).read_bytes()
        assert info == {"bytes": len(raw), "sha256": digest(raw)}
    check_html(output, report, files)
    return report


def run(app: Application, root: Path, config: dict, files: dict[str, bytes] | None = None, timeout: int = 30) -> dict:
    files = FILES if files is None else files
    result = app.run(root, {}, timeout=timeout)
    assert result.returncode == 0 and not result.stderr, (result.returncode, result.stdout, result.stderr)
    report = inspect_bundle(root / config["output"], config, files)
    assert json.loads(result.stdout) == report["summary"]
    assert not (root / "EXECUTED").exists() and not (root / "source/EXECUTED").exists()
    for name, raw in files.items():
        assert (root / "source" / name).read_bytes() == raw
    return report


def semantic_cases(app: Application, root: Path) -> dict:
    config = fixture(root / "hand")
    extra = root / "hand/source"
    (extra / "vendor").mkdir()
    (extra / "vendor/bad.py").write_text("def broken(")
    (extra / ".hidden").mkdir()
    (extra / ".hidden/bad.py").write_text("invalid source !")
    (extra / "notes.txt").write_bytes(b"\xff non-Python input")
    report = run(app, root / "hand", config)
    modules = {row["path"]: row for row in report["modules"]}
    outer, inner, nested, method = modules["pkg/logic.py"]["definitions"]
    assert (outer["id"], outer["start_line"], outer["line"], outer["end_line"], outer["lines"]) == (2, 4, 5, 14, 11)
    assert (outer["metrics"]["statements"], outer["metrics"]["control_statements"], outer["metrics"]["max_depth"]) == (
        6,
        1,
        1,
    )
    assert outer["flags"] == ["lines", "statements"] and inner["metrics"]["statements"] == 1
    assert nested["metrics"]["statements"] == 1 and method["qualified"] == "pkg.logic.outer.<locals>.Nested.method"
    poll = modules["pkg/helper.py"]["definitions"][0]
    assert (
        poll["lines"],
        poll["metrics"]["statements"],
        poll["metrics"]["control_statements"],
        poll["metrics"]["max_depth"],
    ) == (6, 5, 3, 2)
    assert poll["flags"] == ["depth"]
    branches = modules["pkg/branches.py"]["definitions"][0]
    assert branches["metrics"] == {
        "statements": 7,
        "control_statements": 2,
        "max_depth": 2,
        "kinds": {"Try": 1, "Match": 1, "Return": 2, "Raise": 1, "Pass": 2},
    }
    expressions = modules["constructs.py"]["definitions"][-1]
    assert expressions["metrics"]["statements"] == 3 and expressions["metrics"]["control_statements"] == 0
    statuses = [row["status"] for row in modules["main.py"]["imports"]]
    assert statuses == [
        "external",
        "local_module",
        "missing_local",
        "namespace",
        "ambiguous",
        "local_module",
        "local_member",
        "local_member",
        "local_wildcard",
        "external",
        "outside_root",
    ]
    varied = {
        "__init__.py": b"from . import nested\n",
        "nested/__init__.py": b"from .. import api\n",
        "nested/mod.py": b"from ...outside import name\nfrom ..missing import thing\n",
        "api.py": "def K():\n    return 1\n\nif True:\n    def repeated(): pass\nelse:\n    def repeated(): pass\n".encode(),
    }
    run(app, root / "package", fixture(root / "package", varied, "demo"), varied)
    for name, limits in [
        ("zero", {"lines": 0, "statements": 0, "depth": 0}),
        ("ceiling", {"lines": 4096, "statements": 4096, "depth": 64}),
    ]:
        work = root / name
        config = fixture(work)
        config["thresholds"] = limits
        save(work, config)
        result = run(app, work, config)
        if name == "ceiling":
            assert result["summary"]["flagged_functions"] == 0
    run(app, root / "empty", fixture(root / "empty", {}), {})
    return {
        "hand_labeled_modules": len(FILES),
        "fixtures": 5,
        "precise_scope_ownership_and_spans": True,
        "threshold_boundaries": True,
        "import_categories": 8,
        "escaped_html_and_all_links_checked": True,
        "source_never_executed": True,
    }


def invalid(app: Application, root: Path) -> dict:
    base = {
        "version": 1,
        "root": "source",
        "output": "inspection",
        "package": "",
        "exclude": [],
        "thresholds": {"lines": 6, "statements": 5, "depth": 1},
    }
    variants = []
    for key, value in [
        ("version", True),
        ("version", 2),
        ("root", ""),
        ("root", "\x00"),
        ("root", "missing"),
        ("root", "/"),
        ("output", "source/report"),
        ("output", "source"),
        ("package", "a..b"),
        ("package", "class"),
        ("package", "a" * 129),
        ("exclude", ["a", "a"]),
        ("exclude", ["../x"]),
        ("exclude", ["x" * 65]),
        ("exclude", [str(i) for i in range(17)]),
        ("thresholds", {}),
    ]:
        variants.append(dict(copy.deepcopy(base), **{key: value}))
    variants += [dict(base, extra=1), {k: v for k, v in base.items() if k != "root"}]
    for key in ["lines", "statements", "depth"]:
        for value in [-1, True, 1.5, 65 if key == "depth" else 4097]:
            config = copy.deepcopy(base)
            config["thresholds"][key] = value
            variants.append(config)
    for index, config in enumerate(variants):
        work = root / str(index)
        fixture(work, {"a.py": b"pass\n"})
        save(work, config)
        result = app.run(work, {})
        assert result.returncode == 2 and result.stderr and not result.stdout, (config, result)
        assert not (work / "inspection").exists()
    malformed = [b"{", b"\xff", b'{"version":1,"version":1}', b" " * 65537]
    for index, raw in enumerate(malformed):
        work = root / f"json_{index}"
        fixture(work, {})
        (work / "metrics-job.json").write_bytes(raw)
        result = app.run(work, {})
        assert result.returncode == 2 and result.stderr and not (work / "inspection").exists()
    sources = [
        ({"broken.py": b"def broken(:\n"}, "broken.py: python syntax error"),
        ({"wrong.py": b"\xff"}, ""),
        ({"bad-name.py": b"pass\n"}, "invalid module path"),
        ({"class.py": b"pass\n"}, "python syntax error"),
        ({"__init__.py": b"pass\n"}, "root __init__"),
        ({"nul.py": b"#\0"}, "nul.py: invalid Python source bytes"),
        ({"large.py": b"#" * 131073}, "input byte limit"),
        ({"lines.py": b"\n" * 4097}, "4096 lines"),
        ({"nodes.py": b"pass;pass\n" * 2048 + b"pass\n"}, "nodes.py:"),
    ]
    for index, (files, message) in enumerate(sources):
        work = root / f"source_{index}"
        fixture(work, files)
        result = app.run(work, {})
        assert result.returncode == 2 and result.stderr and not result.stdout and message in result.stderr, result
        assert not (work / "inspection").exists()
    return {
        "invalid_configurations": len(variants),
        "malformed_documents": len(malformed),
        "invalid_sources": len(sources),
    }


def paused(app: Application, root: Path, label: str) -> subprocess.Popen:
    process = subprocess.Popen(
        app.command,
        cwd=root,
        env=app.environment({"METRICS_PAUSE": label, "METRICS_RELEASE": str(root.parent / (root.name + "-release"))}),
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
    files = {"a.py": b"def f(): return 1\n"}
    for label in ["staged", "published"]:
        for mode in ["fault", "kill"]:
            work = root / (label + "_" + mode)
            config = fixture(work, files)
            if mode == "fault":
                result = app.run(work, {"METRICS_FAULT": label})
                assert result.returncode == 2 and "injected failure" in result.stderr
                assert not list(work.glob(".metrics-*"))
            else:
                process = paused(app, work, label)
                process.kill()
                process.communicate(timeout=5)
                assert process.returncode == -9
            if label == "published":
                inspect_bundle(work / "inspection", config, files)
            else:
                assert not (work / "inspection").exists()
            if mode == "fault" and label == "staged":
                run(app, work, config, files)
    changes = ["source", "config", "added", "removed", "renamed", "symlink", "competitor", "ignored"]
    for change in changes:
        work = root / change
        config = fixture(work, files)
        (work / "source/vendor").mkdir()
        process = paused(app, work, "staged")
        try:
            source = work / "source/a.py"
            if change == "source":
                source.write_bytes(b"def f(): return 2\n")
            elif change == "config":
                (work / "metrics-job.json").write_text("{}")
            elif change == "added":
                (work / "source/b.py").write_text("pass\n")
            elif change == "removed":
                source.unlink()
            elif change == "renamed":
                source.rename(work / "source/b.py")
            elif change == "symlink":
                (work / "source/new.py").symlink_to(source)
            elif change == "competitor":
                (work / "inspection").mkdir()
                (work / "inspection/sentinel").write_bytes(b"keep")
            else:
                (work / "source/vendor/bad.py").write_text("bad syntax !")
            (work.parent / (work.name + "-release")).touch()
            stdout, stderr = process.communicate(timeout=10)
            if change == "ignored":
                assert process.returncode == 0 and not stderr
                assert json.loads(stdout) == inspect_bundle(work / "inspection", config, files)["summary"]
            else:
                assert process.returncode == 2 and stderr and not stdout
                if change == "competitor":
                    assert (work / "inspection/sentinel").read_bytes() == b"keep"
                else:
                    assert not (work / "inspection").exists()
            assert not list(work.glob(".metrics-*"))
        finally:
            if process.poll() is None:
                process.kill()
                process.communicate()
    return {"atomic_fault_or_kill_boundaries": 4, "mutations_tested": len(changes), "excluded_changes_allowed": True}


def filesystem(app: Application, root: Path) -> dict:
    cases = [
        "input-symlink",
        "input-hardlink",
        "input-fifo",
        "input-unreadable",
        "source-symlink",
        "source-hardlink",
        "source-fifo",
        "source-unreadable",
        "directory-symlink",
        "output-symlink",
        "output-file",
        "output-directory",
        "publication-permission",
    ]
    for name in cases:
        work = root / name
        fixture(work, {"a.py": b"pass\n"})
        sentinel = work / "sentinel"
        sentinel.write_bytes(b"preserve")
        target = work / ("metrics-job.json" if name.startswith("input") else "source/a.py")
        if name.startswith("output"):
            target = work / "inspection"
        elif name == "directory-symlink":
            target = work / "source/alias"
        elif name == "publication-permission":
            assert os.getuid() != 0
            work.chmod(0o500)
        if name.endswith("unreadable"):
            target.chmod(0)
        elif name.endswith("symlink"):
            target.unlink(missing_ok=True)
            target.symlink_to(
                sentinel if name != "directory-symlink" else work / "source",
                target_is_directory=name == "directory-symlink",
            )
        elif name.endswith("hardlink"):
            target.unlink()
            os.link(sentinel, target)
        elif name.endswith("fifo"):
            target.unlink()
            os.mkfifo(target)
        elif name == "output-file":
            target.write_bytes(b"keep output")
        elif name == "output-directory":
            target.mkdir()
        try:
            result = app.run(work, {}, timeout=10)
            assert result.returncode == 2 and result.stderr and not result.stdout, (name, result)
            assert sentinel.read_bytes() == b"preserve"
        finally:
            work.chmod(0o700)
            if name.endswith("unreadable"):
                target.chmod(0o600)
    return {"guarded_paths_and_permissions": len(cases)}


def limits(app: Application, root: Path) -> dict:
    files = {f"m{i:02}.py": b"pass #" + b"x" * (16384 - 7) + b"\n" for i in range(64)}
    work = root / "maximum"
    config = fixture(work, files)
    config["exclude"] = ["vendor", "__pycache__", *[f"excluded_{i}" for i in range(14)]]
    save(work, config)
    job = work / "metrics-job.json"
    job.write_bytes(job.read_bytes().ljust(65536, b" "))
    run(app, work, config, files, 120)
    statements = {f"m{i}.py": b"pass\n" * 4096 for i in range(8)}
    work = root / "statements"
    run(app, work, fixture(work, statements), statements, 120)
    for label, cases in [
        ("module-bytes", {"m.py": b"#" * 131071 + b"\n"}),
        ("directory-depth", {"/".join(["p" * 9] * 8) + "/" + "m" * 47 + ".py": b"pass\n"}),
    ]:
        work = root / label
        run(app, work, fixture(work, cases, "p" * 128 if label == "directory-depth" else ""), cases, 120)
    work = root / "entries"
    config = fixture(work, {"m.py": b"pass\n"})
    for index in range(4095):
        (work / "source" / f"note-{index}").touch()
    run(app, work, config, {"m.py": b"pass\n"}, 120)
    (work / "source/extra").touch()
    config["output"] = "overflow"
    save(work, config)
    result = app.run(work, {}, timeout=120)
    assert result.returncode == 2 and "limit" in result.stderr
    overflow = [
        dict(files, extra=b"pass\n"),
        dict(files, **{"m00.py": files["m00.py"] + b" "}),
        dict(statements, **{"extra.py": b"pass\n"}),
        {"/".join(["pkg"] * 9) + "/m.py": b"pass\n"},
    ]
    overflow[0]["extra.py"] = overflow[0].pop("extra")
    for index, cases in enumerate(overflow):
        work = root / f"overflow-{index}"
        fixture(work, cases)
        result = app.run(work, {}, timeout=120)
        assert result.returncode == 2 and result.stderr and not (work / "inspection").exists()
    work = root / "report-overflow"
    line = b"def f" + b"x" * 40 + b"(): pass\n"
    fixture(work, {f"m{i}.py": line * 2048 for i in range(8)}, "p" * 128)
    result = app.run(work, {}, timeout=120)
    assert (
        result.returncode == 2
        and "report bundle exceeds 16 MiB" in result.stderr
        and not (work / "inspection").exists()
    )
    work = root / "module-name-overflow"
    fixture(work, {"/".join(["p" * 32] * 8) + "/m.py": b"pass\n"})
    result = app.run(work, {})
    assert result.returncode == 2 and "invalid module path" in result.stderr
    return {
        "modules": 64,
        "report_bytes": 16777216,
        "package_name_characters": 128,
        "module_name_characters": 256,
        "configuration_bytes": 65536,
        "exclusions": 16,
        "module_bytes": 131072,
        "project_bytes": 1048576,
        "statements": 32768,
        "directory_depth": 8,
        "directory_entries": 4096,
        "capacity_overflows": 7,
    }


def check(app: Application, directory: Path) -> dict:
    return {
        "semantics": semantic_cases(app, directory / "semantics"),
        "invalid": invalid(app, directory / "invalid"),
        "publication": publication(app, directory / "publication"),
        "filesystem": filesystem(app, directory / "filesystem"),
        "limits": limits(app, directory / "limits"),
        "independent_ast_and_html_oracles": True,
    }
