"""Portable declaration and annotation analysis over the native syntax exchange.

Collect names before resolving signatures so forward and cross-module record
references work. This pass never executes imports or guesses an unknown type.
"""

from py2rust.stdlib import Json, json_array, json_int, json_is_null, json_string

from .source_types import contains_runtime_handle, runtime_handle


def source_label(path: str, node: Json) -> str:
    return path + ":" + str(json_int(node["line"])) + ":" + str(json_int(node["column"]))


def dotted_name(node: Json) -> str:
    kind: str = json_string(node["kind"])
    if kind == "Name":
        return json_string(node["id"])
    if kind == "Attribute":
        return dotted_name(node["value"]) + "." + json_string(node["attr"])
    return ""


def resolve_name(name: str, bindings: dict[str, str]) -> str:
    parts: list[str] = name.split(".")
    if parts[0] in bindings:
        parts[0] = bindings[parts[0]]
        return ".".join(parts)
    return name


def import_origin(module: Json, node: Json) -> str:
    origin: str = json_string(node["module"])
    level: int = json_int(node["level"])
    if level == 0:
        return origin
    package: str = json_string(module["package"])
    parts: list[str] = package.split(".")
    assert package != "" and level <= len(parts), (
        source_label(json_string(module["path"]), node) + ": invalid relative import"
    )
    base: str = ".".join(parts[: len(parts) - level + 1])
    if origin != "":
        base = base + "." + origin
    return base


def module_bindings(module: Json) -> dict[str, str]:
    bindings: dict[str, str] = {}
    module_name: str = json_string(module["name"])
    path: str = json_string(module["path"])
    for node in json_array(module["tree"]["body"]):
        kind: str = json_string(node["kind"])
        if kind in ["FunctionDef", "ClassDef"]:
            name: str = json_string(node["name"])
            assert name not in bindings, source_label(path, node) + ": duplicate binding: " + name
            bindings[name] = module_name + "." + name
        elif kind == "Import" or kind == "ImportFrom":
            for alias in json_array(node["names"]):
                imported: str = json_string(alias["name"])
                local: str = json_string(alias["asname"])
                assert imported != "*", source_label(path, node) + ": wildcard imports are unsupported"
                target: str = imported
                if kind == "ImportFrom":
                    target = import_origin(module, node) + "." + imported
                    if local == "":
                        local = imported
                elif local == "":
                    local = imported.split(".")[0]
                    target = local
                assert local not in bindings, source_label(path, node) + ": duplicate binding: " + local
                bindings[local] = target
    return bindings


def annotation(node: Json, bindings: dict[str, str], records: list[str], path: str) -> Json:
    assert not json_is_null(node), path + ": missing type annotation"
    kind: str = json_string(node["kind"])
    if kind == "Constant" and json_string(node["tag"]) == "none":
        return {"name": "None", "arguments": []}
    if kind == "Subscript":
        container: str = resolve_name(dotted_name(node["value"]), bindings)
        assert container in ["list", "dict", "set", "tuple"], (
            source_label(path, node) + ": unsupported generic: " + container
        )
        arguments: list[Json] = []
        index: Json = node["slice"]
        if json_string(index["kind"]) == "Tuple":
            for item in json_array(index["elts"]):
                arguments.append(annotation(item, bindings, records, path))
        else:
            arguments.append(annotation(index, bindings, records, path))
        count: int = len(arguments)
        assert (
            (container == "dict" and count == 2)
            or (container in ["list", "set"] and count == 1)
            or (container == "tuple" and count > 0)
        ), (source_label(path, node) + ": invalid generic arity")
        if container in ["dict", "set"]:
            assert not contains_runtime_handle(arguments[0]), source_label(path, node) + ": opaque resource key type"
        return {"name": "builtins." + container, "arguments": arguments}
    name: str = resolve_name(dotted_name(node), bindings)
    if name in ["int", "float", "bool", "str", "bytes", "bytearray"]:
        return {"name": "builtins." + name, "arguments": []}
    if name.startswith("py2rust.stdlib.") and runtime_handle(name[15:]):
        return {"name": name, "arguments": []}
    if name == "py2rust.stdlib.Json" or name in records:
        return {"name": name, "arguments": []}
    assert False, source_label(path, node) + ": unknown or unsupported type: " + name
    return {}


def declarations(modules: list[Json]) -> Json:
    records: list[str] = []
    module_names: list[str] = []
    for module in modules:
        name: str = json_string(module["name"])
        assert name not in module_names, "duplicate source module: " + name
        module_names.append(name)
        for node in json_array(module["tree"]["body"]):
            if json_string(node["kind"]) == "ClassDef":
                records.append(name + "." + json_string(node["name"]))
    result: list[Json] = []
    for module in modules:
        bindings: dict[str, str] = module_bindings(module)
        path: str = json_string(module["path"])
        functions: list[Json] = []
        record_definitions: list[Json] = []
        for node in json_array(module["tree"]["body"]):
            kind: str = json_string(node["kind"])
            if kind == "FunctionDef":
                assert len(json_array(node["decorators"])) == 0, (
                    source_label(path, node) + ": function decorators are unsupported"
                )
                parameters: list[Json] = []
                parameter_names: list[str] = []
                for parameter in json_array(node["parameters"]):
                    parameter_name: str = json_string(parameter["name"])
                    assert parameter_name not in parameter_names, source_label(path, node) + ": duplicate parameter"
                    parameter_names.append(parameter_name)
                    parameters.append(
                        {
                            "name": parameter_name,
                            "type": annotation(parameter["annotation"], bindings, records, path),
                            "default": parameter["default"],
                        }
                    )
                functions.append(
                    {
                        "name": bindings[json_string(node["name"])],
                        "parameters": parameters,
                        "result": annotation(node["returns"], bindings, records, path),
                        "syntax": node,
                    }
                )
            elif kind == "ClassDef":
                decorators: list[Json] = json_array(node["decorators"])
                assert (
                    len(decorators) == 1
                    and resolve_name(dotted_name(decorators[0]), bindings) == "dataclasses.dataclass"
                ), (source_label(path, node) + ": only dataclass records are supported")
                assert len(json_array(node["bases"])) == 0 and len(json_array(node["keywords"])) == 0, (
                    source_label(path, node) + ": record inheritance is unsupported"
                )
                fields: list[Json] = []
                field_names: list[str] = []
                for field in json_array(node["body"]):
                    field_kind: str = json_string(field["kind"])
                    if field_kind == "Pass":
                        continue
                    if field_kind == "Expr":
                        value: Json = field["value"]
                        if json_string(value["kind"]) == "Constant" and json_string(value["tag"]) == "str":
                            continue
                    assert field_kind == "AnnAssign" and json_string(field["target"]["kind"]) == "Name", (
                        source_label(path, field) + ": expected an annotated record field"
                    )
                    field_name: str = json_string(field["target"]["id"])
                    assert field_name not in field_names, source_label(path, field) + ": duplicate record field"
                    field_names.append(field_name)
                    fields.append(
                        {
                            "name": field_name,
                            "type": annotation(field["annotation"], bindings, records, path),
                            "default": field["value"],
                            "syntax": field,
                        }
                    )
                record_definitions.append(
                    {"name": bindings[json_string(node["name"])], "fields": fields, "syntax": node}
                )
        result.append(
            {
                "name": module["name"],
                "path": module["path"],
                "bindings": bindings,
                "functions": functions,
                "records": record_definitions,
                "syntax": module["tree"],
            }
        )
    return {"version": 1, "modules": result}
