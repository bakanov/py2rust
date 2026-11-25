"""Independent token fixtures and structural HTML checks for complete source exporters."""

# ruff: noqa: PLR1711 - explicit repository returns
import copy
import hashlib
import json
import os
import random
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path

from .common import Application

KINDS = {"space", "identifier", "keyword", "number", "string", "comment", "punctuation", "error"}


@dataclass
class Fixture:
    directory: Path
    sources: dict[str, bytes]
    expected: dict[str, list[tuple[str, str]]]
    theme: str
    config_name: str = "job.json"
    output_name: str = "output"

    @property
    def config(self) -> Path:
        return self.directory / self.config_name

    @property
    def output(self) -> Path:
        return self.directory / self.output_name


def examples() -> dict[str, list[tuple[str, str]]]:
    good = [
        ("comment", "# <script>alert('x')</script> 😀"),
        ("space", "\n"),
        ("identifier", "server"),
        ("punctuation", "."),
        ("identifier", "enabled"),
        ("space", " "),
        ("punctuation", "="),
        ("space", " "),
        ("keyword", "true"),
        ("space", "\n"),
        ("identifier", "title"),
        ("space", " "),
        ("punctuation", "="),
        ("space", " "),
        ("string", '"héllo \\"<b>world</b>\\" 😀"'),
        ("space", "\n"),
        ("string", "'''first\n# not a comment\n/* neither */\nlast'''"),
        ("space", "\n"),
        ("comment", "/* outer\n /* inner */\n end */"),
        ("space", "\n"),
        ("number", "1.25e-3"),
        ("space", " "),
        ("punctuation", "-"),
        ("number", "2"),
        ("space", "\n"),
        ("identifier", "falsehood"),
        ("space", " "),
        ("keyword", "false"),
        ("space", " "),
        ("keyword", "null"),
        ("space", "\t"),
        ("identifier", "TRUE"),
        ("space", "\n"),
    ]
    triple = '"""'
    fragments = [
        ("identifier", "some_key9"),
        ("keyword", "true"),
        ("keyword", "null"),
        ("number", "0123"),
        ("number", "42.0E+12"),
        ("string", '""'),
        ("string", "''"),
        ("string", '"<&amp; &lt;>é😀"'),
        ("string", triple * 2),
        ("string", triple + "x\\" + triple + "y" + triple),
        ("string", "'escaped \\' and \\\\ slash'"),
        ("comment", "/**/"),
        ("comment", "/* a /* b /* c */ b */ a */"),
        ("punctuation", "{"),
        ("punctuation", "}"),
        ("punctuation", "["),
        ("punctuation", "]"),
        ("punctuation", ":"),
        ("punctuation", ","),
    ]
    rng = random.Random(80080)
    generated = []
    for index in range(240):
        if index:
            generated.append(("space", "\n" if index % 7 == 0 else " "))
        generated.append(rng.choice(fragments))
    return {
        'Settings <img src=x onerror="bad"> & 世界': good,
        "Generated": generated,
        "Broken": [
            ("error", '"unfinished\\'),
            ("space", "\n"),
            ("identifier", "next"),
            ("punctuation", "="),
            ("keyword", "true"),
            ("space", "\n"),
            ("error", "1.2.3"),
            ("space", " "),
            ("error", "@"),
            ("space", "\n"),
            ("error", "/* open /* inner */"),
        ],
        "Triple": [("error", triple + "é\n<script>&")],
        "Empty": [],
    }


def fixture(directory: Path, theme: str = "light", expected: dict | None = None) -> Fixture:
    directory.mkdir(parents=True)
    values = examples() if expected is None else expected
    sources = {}
    entries = []
    for index, (label, tokens) in enumerate(values.items()):
        text = "".join(value for _kind, value in tokens)
        data = text.replace("\n", "\r\n").encode() if index == 0 else text.encode()
        sources[label] = data
        filename = "input-" + str(index) + ".cfg"
        (directory / filename).write_bytes(data)
        entries.append({"label": label, "source": filename})
    config = {"version": 1, "files": entries, "output": "output", "theme": theme}
    (directory / "job.json").write_text(json.dumps(config))
    return Fixture(directory, sources, values, theme)


def coordinates(text: str, offset: int) -> tuple[int, int]:
    return text.count("\n", 0, offset) + 1, offset - text.rfind("\n", 0, offset)


class Page(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.code = False
        self.source = ""
        self.spans = []
        self.links = []
        self.identifiers = set()
        self.theme = ""

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        assert tag not in {"script", "iframe", "object", "embed", "img", "svg", "math", "base"}, tag
        assert not any(name.startswith("on") or name == "style" for name in values), values
        if "id" in values:
            assert values["id"] not in self.identifiers
            self.identifiers.add(values["id"])
        if tag == "body":
            self.theme = values["class"]
        if tag in ["a", "link"]:
            self.links.append(values["href"])
            if values["href"].endswith(".source"):
                assert "download" in values
        if self.code:
            assert tag == "span" and values["class"] in KINDS
            self.spans.append((values["class"], int(values["data-start"]), int(values["data-end"]), values["id"]))
        if tag == "code":
            assert values == {"id": "source"} and not self.code
            self.code = True
        return

    def handle_endtag(self, tag: str) -> None:
        if tag == "code":
            self.code = False
        return

    def handle_data(self, data: str) -> None:
        if self.code:
            self.source += data
        return


def verify(case: Fixture) -> tuple[dict, dict[str, bytes]]:
    files = {path.name: path.read_bytes() for path in case.output.iterdir()}
    report = json.loads(files["report.json"])
    manifest = json.loads(files["manifest.json"])
    assert report["version"] == manifest["version"] == 1 and report["theme"] == case.theme
    assert set(manifest["files"]) == set(files) - {"manifest.json"}
    for name, row in manifest["files"].items():
        assert row == {"bytes": len(files[name]), "sha256": hashlib.sha256(files[name]).hexdigest()}
    assert [row["label"] for row in report["files"]] == list(case.sources)
    total = 0
    pages = {}
    for name, data in files.items():
        if name.endswith(".html"):
            page = Page()
            page.feed(data.decode())
            assert not page.code and page.theme == case.theme
            pages[name] = page
    for index, row in enumerate(report["files"]):
        label = row["label"]
        assert row["page"] == f"file-{index}.html" and row["source"] == f"file-{index}.source"
        assert files[row["source"]] == case.sources[label]
        text = case.sources[label].decode().replace("\r\n", "\n").replace("\r", "\n")
        assert row["lines"] == text.count("\n") + 1
        assert [(token["kind"], token["text"]) for token in row["tokens"]] == case.expected[label], label
        position = 0
        for token in row["tokens"]:
            end = position + len(token["text"])
            assert token["start"] == position and token["end"] == end
            assert text[position:end] == token["text"]
            assert (token["line"], token["column"]) == coordinates(text, position)
            assert (token["end_line"], token["end_column"]) == coordinates(text, end)
            position = end
        assert position == len(text)
        errors = [i for i, token in enumerate(row["tokens"]) if token["kind"] == "error"]
        assert [item["token"] for item in row["diagnostics"]] == errors
        for diagnostic in row["diagnostics"]:
            token = row["tokens"][diagnostic["token"]]
            assert (diagnostic["line"], diagnostic["column"]) == (token["line"], token["column"])
        page = pages[row["page"]]
        assert page.source == text
        assert page.spans == [
            (token["kind"], token["start"], token["end"], f"t{i}") for i, token in enumerate(row["tokens"])
        ]
        total += len(errors)
    assert report["diagnostics"] == total
    for name, page in pages.items():
        for href in page.links:
            target, _, anchor = href.partition("#")
            target = target or name
            assert target in files, (name, href)
            assert not anchor or target in pages and anchor in pages[target].identifiers
    assert b".dark{" in files["style.css"] and b".error{" in files["style.css"]
    return report, files


def run(app: Application, case: Fixture) -> tuple[dict, dict[str, bytes]]:
    originals = [(path, path.read_bytes()) for path in case.directory.iterdir() if path.is_file()]
    result = app.run(case.directory, {"HIGHLIGHT_CONFIG": str(case.config)}, timeout=60)
    expected_errors = sum(kind == "error" for tokens in case.expected.values() for kind, _text in tokens)
    assert result.returncode == (1 if expected_errors else 0) and not result.stderr, result
    report, files = verify(case)
    assert json.loads(result.stdout) == report
    assert all(path.read_bytes() == data for path, data in originals)
    assert not list(case.directory.glob(".highlight-*"))
    return report, files


def snapshot(directory: Path) -> dict:
    result = {}
    for path in directory.rglob("*"):
        info = path.lstat()
        data = os.readlink(path) if path.is_symlink() else path.read_bytes() if path.is_file() else None
        result[str(path.relative_to(directory))] = (info.st_mode, info.st_mtime_ns, data)
    return result


def rejection_cases(app: Application, directory: Path) -> int:
    case = fixture(directory, expected={"Basic": [("identifier", "abc")]})
    base = json.loads(case.config.read_text())
    invalid = [
        dict(base, **change)
        for change in [
            {"version": True},
            {"version": 2},
            {"extra": 1},
            {"theme": "auto"},
            {"theme": False},
            {"files": []},
            {"files": base["files"] * 17},
            {"files": base["files"] * 2},
            {"output": ""},
            {"output": 1},
            {"output": "missing/folder"},
            {"output": "job.json"},
            {"output": "input-0.cfg"},
        ]
    ]
    for key in base:
        changed = copy.deepcopy(base)
        del changed[key]
        invalid.append(changed)
    for changes in [
        {"label": ""},
        {"label": "x" * 81},
        {"label": "two\nlines"},
        {"label": "a\r"},
        {"label": "\0"},
        {"label": 1},
        {"source": ""},
        {"source": 1},
        {"source": "absent"},
        {"extra": True},
    ]:
        invalid.append(dict(base, files=[dict(base["files"][0], **changes)]))
    (directory / "folder").mkdir()
    (directory / "folder/keep").write_bytes(b"preserve")
    (directory / "link").symlink_to(directory / "input-0.cfg")
    (directory / "dangling").symlink_to(directory / "absent")
    os.link(directory / "input-0.cfg", directory / "hardlink")
    for name in ["folder", "link", "dangling"]:
        invalid.append(dict(base, output=name))
        invalid.append(dict(base, files=[{"label": "Bad", "source": name}]))
    invalid.append(dict(base, files=[*base["files"], {"label": "Other", "source": "hardlink"}]))
    for value in invalid:
        case.config.write_text(json.dumps(value))
        before = snapshot(directory)
        result = app.run(directory, {"HIGHLIGHT_CONFIG": str(case.config)})
        assert result.returncode == 2 and not result.stdout and result.stderr, result
        assert snapshot(directory) == before
    # Remove the alias so later cases exercise content limits, not link policy.
    (directory / "hardlink").unlink()
    invalid_sources = [b"\xff", b"a\0", b"#" + b"x" * 65536, b"{" * 8193, b"/*" * 9 + b"*/" * 9]
    for source in invalid_sources:
        (directory / "input-0.cfg").write_bytes(source)
        case.config.write_text(json.dumps(base))
        before = snapshot(directory)
        result = app.run(directory, {"HIGHLIGHT_CONFIG": str(case.config)}, timeout=60)
        assert result.returncode == 2 and not result.stdout and result.stderr, result
        assert snapshot(directory) == before
    for kind in ["bytes", "tokens"]:
        value = copy.deepcopy(base)
        entries = []
        for index in range(5):
            data = b"#" * 65536 if kind == "bytes" else b"{" * 8192
            data = data if index < 4 else b"{"
            name = f"{kind}-{index}.cfg"
            (directory / name).write_bytes(data)
            entries.append({"label": str(index), "source": name})
        value["files"] = entries
        case.config.write_text(json.dumps(value))
        before = snapshot(directory)
        result = app.run(directory, {"HIGHLIGHT_CONFIG": str(case.config)}, timeout=120)
        assert result.returncode == 2 and not result.stdout and result.stderr, result
        assert snapshot(directory) == before
    return len(invalid) + len(invalid_sources) + 2


def check(app: Application, directory: Path) -> dict:
    bundles = []
    for theme in ["light", "dark"]:
        case = fixture(directory / theme, theme)
        report, files = run(app, case)
        messages = [row["message"] for item in report["files"] for row in item["diagnostics"]]
        assert messages == [
            "unterminated string",
            "invalid number",
            "unexpected character",
            "unterminated block comment",
            "unterminated string",
        ]
        bundles.append(hashlib.sha256(b"".join(files[name] for name in sorted(files))).hexdigest())
        rebuilt = Fixture(case.output, case.sources, case.expected, case.theme, "highlight-job.json", "rebuilt")
        replayed, second_files = run(app, rebuilt)
        assert replayed == report and second_files == files
    valid = {
        "Nested": [("comment", "/*" * 8 + "*/" * 8)],
        "CR": [("identifier", "name"), ("space", "\n"), ("string", '"é😀"')],
    }
    case = fixture(directory / "valid", expected=valid)
    case.sources["CR"] = case.sources["CR"].replace(b"\n", b"\r")
    (case.directory / "input-1.cfg").write_bytes(case.sources["CR"])
    run(app, case)
    invalid = rejection_cases(app, directory / "invalid")
    return {
        "independent_token_fixtures": True,
        "generated_fragments": 240,
        "themes": 2,
        "source_coordinates_and_complete_token_coverage": True,
        "html_reconstructs_exact_normalized_source": True,
        "all_links_and_diagnostics_resolve": True,
        "raw_source_bytes_preserved": True,
        "nested_comments_escaped_quotes_and_multiline_strings": True,
        "unfinished_tokens_render_safely": True,
        "byte_identical_replay": True,
        "invalid_cases_rejected_without_writes": invalid,
        "bundle_sha256": bundles,
    }
