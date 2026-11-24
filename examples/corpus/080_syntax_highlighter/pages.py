"""Render fixed, themed HTML structure while escaping every label and source token."""

from lexing import Token
from project import Project, Source

from py2rust.stdlib import json_int, json_string

STYLE: str = (
    """*{box-sizing:border-box}body{--bg:#f4f7fb;--panel:#fff;--ink:#223249;--muted:#65758d;--border:#dbe3ed;--link:#1768b2;--string:#156b41;--number:#8b3bb0;--comment:#667d70;--error:#bd2340;margin:0;background:var(--bg);color:var(--ink);font:16px system-ui}.dark{--bg:#141c29;--panel:#1c2839;--ink:#dbe7f6;--muted:#99abc2;--border:#35445b;--link:#80b9ff;--string:#8fd5a6;--number:#d5a5ff;--comment:#9bad9f;--error:#ff9aad}header,main{max-width:1200px;margin:auto;padding:1.5rem}header{border-bottom:1px solid var(--border)}h1{font-size:1.7rem;overflow-wrap:anywhere}a{color:var(--link)}nav{display:flex;gap:1rem;flex-wrap:wrap}article,.listing{background:var(--panel);border:1px solid var(--border);border-radius:.6rem;padding:1rem;margin:1rem 0}.listing{display:flex;padding:0;overflow:auto}pre{margin:0;padding:1rem;white-space:pre;font:14px/1.65 'DejaVu Sans Mono',monospace;tab-size:4}.gutter{color:var(--muted);border-right:1px solid var(--border);text-align:right;user-select:none}code{font:inherit}.keyword{color:var(--link);font-weight:bold}.number{color:var(--number)}.string{color:var(--string)}.comment{color:var(--comment);font-style:italic}.error{color:var(--error);text-decoration:underline wavy}span:target{outline:2px solid var(--link)}small{color:var(--muted)}li{margin:.5rem 0}footer{margin-top:1.5rem;color:var(--muted)}"""
)


def escape(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )


def link(href: str, label: str) -> str:
    return '<a href="' + escape(href) + '">' + escape(label) + "</a>"


def page(title: str, body: str, project: Project) -> bytes:
    navigation: list[str] = [link("index.html", "Project")]
    for index in range(len(project.sources)):
        navigation.append(link("file-" + str(index) + ".html", project.sources[index].label))
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
        + "<title>"
        + escape(title)
        + '</title><link rel="stylesheet" href="style.css"></head><body class="'
        + project.theme
        + '"><header><nav>'
        + "".join(navigation)
        + "</nav><h1>"
        + escape(title)
        + "</h1></header><main>"
        + body
        + "<footer>Configuration source viewer · "
        + escape(project.theme)
        + " theme</footer></main></body></html>"
    ).encode()


def render(source: Source, index: int, project: Project) -> bytes:
    pieces: list[str] = []
    for number in range(len(source.highlight.tokens)):
        token: Token = source.highlight.tokens[number]
        pieces.append(
            '<span class="'
            + token.kind.value
            + '" id="t'
            + str(number)
            + '" data-start="'
            + str(token.start)
            + '" data-end="'
            + str(token.end)
            + '">'
            + escape(token.text)
            + "</span>"
        )
    numbers: list[str] = []
    for number in range(len(source.highlight.text.split("\n"))):
        numbers.append(str(number + 1))
    body: str = '<p><a download href="file-' + str(index) + '.source">Download original source</a> · '
    body = body + str(len(numbers)) + " lines · " + str(len(pieces)) + " tokens</p>"
    if len(source.highlight.diagnostics) > 0:
        body = body + '<section aria-label="Diagnostics"><h2>Diagnostics</h2><ul>'
        for diagnostic in source.highlight.diagnostics:
            label: str = (
                str(json_int(diagnostic["line"]))
                + ":"
                + str(json_int(diagnostic["column"]))
                + ": "
                + json_string(diagnostic["message"])
            )
            body = body + "<li>" + link("#t" + str(json_int(diagnostic["token"])), label) + "</li>"
        body = body + "</ul></section>"
    body = body + '<div class="listing"><pre class="gutter" aria-hidden="true">' + "\n".join(numbers)
    body = body + '</pre><pre><code id="source">' + "".join(pieces) + "</code></pre></div>"
    return page(source.label, body, project)


def index_page(project: Project) -> bytes:
    body: list[str] = ["<p>Browse highlighted configuration text. Source is displayed without execution.</p>"]
    for index in range(len(project.sources)):
        source: Source = project.sources[index]
        body.append(
            "<article><h2>"
            + link("file-" + str(index) + ".html", source.label)
            + "</h2><p>"
            + str(len(source.highlight.tokens))
            + " tokens · "
            + str(len(source.highlight.diagnostics))
            + " diagnostics</p></article>"
        )
    body.append(
        "<p>" + link("report.json", "Token report") + " · " + link("highlight-job.json", "Replay project") + "</p>"
    )
    return page("Configuration source viewer", "".join(body), project)
