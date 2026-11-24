"""Flatten compiler-owned node trees into the validated topological IR exchange.

Traversal is iterative and all storage is local: helpers do not depend on implicit
mutation of borrowed parameters. Duplicate subtrees need no object identities.
"""

from py2rust.stdlib import Json, json_array, json_bool, json_is_null, json_string

from .ir_schema import node_schema, validate_document


def children(node: Json) -> list[Json]:
    result: list[Json] = []
    schema: dict[str, str] = node_schema(json_string(node["kind"]))
    for field in schema:  # noqa: PLC0206 - portable subset has no items unpacking
        shape: str = schema[field]
        value: Json = node[field]
        if shape.startswith("ref:") or (shape.startswith("optional:") and not json_is_null(value)):
            result.append(value)
        elif shape.startswith("list:"):
            result.extend(json_array(value))
        elif shape == "blocks":
            for block in json_array(value):
                result.extend(json_array(block))
        elif shape == "members":
            for member in json_array(value):
                result.append(member[1])
    return result


def reference_row(node: Json, references: list[int]) -> Json:
    result: Json = {"kind": node["kind"]}
    schema: dict[str, str] = node_schema(json_string(node["kind"]))
    position: int = 0
    for field in schema:  # noqa: PLC0206 - portable subset has no items unpacking
        shape: str = schema[field]
        value: Json = node[field]
        if shape.startswith("ref:") or (shape.startswith("optional:") and not json_is_null(value)):
            result[field] = references[position]
            position = position + 1
        elif shape.startswith("list:"):
            ids: list[int] = []
            for item in json_array(value):
                ids.append(references[position])
                position = position + 1
            result[field] = ids
        elif shape == "blocks":
            blocks: list[Json] = []
            for block in json_array(value):
                block_ids: list[int] = []
                for statement in json_array(block):
                    block_ids.append(references[position])
                    position = position + 1
                blocks.append(block_ids)
            result[field] = blocks
        elif shape == "members":
            members: list[Json] = []
            for member in json_array(value):
                members.append([member[0], references[position]])
                position = position + 1
            result[field] = members
        else:
            result[field] = value
    assert position == len(references), "IR builder reference count mismatch"
    return result


def build_document(modules: list[Json], entry: str) -> Json:
    nodes: list[Json] = []
    roots: list[int] = []
    for module in modules:
        pending: list[Json] = [{"node": module, "exit": False}]
        results: list[int] = []
        while len(pending) > 0:
            task: Json = pending.pop()
            node: Json = task["node"]
            nested: list[Json] = children(node)
            if json_bool(task["exit"]):
                references: list[int] = []
                for index in range(len(nested)):
                    references.insert(0, results.pop())
                nodes.append(reference_row(node, references))
                results.append(len(nodes) - 1)
            else:
                pending.append({"node": node, "exit": True})
                for offset in range(len(nested)):
                    pending.append({"node": nested[len(nested) - offset - 1], "exit": False})
        assert len(results) == 1, "IR builder root count mismatch"
        roots.append(results[0])
    document: Json = {"format": 1, "entry": entry, "nodes": nodes, "modules": roots}
    validate_document(document)
    return document
