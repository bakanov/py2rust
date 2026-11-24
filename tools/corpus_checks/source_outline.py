"""Independent CPython-AST and HTML checks for complete source-browser projects."""

# ruff: noqa: PLR1711 - explicit repository returns
import ast
import hashlib
import json
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path

from .common import Application


@dataclass
class Fixture:
    directory: Path
    config: Path
    output: Path
    sources: dict[str, bytes]
    packages: dict[str, bool]


def fixture(directory: Path, name: str, sources: dict[str, bytes] | None = None) -> Fixture:
    work = directory / name
    work.mkdir(parents=True)
    if sources is None:
        sources = {
            "sample": b'"Package documentation."\nfrom .model import Client\n',
            "sample.model": '''"""Model <script>alert('not HTML')</script>.

    Second paragraph.
"""
from .helpers import decorate as wrap
from . import helpers
import json
@wrap("<b>é</b>")
class Client[T]:
    """A client.
        Indented documentation.
    """
    @wrap(
        "async")
    async def fetch(self, value: T) -> T:
        """Fetch a value.
        \tTab-indented documentation.
        """
        def nested():
            "Nested function."
            return value
        if value:
            from .helpers import utility
        return value
if True:
    def conditional(): pass
elif False:
    class Alternative: pass
else:
    pass
try:
    import os.path
except* ValueError:
    from external import unavailable
finally:
    pass
match []:
    case [item]:
        def matched(): pass
type Pair[T] = tuple[T, T]
'''.encode(),
            "sample.helpers": """"Helpers."
def decorate(value):
    "Return a decorator."
    def apply(target): return target
    return apply
def utility():
    return "never executed"
def K():
    "Unicode normalized name."
    return 1
""".encode(),
            "sample.unexecuted": b'"No imports are executed."\nfrom pathlib import Path\nPath("EXECUTED").write_text("bad")\nraise RuntimeError("must not run")\n',
            "index": b'"Index module does not overwrite the project index."\nfrom sample.model import Client as C\nfrom sample import helpers\nfrom ...missing import value\n',
        }
    entries = []
    packages = {}
    for index, (module, data) in enumerate(sources.items()):
        filename = f"input-{index}.py"
        (work / filename).write_bytes(data)
        packages[module] = module == "sample"
        entries.append({"name": module, "source": filename, "package": packages[module]})
    config = work / "project.json"
    config.write_text(json.dumps({"version": 1, "modules": entries, "output": "site"}))
    return Fixture(work, config, work / "site", sources, packages)


def oracle(source: bytes, name: str) -> dict:
    text = source.decode("utf-8-sig").replace("\r\n", "\n").replace("\r", "\n")
    root = ast.parse(text, feature_version=(3, 12))
    definitions = []
    imports = []
    statements = 0

    def visit(node: ast.AST, scope: str) -> None:
        nonlocal statements
        if isinstance(node, ast.stmt):
            statements += 1
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.TypeAlias)):
            alias = isinstance(node, ast.TypeAlias)
            symbol = node.name.id if alias else node.name
            qualified = scope + "." + symbol
            definitions.append(
                {
                    "kind": type(node).__name__,
                    "name": symbol,
                    "qualified": qualified,
                    "line": node.lineno,
                    "end_line": node.end_lineno,
                    "docstring": "" if alias else ast.get_docstring(node) or "",
                    "decorators": (
                        [] if alias else [ast.get_source_segment(text, value) for value in node.decorator_list]
                    ),
                }
            )
            if not alias:
                scope = qualified + (".<locals>" if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) else "")
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            for value in node.names:
                imports.append(
                    {
                        "kind": type(node).__name__,
                        "scope": scope,
                        "line": node.lineno,
                        "module": getattr(node, "module", "") or "",
                        "level": getattr(node, "level", 0),
                        "name": value.name,
                        "alias": value.asname or "",
                    }
                )
        for child in ast.iter_child_nodes(node):
            visit(child, scope)
        return

    visit(root, name)
    return {
        "definitions": definitions,
        "imports": imports,
        "docstring": ast.get_docstring(root) or "",
        "statements": statements,
    }


class Links(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[str] = []
        self.identifiers: set[str] = set()
        self.scripts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if tag == "a":
            self.links.append(values["href"])
        if "id" in values:
            assert values["id"] not in self.identifiers
            self.identifiers.add(values["id"])
        if tag == "script":
            self.scripts.append(tag)
        return


def verify_bundle(output: Path, sources: dict[str, bytes]) -> tuple[dict, dict[str, bytes]]:
    files = {path.name: path.read_bytes() for path in output.iterdir()}
    report = json.loads(files["report.json"])
    manifest = json.loads(files["manifest.json"])
    assert manifest["version"] == 1 and set(manifest["files"]) == set(files) - {"manifest.json"}
    for name, metadata in manifest["files"].items():
        assert metadata == {"bytes": len(files[name]), "sha256": hashlib.sha256(files[name]).hexdigest()}
    assert [module["name"] for module in report["modules"]] == list(sources)
    for module in report["modules"]:
        name = module["name"]
        expected = oracle(sources[name], name)
        assert module["docstring"] == expected["docstring"]
        assert module["statements"] == expected["statements"]
        actual = []
        for value in module["definitions"]:
            row = {key: item for key, item in value.items() if key != "node"}
            row["decorators"] = [item["text"] for item in row["decorators"]]
            actual.append(row)
        assert actual == expected["definitions"], (name, actual, expected["definitions"])
        assert [
            {key: value for key, value in row.items() if key not in {"href", "target"}} for row in module["imports"]
        ] == expected["imports"]
        assert files["source-" + name + ".py"] == sources[name]
    pages = {}
    for name, data in files.items():
        if name.endswith(".html"):
            parser = Links()
            parser.feed(data.decode())
            assert not parser.scripts
            pages[name] = parser
    for name, page in pages.items():
        for href in page.links:
            target, _, anchor = href.partition("#")
            target = target or name
            assert target in pages, (name, href)
            assert not anchor or anchor in pages[target].identifiers, (name, href)
    return report, files


def run(app: Application, case: Fixture) -> tuple[dict, dict[str, bytes]]:
    result = app.run(case.directory, {"OUTLINE_CONFIG": str(case.config)}, timeout=60)
    assert result.returncode == 0 and not result.stderr, result
    report, files = verify_bundle(case.output, case.sources)
    assert json.loads(result.stdout) == report
    assert not (case.directory / "EXECUTED").exists()
    assert not list(case.directory.glob(".outline-*"))
    return report, files


def check(app: Application, directory: Path) -> dict:
    case = fixture(directory, "project")
    report, files = run(app, case)
    targets = {row["name"]: row["target"] for module in report["modules"] for row in module["imports"]}
    assert targets["Client"] == "sample.model.Client"
    assert targets["helpers"] == "sample.helpers" and targets["utility"] == "sample.helpers.utility"
    assert targets["json"] == targets["unavailable"] == targets["value"] == ""
    assert b"&lt;script&gt;" in files["module-sample.model.html"]
    assert b"Python project outline" in files["index.html"]
    # The bundle itself is a complete, portable project input.
    rebuilt = Fixture(case.output, case.output / "project.json", case.output / "rebuilt", case.sources, case.packages)
    second, second_files = run(app, rebuilt)
    assert second == report and second_files == files
    normalized = fixture(
        directory,
        "line-endings",
        {"bom": b'\xef\xbb\xbf"BOM"\r\ndef f():\r\n    pass\r\n', "old_mac": b'"CR"\rdef g():\r    pass\r'},
    )
    run(app, normalized)
    application = Path(__file__).resolve().parents[2] / "examples/corpus/077_source_outline"
    own_sources = {path.stem: path.read_bytes() for path in sorted(application.glob("*.py"))}
    own = fixture(directory, "own-project", own_sources)
    own_report, _ = run(app, own)
    assert all(module["definitions"] for module in own_report["modules"])
    duplicates = fixture(
        directory, "ambiguous", {"a": b"def f(): pass\ndef f(): pass\n", "b": b"from a import f\nimport a.f\n"}
    )
    ambiguous, _ = run(app, duplicates)
    assert ambiguous["modules"][1]["imports"][0]["target"] == "a"
    assert ambiguous["modules"][1]["imports"][0]["href"] == "module-a.html"
    assert ambiguous["modules"][1]["imports"][1]["target"] == ""
    invalid = []
    base = json.loads(case.config.read_text())
    for changes in [
        {"version": 2},
        {"version": True},
        {"modules": []},
        {"modules": base["modules"] * 7},
        {"unknown": 0},
        {"output": ""},
    ]:
        invalid.append(dict(base, **changes))
    for entry in [
        {"name": "bad/name", "source": "input-0.py"},
        {"name": "", "source": "input-0.py"},
        {"name": "m", "source": "missing.py"},
        {"name": "m", "source": "input-0.txt"},
        {"name": "m", "source": "input-0.py", "package": "yes"},
        {"name": "m", "source": "input-0.py", "extra": 1},
    ]:
        invalid.append(dict(base, modules=[entry]))
    invalid.append(dict(base, modules=[base["modules"][0], base["modules"][0]]))
    same_path = dict(base["modules"][0], name="another")
    invalid.append(dict(base, modules=[base["modules"][0], same_path]))
    for index, config in enumerate(invalid):
        bad = fixture(directory, "invalid-" + str(index))
        bad.config.write_text(json.dumps(config))
        result = app.run(bad.directory, {"OUTLINE_CONFIG": str(bad.config)})
        assert result.returncode == 2 and not result.stdout and not bad.output.exists(), result
        assert not list(bad.directory.glob(".outline-*"))
    bad_sources = [
        b"def invalid(: pass",
        b"\xff",
        b"pass\0",
        b"#" + b"x" * 131072,
        b"\n" * 4096,
        b'x="\\ud800"',
        b"def f(x,x): pass",
        b"type X[T = int] = T",
    ]
    for index, source in enumerate(bad_sources):
        bad = fixture(directory, "syntax-" + str(index), {"bad": source})
        result = app.run(bad.directory, {"OUTLINE_CONFIG": str(bad.config)})
        assert result.returncode == 2 and not result.stdout and not bad.output.exists(), result
        assert not list(bad.directory.glob(".outline-*"))
    for kind in ["file", "directory", "symlink", "dangling"]:
        bad = fixture(directory, "existing-" + kind)
        if kind == "file":
            bad.output.write_bytes(b"preserve")
        elif kind == "directory":
            bad.output.mkdir()
            (bad.output / "keep").write_bytes(b"preserve")
        else:
            bad.output.symlink_to(bad.config if kind == "symlink" else bad.directory / "absent")
        before = bad.output.lstat()
        result = app.run(bad.directory, {"OUTLINE_CONFIG": str(bad.config)})
        assert result.returncode == 2 and not result.stdout
        after = bad.output.lstat()
        for field in ["st_dev", "st_ino", "st_mode", "st_size", "st_mtime_ns", "st_ctime_ns"]:
            assert getattr(after, field) == getattr(before, field)
    for kind in ["directory", "symlink"]:
        bad = fixture(directory, "input-" + kind)
        path = bad.directory / "input-0.py"
        path.unlink()
        path.mkdir() if kind == "directory" else path.symlink_to(bad.directory / "input-1.py")
        result = app.run(bad.directory, {"OUTLINE_CONFIG": str(bad.config)})
        assert result.returncode == 2 and not bad.output.exists()
    return {
        "modules": len(report["modules"]),
        "definitions": sum(len(row["definitions"]) for row in report["modules"]),
        "independent_cpython_ast": True,
        "actual_application_sources_parsed": len(own_sources),
        "all_html_links_resolve": True,
        "source_never_executed": True,
        "portable_rebuild_byte_identical": True,
        "unicode_decorators_docstrings_and_nested_scopes": True,
        "invalid_configurations": len(invalid),
        "invalid_sources": len(bad_sources),
        "existing_outputs_preserved": 4,
        "nonregular_sources_rejected": 2,
        "bundle_sha256": hashlib.sha256(b"".join(files[name] for name in sorted(files))).hexdigest(),
    }
