"""Count statements by their nearest definition scope, with explicit physical spans and depth."""
# ruff: noqa: I001 - compact imports
from project import Source, digest
from py2rust.stdlib import Json, json_array, json_get, json_int, json_string


def empty() -> Json:
    return {"statements": 0, "control_statements": 0, "max_depth": 0, "kinds": {}}


def analyze(source: Source, page: str, thresholds: Json) -> Json:
    nodes: list[Json] = json_array(source.tree["nodes"])
    owners: list[int] = []
    depths: list[int] = []
    scopes: list[str] = []
    counts: dict[int, Json] = {-1: empty()}
    definitions: list[Json] = []
    imports: list[Json] = []
    kinds: Json = {}
    for index in range(len(nodes)):
        node: Json = nodes[index]
        parent: int = json_int(node["parent"])
        owner: int = -1 if parent == -1 else owners[parent]
        depth: int = 0 if parent == owner else depths[parent] + 1
        scope: str = source.name if parent == -1 else scopes[parent]
        kind: str = json_string(node["kind"])
        kinds[kind] = json_int(json_get(kinds, kind, 0)) + 1
        counter: Json = counts[owner]
        counter["statements"] = json_int(counter["statements"]) + 1
        counter["max_depth"] = max(json_int(counter["max_depth"]), depth)
        local_kinds: Json = counter["kinds"]
        local_kinds[kind] = json_int(json_get(local_kinds, kind, 0)) + 1
        counter["kinds"] = local_kinds
        if kind in ["If", "For", "AsyncFor", "While", "Try", "TryStar", "With", "AsyncWith", "Match"]:
            counter["control_statements"] = json_int(counter["control_statements"]) + 1
        counts[owner] = counter
        if kind in ["ClassDef", "FunctionDef", "AsyncFunctionDef"]:
            qualified: str = scope + "." + json_string(node["name"])
            start: int = json_int(node["line"])
            for decorator in json_array(node["decorators"]):
                start = min(start, json_int(decorator["line"]))
            definitions.append({
                "id": index, "kind": kind, "name": node["name"], "qualified": qualified,
                "line": node["line"], "column": node["column"], "end_line": node["end_line"],
                "end_column": node["end_column"], "start_line": start,
                "lines": json_int(node["end_line"]) - start + 1, "metrics": None, "flags": [],
            })
            counts[index] = empty()
            owner = index
            scope = qualified if kind == "ClassDef" else qualified + ".<locals>"
        if kind in ["Import", "ImportFrom"]:
            for alias in json_array(node["names"]):
                imports.append({
                    "kind": kind, "line": node["line"], "column": node["column"], "scope": scope,
                    "module": node["module"], "level": node["level"], "name": alias["name"], "alias": alias["asname"],
                    "status": "", "target": "", "href": "",
                })
        owners.append(owner)
        depths.append(depth)
        scopes.append(scope)
    flagged: int = 0
    functions: int = 0
    for index in range(len(definitions)):
        definition: Json = definitions[index]
        metrics: Json = counts[json_int(definition["id"])]
        flags: list[str] = []
        if json_string(definition["kind"]) != "ClassDef":
            functions = functions + 1
            if json_int(definition["lines"]) > json_int(thresholds["lines"]):
                flags.append("lines")
            if json_int(metrics["statements"]) > json_int(thresholds["statements"]):
                flags.append("statements")
            if json_int(metrics["max_depth"]) > json_int(thresholds["depth"]):
                flags.append("depth")
        definition["metrics"] = metrics
        definition["flags"] = flags
        if len(flags) > 0:
            flagged = flagged + 1
        definitions[index] = definition
    lines: int = len(source.text.split("\n")) - (1 if source.text.endswith("\n") else 0)
    if source.text == "":
        lines = 0
    return {
        "path": source.relative, "name": source.name, "package": source.package, "page": page,
        "bytes": len(source.document.data), "sha256": digest(source.document.data), "lines": lines,
        "statements": len(nodes), "kinds": kinds, "top_level": counts[-1], "definitions": definitions,
        "functions": functions, "classes": len(definitions) - functions,
        "flagged_functions": flagged, "imports": imports,
    }
