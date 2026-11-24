"""Independent HTML goldens, generated markup trees, link audits, and publication checks for 072."""

# ruff: noqa: PLR1711 - explicit repository returns

from __future__ import annotations

import hashlib
import html
import json
import random
import re
import selectors
import subprocess
import unicodedata
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import quote, unquote

from .common import Application
from .csv_json import canonical


@dataclass
class Expected:
    body: str
    headings: list[dict]
    links: list[str]


def escaped(value: str) -> str:
    return html.escape(value, quote=True).replace("&#x27;", "&#39;")


def anchors(texts: list[str]) -> list[str]:
    used = set()
    result = []
    for text in texts:
        normalized = unicodedata.normalize("NFKC", text).casefold()
        base = re.sub(r"[^a-z0-9\u0080-\U0010ffff]+", "-", normalized).strip("-")[:64] or "section"
        candidate = base
        suffix = 2
        while candidate in used:
            candidate = f"{base}-{suffix}"
            suffix += 1
        used.add(candidate)
        result.append(candidate)
    return result


def sample() -> dict[str, bytes]:
    return {
        "index": (
            b"# Field notes\r\n\r\nA **small _readable_** site built from Python.\r\n"
            b"See the [guide](guide#setup).\r\n\r\n- Keep <HTML> as text.\r\n"
            b"- Keep `**code**` literal.\r\n\r\n## Field notes\r\n"
            b"[Jump back](#field-notes) or visit [Rust](https://www.rust-lang.org/).\r\n"
        ),
        "guide": (
            '# Setup\n\n```python\nprint("<hello> & goodbye")\n```\n\n'
            "## Setup\nDuplicate headings stay linkable: [second setup](#setup-2).\n\n"
            "## 世界 😀\nUnicode headings work. [Home](index).\n"
        ).encode(),
    }


def sample_expected() -> dict[str, Expected]:
    return {
        "index": Expected(
            '<h1 id="field-notes">Field notes</h1>\n'
            "<p>A <strong>small <em>readable</em></strong> site built from Python. "
            'See the <a href="guide.html#setup">guide</a>.</p>\n'
            "<ul>\n<li>Keep &lt;HTML&gt; as text.</li>\n<li>Keep <code>**code**</code> literal.</li>\n</ul>\n"
            '<h2 id="field-notes-2">Field notes</h2>\n'
            '<p><a href="index.html#field-notes">Jump back</a> or visit '
            '<a href="https://www.rust-lang.org/">Rust</a>.</p>\n',
            [
                {"level": 1, "text": "Field notes", "id": "field-notes"},
                {"level": 2, "text": "Field notes", "id": "field-notes-2"},
            ],
            ["guide#setup", "#field-notes", "https://www.rust-lang.org/"],
        ),
        "guide": Expected(
            '<h1 id="setup">Setup</h1>\n<pre><code class="language-python">'
            "print(&quot;&lt;hello&gt; &amp; goodbye&quot;)</code></pre>\n"
            '<h2 id="setup-2">Setup</h2>\n<p>Duplicate headings stay linkable: '
            '<a href="guide.html#setup-2">second setup</a>.</p>\n'
            '<h2 id="世界-😀">世界 😀</h2>\n<p>Unicode headings work. <a href="index.html">Home</a>.</p>\n',
            [
                {"level": 1, "text": "Setup", "id": "setup"},
                {"level": 2, "text": "Setup", "id": "setup-2"},
                {"level": 2, "text": "世界 😀", "id": "世界-😀"},
            ],
            ["#setup-2", "index"],
        ),
    }


@dataclass
class Fixture:
    work: Path
    config: dict

    @property
    def path(self) -> Path:
        return self.work / "site-job.json"

    @property
    def manifest(self) -> Path:
        return self.work / self.config["site"]

    @property
    def output(self) -> Path:
        return self.work / self.config["output"]

    def save(self) -> None:
        self.path.write_text(json.dumps(self.config, ensure_ascii=False))
        return

    def settings(self, mode: str = "write", **extra: str) -> dict:
        return {
            "SITE_CONFIG": str(self.path),
            "SITE_MODE": mode,
            "SITE_FAIL": "",
            "SITE_PAUSE": "",
            "SITE_CONTINUE": "",
            **extra,
        }


def fixture(directory: Path, name: str, inputs: dict[str, bytes], **changes: object) -> Fixture:
    work = directory / name
    work.mkdir(parents=True)
    fix = Fixture(work, {"site": "site.json", "output": "built-site", **changes})
    entries = []
    for index, (identifier, raw) in enumerate(inputs.items()):
        filename = f"input-{index}.md"
        (work / filename).write_bytes(raw)
        entries.append({"id": identifier, "title": identifier + " <&\"'>", "source": filename})
    (work / "site.json").write_text(
        json.dumps({"version": 1, "title": "A <small> & useful site", "pages": entries}, ensure_ascii=False)
    )
    fix.save()
    return fix


def source_files(fix: Fixture) -> list[tuple[dict, Path]]:
    return [(row, fix.manifest.parent / row["source"]) for row in json.loads(fix.manifest.read_bytes())["pages"]]


class DOM(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.tags: list[tuple[str, dict]] = []
        self.identifiers: list[str] = []
        self.links: list[str] = []
        self.heading: dict | None = None
        self.headings: list[dict] = []
        self.stack: list[str] = []

    def handle_starttag(self, tag: str, attrs: list) -> None:
        values = dict(attrs)
        assert len(values) == len(attrs), "duplicate attributes"
        assert tag in {
            "html",
            "head",
            "meta",
            "title",
            "link",
            "body",
            "header",
            "p",
            "nav",
            "a",
            "aside",
            "ol",
            "li",
            "main",
            "h1",
            "h2",
            "h3",
            "h4",
            "h5",
            "h6",
            "ul",
            "pre",
            "code",
            "strong",
            "em",
        }
        assert not any(name.startswith("on") for name in values)
        self.tags.append((tag, values))
        if tag not in {"meta", "link"}:
            self.stack.append(tag)
        if "id" in values:
            self.identifiers.append(values["id"])
        if tag == "a":
            self.links.append(values["href"])
        if re.fullmatch(r"h[1-6]", tag):
            self.heading = {"level": int(tag[1:]), "text": "", "id": values["id"]}
        return

    def handle_data(self, data: str) -> None:
        if self.heading is not None:
            self.heading["text"] += data
        return

    def handle_endtag(self, tag: str) -> None:
        assert self.stack and self.stack.pop() == tag, tag
        if re.fullmatch(r"h[1-6]", tag):
            assert self.heading is not None
            self.headings.append(self.heading)
            self.heading = None
        return


def golden_page(site: dict, row: dict, expected: Expected) -> str:
    navigation = "".join(
        f'<a href="{item["id"]}.html"'
        + (' aria-current="page"' if item["id"] == row["id"] else "")
        + f'>{escaped(item["title"])}</a>\n'
        for item in site["pages"]
    )
    contents = "".join(
        f'<li><a href="#{quote(item["id"], safe="")}">{escaped(item["text"])}</a></li>\n' for item in expected.headings
    )
    return (
        '<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f'<title>{escaped(row["title"])} — {escaped(site["title"])}</title>\n'
        '<link rel="stylesheet" href="style.css">\n</head>\n<body>\n'
        f'<header><p>{escaped(site["title"])}</p><nav aria-label="Pages">\n{navigation}</nav></header>\n'
        f'<aside aria-label="On this page"><ol>\n{contents}</ol></aside>\n<main>\n{expected.body}'
        "</main>\n</body>\n</html>\n"
    )


def outputs(fix: Fixture, report: dict, expected: dict[str, Expected] | None = None) -> dict[str, bytes]:
    site = json.loads(fix.manifest.read_bytes())
    sources = source_files(fix)
    actual = {p.name: p.read_bytes() for p in fix.output.iterdir()}
    names = {"site.json", "style.css", "report.json", "manifest.json"}
    names |= {row["id"] + ".html" for row, _path in sources}
    names |= {f"source-{number}.md" for number in range(len(sources))}
    assert set(actual) == names
    assert actual["report.json"] == (canonical(report) + "\n").encode()
    exported = []
    parsed = {}
    for index, (row, path) in enumerate(sources):
        assert actual[f"source-{index}.md"] == path.read_bytes()
        exported.append({**row, "source": f"source-{index}.md"})
        text = actual[row["id"] + ".html"].decode()
        dom = DOM()
        dom.feed(text)
        dom.close()
        assert not dom.stack and len(set(dom.identifiers)) == len(dom.identifiers)
        observed = report["pages"][index]
        assert observed["headings"] == dom.headings
        assert [item["id"] for item in dom.headings] == anchors([item["text"] for item in dom.headings])
        assert [attrs["href"] for tag, attrs in dom.tags if tag == "link"] == ["style.css"]
        assert [attrs["href"] for tag, attrs in dom.tags if tag == "a" and "aria-current" in attrs] == [
            row["id"] + ".html"
        ]
        if expected is not None:
            golden = expected[row["id"]]
            assert observed["headings"] == golden.headings and observed["links"] == golden.links
            assert text == golden_page(site, row, golden), (fix.work, row["id"], text, golden.body)
        parsed[row["id"] + ".html"] = dom
    for filename, dom in parsed.items():
        for link in dom.links:
            if link.startswith(("http://", "https://")):
                continue
            target, _, fragment = link.partition("#")
            target = target or filename
            assert target in parsed and (not fragment or unquote(fragment) in parsed[target].identifiers), link
    assert json.loads(actual["site.json"]) == {**site, "pages": exported}
    assert b"@media" in actual["style.css"] and b"system-ui" in actual["style.css"]
    assert json.loads(actual["manifest.json"]) == {
        "version": 1,
        "files": {
            name: {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}
            for name, raw in actual.items()
            if name != "manifest.json"
        },
    }
    return actual


def success(app: Application, fix: Fixture, expected: dict[str, Expected] | None = None, mode: str = "write") -> dict:
    sources = source_files(fix)
    before = {path: path.read_bytes() for path in [fix.path, fix.manifest, *(path for _row, path in sources)]}
    result = app.run(fix.work, fix.settings(mode), timeout=180)
    assert result.returncode == 0 and not result.stderr, (fix.work, result)
    report = json.loads(result.stdout)
    site = json.loads(before[fix.manifest])
    assert set(report) == {"version", "title", "entry", "pages"}
    assert report["version"] == 1 and report["title"] == site["title"]
    assert report["entry"] == sources[0][0]["id"] + ".html" and len(report["pages"]) == len(sources)
    for observed, (row, path) in zip(report["pages"], sources, strict=True):
        assert set(observed) == {"id", "title", "source_sha256", "headings", "links"}
        assert observed["id"] == row["id"] and observed["title"] == row["title"]
        assert observed["source_sha256"] == hashlib.sha256(before[path]).hexdigest()
    assert result.stdout == canonical(report) + "\n"
    assert before == {path: path.read_bytes() for path in before}
    if mode == "write":
        outputs(fix, report, expected)
    else:
        assert not fix.output.exists()
    assert not list(fix.output.parent.glob(".site-*"))
    return report


def failure(app: Application, fix: Fixture, message: str = "", **extra: str) -> None:
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
    assert not list(fix.output.parent.glob(".site-*"))
    return


def markup(value: str) -> str:
    return "".join("\\" + character if character in "\\`_*[]" else character for character in value)


def generated_inline(rng: random.Random, depth: int) -> tuple[str, str, str]:
    plain = rng.choice(["a<&\"'", "Straße", "世界 😀", "e\u0301", "x_y [z] * \\", "", "ﬁ Ａ"])
    source, rendered = markup(plain), escaped(plain)
    for level in range(depth):
        delimiter, tag = ("**", "strong") if level % 2 == 0 else ("_", "em")
        source, rendered = delimiter + source + delimiter, f"<{tag}>{rendered}</{tag}>"
    return source, rendered, plain


def scenarios(app: Application, directory: Path) -> dict:
    digests = []
    fix = fixture(directory, "sample", sample())
    report = success(app, fix, sample_expected())
    digests.append(hashlib.sha256((fix.output / "index.html").read_bytes()).hexdigest())
    labeled = [
        ("", "", [], []),
        ("a\nb", "<p>a b</p>\n", [], []),
        (
            "# Heading\nparagraph\n\n- first\n- second\n\nend",
            '<h1 id="heading">Heading</h1>\n<p>paragraph</p>\n<ul>\n<li>first</li>\n<li>second</li>\n</ul>\n<p>end</p>\n',
            [{"level": 1, "text": "Heading", "id": "heading"}],
            [],
        ),
        (
            "# \n## !!!\n### Section-2\n#### !!!",
            '<h1 id="section"></h1>\n<h2 id="section-2">!!!</h2>\n<h3 id="section-2-2">Section-2</h3>\n<h4 id="section-3">!!!</h4>\n',
            [
                {"level": 1, "text": "", "id": "section"},
                {"level": 2, "text": "!!!", "id": "section-2"},
                {"level": 3, "text": "Section-2", "id": "section-2-2"},
                {"level": 4, "text": "!!!", "id": "section-3"},
            ],
            [],
        ),
        (
            "# A\n# A-2\n# A",
            '<h1 id="a">A</h1>\n<h1 id="a-2">A-2</h1>\n<h1 id="a-3">A</h1>\n',
            [
                {"level": 1, "text": "A", "id": "a"},
                {"level": 1, "text": "A-2", "id": "a-2"},
                {"level": 1, "text": "A", "id": "a-3"},
            ],
            [],
        ),
        (
            '<script>alert("x")</script> & &#60;img&#62;',
            "<p>&lt;script&gt;alert(&quot;x&quot;)&lt;/script&gt; &amp; &amp;#60;img&amp;#62;</p>\n",
            [],
            [],
        ),
        (
            "```\n<a onclick='bad()'>\n_**[raw](javascript:x)**_\n```",
            "<pre><code>&lt;a onclick=&#39;bad()&#39;&gt;\n_**[raw](javascript:x)**_</code></pre>\n",
            [],
            [],
        ),
        ("````", None, None, None),
        ("#No heading\n####### seven", "<p>#No heading ####### seven</p>\n", [], []),
        (
            "- \n- `x`\n# Title",
            '<ul>\n<li></li>\n<li><code>x</code></li>\n</ul>\n<h1 id="title">Title</h1>\n',
            [{"level": 1, "text": "Title", "id": "title"}],
            [],
        ),
        (
            r"\_literal\_ \*\*plain\*\* \[x] \\ _em **strong**_",
            "<p>_literal_ **plain** [x] \\ <em>em <strong>strong</strong></em></p>\n",
            [],
            [],
        ),
        (
            "[**bold _em_**](https://example.test/a?x=1&y='ok'#f)",
            '<p><a href="https://example.test/a?x=1&amp;y=&#39;ok&#39;#f"><strong>bold <em>em</em></strong></a></p>\n',
            [],
            ["https://example.test/a?x=1&y='ok'#f"],
        ),
        ("```x\n```", '<pre><code class="language-x"></code></pre>\n', [], []),
    ]
    for index, (source, body, headings, links) in enumerate(labeled):
        fix = fixture(directory, f"labeled-{index}", {"index": source.encode()})
        if body is None:
            failure(app, fix)
        else:
            success(app, fix, {"index": Expected(body, headings, links)})
            digests.append(hashlib.sha256((fix.output / "index.html").read_bytes()).hexdigest())
    texts = [
        "Straße",
        "STRASSE",
        "K",
        "K",
        "ﬁ",
        "fi",
        "世界 😀",
        "e\u0301",
        "é",
        "---",
        "section",
        "Ａ",
        "a",
        "a" * 63 + " ! b",
        "a" * 64 + "x",
        "\u0085",
        "\u200d",
    ]
    ids = anchors(texts)
    source = "\n".join("# " + markup(value) for value in texts)
    body = "".join(
        f'<h1 id="{escaped(anchor)}">{escaped(value)}</h1>\n' for value, anchor in zip(texts, ids, strict=True)
    )
    heads = [{"level": 1, "text": text, "id": anchor} for text, anchor in zip(texts, ids, strict=True)]
    fix = fixture(directory, "unicode-collisions", {"index": source.encode()})
    success(app, fix, {"index": Expected(body, heads, [])})
    rng = random.Random(72072)
    for index in range(60):
        sources = {}
        expected = {}
        for page in ["index", "notes", "guide"]:
            pieces, fragments, headings, links = [], [], [], []
            used_texts = []
            for number in range(8):
                source, rendered, plain = generated_inline(rng, rng.randrange(7))
                if number % 3 == 0:
                    level = rng.randrange(1, 7)
                    used_texts.append(plain)
                    anchor = anchors(used_texts)[-1]
                    pieces.append("#" * level + " " + source)
                    fragments.append(f'<h{level} id="{escaped(anchor)}">{rendered}</h{level}>\n')
                    headings.append({"level": level, "text": plain, "id": anchor})
                elif number % 3 == 1:
                    target = rng.choice(["index", "notes", "guide"])
                    pieces.append(f"[{source}]({target})")
                    fragments.append(f'<p><a href="{target}.html">{rendered}</a></p>\n')
                    links.append(target)
                else:
                    pieces.append("- " + source + "\n- `a<&>`")
                    fragments.append(f"<ul>\n<li>{rendered}</li>\n<li><code>a&lt;&amp;&gt;</code></li>\n</ul>\n")
            sources[page] = "\n\n".join(pieces).encode()
            expected[page] = Expected("".join(fragments), headings, links)
        fix = fixture(directory, f"generated-{index}", sources)
        success(app, fix, expected)
        digests.append(hashlib.sha256((fix.output / "report.json").read_bytes()).hexdigest())
    return {
        "labeled_cases": len(labeled),
        "unicode_collision_headings": len(texts),
        "generated_three_page_sites": 60,
        "observations_sha256": hashlib.sha256(canonical(digests).encode()).hexdigest(),
        "sample_pages": len(report["pages"]),
    }


def invalid_inputs(app: Application, directory: Path) -> int:
    count = 0
    jobs = [None, [], {}, {"site": "site.json"}, {"output": "out"}, {"site": "site.json", "output": "out", "extra": 1}]
    jobs += [{"site": value, "output": "out"} for value in [None, 1, True, [], {}, "", "missing", "a\0b"]]
    jobs += [{"site": "site.json", "output": value} for value in [None, 1, True, [], {}, "", "a\0b", "absent/out"]]
    for index, job in enumerate(jobs):
        fix = fixture(directory, f"job-{index}", {"index": b"# Hello"})
        fix.path.write_text(json.dumps(job))
        result = app.run(fix.work, fix.settings())
        assert result.returncode == 2 and result.stderr and not result.stdout and not fix.output.exists()
        count += 1
    base = {"version": 1, "title": "Site", "pages": [{"id": "index", "title": "Home", "source": "input-0.md"}]}
    manifests = [None, [], {}, {**base, "extra": 1}]
    manifests += [{key: value for key, value in base.items() if key != missing} for missing in base]
    manifests += [{**base, "version": value} for value in [None, True, 0, 2, "1", 1.5]]
    manifests += [
        {**base, "title": value} for value in [None, 1, True, [], {}, "", "x" * 129, "bad\0", "bad\n", "bad\x7f"]
    ]
    manifests += [{**base, "pages": value} for value in [None, 1, True, {}, [], [None], [[]], [{}], ["x"]]]
    row = base["pages"][0]
    badrows = [{**row, "extra": 1}]
    badrows += [{key: value for key, value in row.items() if key != missing} for missing in row]
    badrows += [
        {**row, "id": value} for value in [None, True, 1, "", "-x", "X", "x_y", ".", "..", "a/b", "é", "a\0", "x" * 65]
    ]
    badrows += [{**row, "title": value} for value in [None, 1, [], "", "x" * 129, "bad\r", "bad\t"]]
    badrows += [{**row, "source": value} for value in [None, True, 1, {}, "", "absent", "a\0b"]]
    manifests += [{**base, "pages": [bad]} for bad in badrows]
    manifests += [{**base, "pages": [row, row]}, {**base, "pages": [row, {**row, "id": "other"}]}]
    for index, value in enumerate(manifests):
        fix = fixture(directory, f"manifest-{index}", {"index": b"# Hello"})
        fix.manifest.write_text(json.dumps(value))
        failure(app, fix)
        count += 1
    malformed = [
        b"\xff",
        b"a\0b",
        b"x\ry",
        b"\x1bscript",
        b"\x7f",
        b"**unclosed",
        b"_unclosed",
        b"`unclosed",
        b"trailing\\",
        b"[label]",
        b"[label](",
        b"[label]()",
        b"[outer [inner](index)](index)",
        b"[x](javascript:alert)",
        b"[x](data:text/html,bad)",
        b"[x](file:///etc/passwd)",
        b"[x](//evil.test)",
        b"[x](../index)",
        b"[x](index.html)",
        b"[x](missing)",
        b"[x](#missing)",
        b"[x](index#)",
        b"[x](index#a#b)",
        b"[x](https://a b.test/)",
        b"[x](https://example.test/%GG)",
        b"[x](https://example.test/\\x)",
        b'[x](https://example.test/"onclick="bad)',
        b"[x](https://example.test/<script>)",
        b"[x](https://user:password@example.test/)",
        b"[x](https://example.test:0/)",
        b"```",
        b"``` bad\nx\n```",
        b"```<script>\nx\n```",
        b"[x](#HEADING)\n# Heading",
    ]
    for index, source in enumerate(malformed):
        fix = fixture(directory, f"source-{index}", {"index": source})
        failure(app, fix)
        assert (fix.work / "input-0.md").read_bytes() == source
        count += 1
    for filename in ["site-job.json", "site.json"]:
        for index, raw in enumerate([b"\xff", b"{", b'{"version":1,"version":1}', b"null"]):
            fix = fixture(directory, f"json-{filename}-{index}", {"index": b""})
            (fix.work / filename).write_bytes(raw)
            failure(app, fix)
            count += 1
    fix = fixture(directory, "mode", {"index": b""})
    failure(app, fix, "invalid site mode", SITE_MODE="unknown")
    return count + 1


def nested(depth: int) -> bytes:
    value = "x"
    for level in range(depth):
        delimiter = "**" if level % 2 == 0 else "_"
        value = delimiter + value + delimiter
    return value.encode()


def big_source(size: int) -> bytes:
    prefix = b"```\n" + (b"x" * 8187 + b"\n") * 8
    remaining = size - len(prefix) - len(b"\n```")
    assert 0 <= remaining <= 8192
    return prefix + b"x" * remaining + b"\n```"


def limits(app: Application, directory: Path) -> dict:
    fix = fixture(directory, "32-pages", {f"p{index}": b"# Hello" for index in range(32)})
    success(app, fix)
    fix = fixture(directory, "33-pages", {f"p{index}": b"" for index in range(33)})
    failure(app, fix, "1..32 pages")
    for size in [65536, 65537]:
        fix = fixture(directory, f"source-{size}", {"index": big_source(size)})
        if size == 65536:
            success(app, fix)
        else:
            failure(app, fix, "input byte limit")
    inputs = {f"p{index}": big_source(65536) for index in range(16)}
    fix = fixture(directory, "combined-exact", inputs)
    success(app, fix)
    fix = fixture(directory, "combined-over", {**inputs, "extra": b"x"})
    failure(app, fix, "combined sources")
    for size in [4096, 4097]:
        fix = fixture(directory, f"lines-{size}", {"index": b"\n" * (size - 1)})
        if size == 4096:
            success(app, fix)
        else:
            failure(app, fix, "4096 source lines")
    for size in [8192, 8193]:
        for kind in ["plain", "code", "unicode", "blank"]:
            line = (
                b" " * size
                if kind == "blank"
                else (("é" * (size // 2)).encode() + b"x" * (size % 2) if kind == "unicode" else b"x" * size)
            )
            source = b"```\n" + line + b"\n```" if kind == "code" else line
            fix = fixture(directory, f"line-{kind}-{size}", {"index": source})
            if size == 8192:
                success(app, fix)
            else:
                failure(app, fix, "8192 bytes")
    for size in [8192, 8193]:
        source = b"x" * 4096 + b"\n" + b"x" * (size - 4097)
        fix = fixture(directory, f"paragraph-{size}", {"index": source})
        if size == 8192:
            success(app, fix)
        else:
            failure(app, fix, "inline block")
    for count in [256, 257]:
        fix = fixture(directory, f"headings-{count}", {"index": b"# A\n" * count})
        if count == 256:
            result = success(app, fix)
            assert result["pages"][0]["headings"][-1]["id"] == "a-256"
        else:
            failure(app, fix, "256 headings")
    for depth in [12, 13]:
        fix = fixture(directory, f"nesting-{depth}", {"index": nested(depth)})
        if depth == 12:
            success(app, fix)
        else:
            failure(app, fix, "nesting exceeds 12")
    for depth in [11, 12]:
        fix = fixture(directory, f"label-depth-{depth}", {"index": b"[" + nested(depth) + b"](index)"})
        if depth == 11:
            success(app, fix)
        else:
            failure(app, fix, "nesting exceeds 12")
    for size in [32, 33]:
        fix = fixture(directory, f"language-{size}", {"index": b"```" + b"x" * size + b"\n```"})
        if size == 32:
            success(app, fix)
        else:
            failure(app, fix, "language exceeds 32")
    for filename in ["site-job.json", "site.json"]:
        for size in [65536, 65537]:
            fix = fixture(directory, f"json-{filename}-{size}", {"index": b""})
            path = fix.work / filename
            path.write_bytes(path.read_bytes().ljust(size, b" "))
            if size == 65536:
                success(app, fix)
            else:
                failure(app, fix, "input byte limit")
    fix = fixture(directory, "names-exact", {"a" * 64: b""})
    site = json.loads(fix.manifest.read_bytes())
    site["title"] = "😀" * 128
    site["pages"][0]["title"] = "😀" * 128
    fix.manifest.write_text(json.dumps(site, ensure_ascii=False))
    success(app, fix)
    return {
        "pages": 32,
        "source_bytes": 65536,
        "combined_source_bytes": 1048576,
        "source_lines": 4096,
        "line_and_inline_bytes": 8192,
        "headings_per_page": 256,
        "inline_depth": 12,
        "code_language_characters": 32,
        "config_and_manifest_bytes": 65536,
        "page_id_characters": 64,
        "title_characters": 128,
        "title_bytes": 512,
    }


def link_graphs(app: Application, directory: Path) -> dict:
    count = 0
    digest = hashlib.sha256()
    for mask in range(64):
        nodes = ["index", "guide", "notes"]
        edges = [(a, b) for a in nodes for b in nodes if a != b]
        sources = {}
        expected = {}
        for node in nodes:
            targets = [b for index, (a, b) in enumerate(edges) if a == node and mask & (1 << index)]
            sources[node] = ("# Start\n\n" + " ".join(f"[go]({target}#start)" for target in targets)).encode()
            body = '<h1 id="start">Start</h1>\n'
            if targets:
                body += "<p>" + " ".join(f'<a href="{target}.html#start">go</a>' for target in targets) + "</p>\n"
            expected[node] = Expected(
                body, [{"level": 1, "text": "Start", "id": "start"}], [target + "#start" for target in targets]
            )
        fix = fixture(directory, f"graph-{mask}", sources)
        report = success(app, fix, expected)
        digest.update(canonical(report).encode())
        count += 1
    for index, order in enumerate([["guide", "index"], ["index", "guide"]]):
        fix = fixture(directory, f"order-{index}", {name: sample()[name] for name in order})
        report = success(app, fix, sample_expected())
        assert report["entry"] == order[0] + ".html"
    fix = fixture(directory, "unicode-fragment", {"index": "# 世界 😀\n\n[jump](#世界-😀)".encode()})
    success(app, fix)
    assert 'href="index.html#%E4%B8%96%E7%95%8C-%F0%9F%98%80"' in (fix.output / "index.html").read_text()
    return {
        "three_page_link_graphs": count,
        "page_orderings": 2,
        "unicode_fragments": 1,
        "graph_reports_sha256": digest.hexdigest(),
    }


def paused(app: Application, fix: Fixture) -> subprocess.Popen:
    process = subprocess.Popen(
        app.command,
        cwd=fix.work,
        env=app.environment(fix.settings(SITE_PAUSE="ready", SITE_CONTINUE=str(fix.work / "continue"))),
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
        "source-0.md",
        "source-1.md",
        "site.json",
        "report.json",
        "index.html",
        "guide.html",
        "style.css",
        "manifest.json",
        "ready",
        "published",
    ]
    for point in points:
        fix = fixture(directory, "fault-" + point, sample())
        reference = success(app, fix, mode="preview")
        result = app.run(fix.work, fix.settings(SITE_FAIL=point))
        assert result.returncode == 2 and "injected failure: " + point in result.stderr and not result.stdout
        assert not list(fix.work.glob(".site-*"))
        if point == "published":
            outputs(fix, reference)
        else:
            assert not fix.output.exists()
            success(app, fix)
    for name in ["input-0.md", "input-1.md", "site.json", "config", "destination"]:
        fix = fixture(directory, "changed-" + name, sample())
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
            assert not list(fix.work.glob(".site-*"))
            if name == "destination":
                assert list(fix.output.iterdir()) == [fix.output / "keep"]
                assert (fix.output / "keep").read_bytes() == b"another writer"
            else:
                assert "input changed before publication" in error and not fix.output.exists()
        finally:
            stop(process)
    fix = fixture(directory, "killed", sample())
    reference = success(app, fix, mode="preview")
    process = paused(app, fix)
    stop(process)
    assert not fix.output.exists()
    abandoned = list(fix.work.glob(".site-*"))
    assert len(abandoned) == 1
    old = {path.name: path.read_bytes() for path in abandoned[0].iterdir()}
    result = app.run(fix.work, fix.settings())
    assert result.returncode == 0 and not result.stderr
    outputs(fix, reference)
    assert {path.name: path.read_bytes() for path in abandoned[0].iterdir()} == old
    return len(points) + 6


def paths(app: Application, directory: Path) -> int:
    names = ["input-0.md", "input-1.md", "site.json", "site-job.json"]
    for name in ["file", "directory", "symlink", "dangling", *names]:
        fix = fixture(directory, "destination-" + name, sample())
        if name == "file":
            fix.output.write_bytes(b"preserve")
        elif name == "directory":
            fix.output.mkdir()
            (fix.output / "keep").write_bytes(b"preserve")
        elif name in ["symlink", "dangling"]:
            fix.output.symlink_to(fix.work / ("input-0.md" if name == "symlink" else "missing"))
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
    fix = fixture(directory, "nested-manifest", sample())
    nested = fix.work / "nested"
    nested.mkdir()
    old = fix.manifest
    value = json.loads(old.read_bytes())
    for row in value["pages"]:
        row["source"] = "../" + row["source"]
    old.unlink()
    fix.config["site"] = "nested/site.json"
    fix.manifest.write_text(json.dumps(value))
    fix.save()
    success(app, fix)
    return 14


def check(app: Application, directory: Path) -> dict:
    result = scenarios(app, directory / "scenarios")
    result.update(link_graphs(app, directory / "graphs"))
    print(app.engine + " static site: independent HTML goldens, generated markup and link graphs passed", flush=True)
    result["invalid_inputs"] = invalid_inputs(app, directory / "invalid")
    result["limits"] = limits(app, directory / "limits")
    result["publication_cases"] = publication(app, directory / "publication")
    result["path_cases"] = paths(app, directory / "paths")
    print(app.engine + " static site: validation, bounds, publication and path checks passed", flush=True)
    return result
