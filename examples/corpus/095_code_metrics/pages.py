"""Self-contained metric tables and source pages; every displayed source fragment is escaped."""
# ruff: noqa: I001 - compact imports
from project import Source
from py2rust.stdlib import Json, json_array, json_int, json_string

STYLE: str = """
*{box-sizing:border-box}body{margin:0;background:#f4f7fb;color:#1b2b42;font:15px system-ui}
header{padding:24px 32px;background:#172d46;color:white}header small{color:#a5c9e8}h1{margin:8px 0}
a{color:#126aa4;text-decoration:none}a:hover{text-decoration:underline}.layout{display:flex;min-height:85vh}
nav{width:250px;flex-shrink:0;padding:24px;background:white;border-right:1px solid #dce5ee}
nav a{display:block;padding:7px;overflow-wrap:anywhere}main{padding:28px;min-width:0;flex:1}
article{background:white;border:1px solid #dce5ee;border-radius:10px;padding:20px;margin-bottom:20px}
table{border-collapse:collapse;width:100%;font-size:14px}
td,th{text-align:left;padding:10px;border-bottom:1px solid #e8eef4}
th{color:#536780}.flag{color:#a33828;background:#fff1ec}.muted{color:#64758a}code,pre{font:13px ui-monospace,monospace}
.source{overflow:auto;white-space:pre;padding:16px;background:#152538;color:#dce9f5;border-radius:8px}
.line{display:block;min-height:1.5em}.line:target{background:#38516a}
.number{display:inline-block;width:4em;color:#8bbce0}
@media(max-width:760px){.layout{display:block}nav{width:auto}main{padding:12px}table{display:block;overflow:auto}}
"""


def escape(text: str) -> str:
    cleaned: str = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return cleaned.replace('"', "&quot;").replace("'", "&#39;")


def link(href: str, label: str) -> str:
    return '<a href="' + escape(href) + '">' + escape(label) + "</a>"


def shell(title: str, body: str, modules: list[Json]) -> bytes:
    navigation: str = link("index.html", "Project overview")
    for module in modules:
        navigation = navigation + link(json_string(module["page"]), json_string(module["path"]))
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width">'
        + "<title>" + escape(title) + " · Code metrics</title><style>" + STYLE + "</style></head><body>"
        + "<header><small>PYTHON PROJECT / STRUCTURAL METRICS</small><h1>" + escape(title) + "</h1>"
        + '<div>Static source analysis · Use browser Find to search</div></header><div class="layout"><nav>'
        + navigation + "</nav><main>" + body + "</main></div></body></html>"
    ).encode()


def definitions(module: Json) -> str:
    body: str = ("<table><thead><tr><th>Definition</th><th>Lines</th><th>Statements</th>"
                 "<th>Control</th><th>Depth</th><th>Flags</th></tr></thead><tbody>")
    for row in json_array(module["definitions"]):
        flags: list[str] = []
        for flag in json_array(row["flags"]):
            flags.append(json_string(flag))
        css: str = ' class="flag"' if len(flags) > 0 else ""
        href: str = json_string(module["page"]) + "#L" + str(json_int(row["line"]))
        body = body + "<tr" + css + "><td>" + link(href, json_string(row["qualified"]))
        body = body + '</td><td>' + str(json_int(row["lines"])) + "</td>"
        for key in ["statements", "control_statements", "max_depth"]:
            body = body + "<td>" + str(json_int(row["metrics"][key])) + "</td>"
        body = body + "<td>" + escape(", ".join(flags)) + "</td></tr>"
    return body + "</tbody></table>"


def render(source: Source, module: Json, modules: list[Json]) -> bytes:
    body: str = "<article><h2>Definitions</h2>" + definitions(module) + "</article><article><h2>Imports</h2><ul>"
    for item in json_array(module["imports"]):
        label: str = json_string(item["module"]) + " · " + json_string(item["name"])
        href: str = json_string(item["href"])
        body = body + "<li>" + link("#L" + str(json_int(item["line"])), "line " + str(json_int(item["line"]))) + " — "
        body = body + (link(href, label) if href != "" else escape(label))
        body = body + " <small>" + escape(json_string(item["status"])) + "</small></li>"
    body = body + '</ul></article><h2>Source</h2><pre class="source"><code>'
    lines: list[str] = source.text.split("\n")
    for index in range(json_int(module["lines"])):
        number: str = str(index + 1)
        body = body + '<span class="line" id="L' + number + '"><a class="number" href="#L' + number + '">'
        body = body + number + "</a>" + escape(lines[index]) + "</span>"
    return shell(source.name, body + "</code></pre>", modules)


def overview(modules: list[Json], summary: Json) -> bytes:
    body: str = "<article><h2>Project overview</h2><p>"
    for name in ["modules", "functions", "classes", "statements", "flagged_functions"]:
        body = body + str(json_int(summary[name])) + " " + escape(name.replace("_", " ")) + " · "
    body = body + ('</p><p class="muted">Function spans include decorators. Owned statements exclude nested '
                   'definition bodies. Control counts describe statements, not cyclomatic complexity.</p></article>')
    for module in modules:
        body = body + "<article><h2>" + link(json_string(module["page"]), json_string(module["path"])) + "</h2>"
        body = body + '<p class="muted">' + escape(json_string(module["name"]))
        body = body + " · " + str(json_int(module["lines"])) + " source lines</p>"
        body = body + definitions(module) + "</article>"
    return shell("Code metrics browser", body, modules)
