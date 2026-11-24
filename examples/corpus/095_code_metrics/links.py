"""Resolve syntactic module candidates, retaining ambiguity and missing-local classifications."""
from py2rust.stdlib import Json, json_array, json_bool, json_int, json_string


def connect(modules: list[Json]) -> list[Json]:
    pages: dict[str, list[str]] = {}
    namespaces: set[str] = set()
    for module in modules:
        name: str = json_string(module["name"])
        if name not in pages:
            pages[name] = []
        pages[name].append(json_string(module["page"]))
        parts: list[str] = name.split(".")
        for index in range(1, len(parts)):
            namespaces.add(".".join(parts[:index]))
    result: list[Json] = []
    for module in modules:
        imports: list[Json] = []
        for item in json_array(module["imports"]):
            base: str = json_string(item["module"])
            level: int = json_int(item["level"])
            outside: bool = False
            if level > 0:
                parts: list[str] = json_string(module["name"]).split(".")
                if not json_bool(module["package"]):
                    parts.pop()
                outside = level > len(parts)
                if not outside:
                    prefix: str = ".".join(parts[:len(parts) - level + 1])
                    base = prefix if base == "" else prefix + "." + base
            candidate: str = json_string(item["name"])
            imported: bool = json_string(item["kind"]) == "ImportFrom"
            if imported:
                candidate = base + "." + candidate
            status: str = "external"
            target: str = candidate
            href: str = ""
            if outside:
                status = "outside_root"
                target = ""
            else:
                member: bool = imported and candidate not in pages and candidate not in namespaces
                if member and (base in pages or base in namespaces):
                    target = base
                    status = "local_wildcard" if json_string(item["name"]) == "*" else "local_member"
                if target in pages:
                    if len(pages[target]) > 1:
                        status = "ambiguous"
                    else:
                        href = pages[target][0]
                        if not member:
                            status = "local_module"
                elif target in namespaces:
                    if not member:
                        status = "namespace"
                    href = "index.html"
                elif level > 0 or target.split(".")[0] in pages or target.split(".")[0] in namespaces:
                    status = "missing_local"
            item["status"] = status
            item["target"] = target
            item["href"] = href
            imports.append(item)
        module["imports"] = imports
        result.append(module)
    return result
