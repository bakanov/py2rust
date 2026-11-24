"""Build scopes and docstrings from the native parser's ordinary statement records."""

from project import Source

from py2rust.stdlib import (
    Json,
    json_array,
    json_bool,
    json_int,
    json_is_null,
    json_string,
)


def indentation(text: str) -> int:
    count: int = 0
    for character in text:
        if character.strip() != "":
            break
        count = count + 1
    return count


def clean_docstring(text: str) -> str:
    expanded: str = ""
    column: int = 0
    for character in text:
        if character == "\t":
            width: int = 8 - column % 8
            for padding in range(width):
                expanded = expanded + " "
            column = column + width
        else:
            expanded = expanded + character
            column = column + 1
            if character == "\n" or character == "\r":
                column = 0
    lines: list[str] = expanded.split("\n")
    margin: int = 131072
    for line in lines[1:]:
        if line[indentation(line) :] != "":
            margin = min(margin, len(line) - len(line[indentation(line) :]))
    lines[0] = lines[0][indentation(lines[0]) :]
    if margin < 131072:
        for index in range(1, len(lines)):
            lines[index] = lines[index][margin:]
    while len(lines) > 0 and lines[-1] == "":
        lines.pop()
    while len(lines) > 0 and lines[0] == "":
        lines.pop(0)
    return "\n".join(lines)


def describe(source: Source) -> Json:
    nodes: list[Json] = json_array(source.tree["nodes"])
    scopes: list[str] = []
    first: dict[int, Json] = {}
    definitions: list[Json] = []
    imports: list[Json] = []
    for index in range(len(nodes)):
        node: Json = nodes[index]
        parent: int = json_int(node["parent"])
        if json_string(node["block"]) == "body" and parent not in first:
            first[parent] = node
        scope: str = source.name
        if parent >= 0:
            scope = scopes[parent]
        kind: str = json_string(node["kind"])
        name: str = json_string(node["name"])
        if kind in ["ClassDef", "FunctionDef", "AsyncFunctionDef", "TypeAlias"]:
            qualified: str = scope + "." + name
            definitions.append(
                {
                    "node": index,
                    "kind": kind,
                    "name": name,
                    "qualified": qualified,
                    "line": node["line"],
                    "end_line": node["end_line"],
                    "decorators": node["decorators"],
                    "docstring": "",
                }
            )
            if kind != "TypeAlias":
                scope = qualified
                if kind != "ClassDef":
                    scope = scope + ".<locals>"
        scopes.append(scope)
        if kind in ["Import", "ImportFrom"]:
            for alias in json_array(node["names"]):
                imports.append(
                    {
                        "kind": kind,
                        "scope": scope,
                        "line": node["line"],
                        "module": node["module"],
                        "level": node["level"],
                        "name": alias["name"],
                        "alias": alias["asname"],
                        "target": "",
                        "href": "",
                    }
                )
    for index in range(len(definitions)):
        definition: Json = definitions[index]
        identity: int = json_int(definition["node"])
        if identity in first and not json_is_null(first[identity]["string"]):
            definition["docstring"] = clean_docstring(json_string(first[identity]["string"]))
        definitions[index] = definition
    docstring: str = ""
    if -1 in first and not json_is_null(first[-1]["string"]):
        docstring = clean_docstring(json_string(first[-1]["string"]))
    return {
        "name": source.name,
        "package": source.package,
        "docstring": docstring,
        "definitions": definitions,
        "imports": imports,
        "statements": len(nodes),
    }


def connect(modules: list[Json]) -> list[Json]:
    pages: dict[str, str] = {}
    symbols: dict[str, str] = {}
    counts: dict[str, int] = {}
    for module in modules:
        name: str = json_string(module["name"])
        pages[name] = "module-" + name + ".html"
        for definition in json_array(module["definitions"]):
            qualified: str = json_string(definition["qualified"])
            if qualified == name + "." + json_string(definition["name"]):
                if qualified not in counts:
                    counts[qualified] = 0
                counts[qualified] = counts[qualified] + 1
                symbols[qualified] = "module-" + name + ".html#L" + str(json_int(definition["line"]))
    result: list[Json] = []
    for module in modules:
        rows: list[Json] = []
        for item in json_array(module["imports"]):
            base: str = json_string(item["module"])
            level: int = json_int(item["level"])
            if level > 0:
                parts: list[str] = json_string(module["name"]).split(".")
                if not json_bool(module["package"]):
                    parts.pop()
                if level > len(parts):
                    base = "!outside-project"
                else:
                    parts = parts[: len(parts) - level + 1]
                    if base != "":
                        parts.append(base)
                    base = ".".join(parts)
            target: str = json_string(item["name"])
            if json_string(item["kind"]) == "ImportFrom":
                target = base + "." + target
            href: str = ""
            if target in pages:
                href = pages[target]
            elif json_string(item["kind"]) == "ImportFrom" and target in counts and counts[target] == 1:
                href = symbols[target]
            elif base in pages:
                target = base
                href = pages[base]
            if href != "":
                item["target"] = target
                item["href"] = href
            rows.append(item)
        module["imports"] = rows
        result.append(module)
    return result
