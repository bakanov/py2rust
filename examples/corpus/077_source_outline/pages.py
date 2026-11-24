"""Small, self-contained HTML pages with source-line and import links."""

from project import Source

from py2rust.stdlib import Json, json_array, json_int, json_string

STYLE: str = (
    """body{margin:0;font:16px system-ui;color:#203040;background:#f4f7fa}header,main{padding:1.5rem;max-width:1100px;margin:auto}header{background:#e2edf5}a{color:#086ba5}nav{display:flex;gap:1rem;flex-wrap:wrap}article{background:white;padding:1rem;margin:1rem 0;border-radius:8px}pre{overflow:auto;white-space:pre-wrap}code{font:14px monospace}.source{white-space:pre;overflow:auto;background:white;padding:1rem}.line{display:block}.line:target{background:#fff1a8}.number{display:inline-block;width:4em;color:#789}small{color:#567}h1{overflow-wrap:anywhere}"""
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


def page(title: str, body: str, modules: list[Json]) -> bytes:
    navigation: str = link("index.html", "Project")
    for module in modules:
        name: str = json_string(module["name"])
        navigation = navigation + link("module-" + name + ".html", name)
    return (
        '<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width">'
        + "<title>"
        + escape(title)
        + "</title><style>"
        + STYLE
        + "</style><header><nav>"
        + navigation
        + "</nav><h1>"
        + escape(title)
        + "</h1></header><main>"
        + body
        + "</main></html>"
    ).encode()


def render(source: Source, module: Json, modules: list[Json]) -> bytes:
    body: str = "<pre>" + escape(json_string(module["docstring"])) + "</pre><h2>Definitions</h2>"
    for definition in json_array(module["definitions"]):
        line: str = str(json_int(definition["line"]))
        body = body + "<article><h3>" + link("#L" + line, json_string(definition["qualified"])) + "</h3><small>"
        body = body + escape(json_string(definition["kind"])) + " · line " + line + "</small>"
        for decorator in json_array(definition["decorators"]):
            body = body + "<pre>@" + escape(json_string(decorator["text"])) + "</pre>"
        body = body + "<pre>" + escape(json_string(definition["docstring"])) + "</pre></article>"
    body = body + "<h2>Imports</h2><ul>"
    for item in json_array(module["imports"]):
        label: str = ""
        for depth in range(json_int(item["level"])):
            label = label + "."
        label = label + json_string(item["module"]) + " " + json_string(item["name"])
        if json_string(item["alias"]) != "":
            label = label + " as " + json_string(item["alias"])
        body = body + "<li>" + link("#L" + str(json_int(item["line"])), "source") + " · "
        if json_string(item["href"]) != "":
            body = body + link(json_string(item["href"]), label)
        else:
            body = body + escape(label) + " <small>(external or unresolved)</small>"
        body = body + "</li>"
    body = body + '</ul><h2>Source</h2><pre class="source"><code>'
    lines: list[str] = source.text.split("\n")
    for index in range(len(lines)):
        number: str = str(index + 1)
        body = body + '<span class="line" id="L' + number + '"><a class="number" href="#L' + number + '">'
        body = body + number + "</a>" + escape(lines[index]) + "</span>"
    return page(source.name, body + "</code></pre>", modules)


def index_page(modules: list[Json]) -> bytes:
    body: str = (
        "<p>Browse modules, definitions, documentation and imports. Use your browser's Find to search a page.</p>"
    )
    for module in modules:
        name: str = json_string(module["name"])
        body = (
            body
            + "<article><h2>"
            + link("module-" + name + ".html", name)
            + "</h2><pre>"
            + escape(json_string(module["docstring"]))
            + "</pre><ul>"
        )
        for definition in json_array(module["definitions"]):
            href: str = "module-" + name + ".html#L" + str(json_int(definition["line"]))
            body = body + "<li>" + link(href, json_string(definition["qualified"])) + "</li>"
        body = body + "</ul></article>"
    return page("Python project outline", body, modules)
