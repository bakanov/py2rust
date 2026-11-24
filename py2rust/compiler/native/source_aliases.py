"""Return-retention summaries distinguish outer identity from contained aliases.

Facts contain parameter names, not Python object identities. A least fixed point
propagates these facts through calls and loop backedges. Unknown calls retain all
arguments; indexing a local container exposes its known contents, not its root.
"""

from py2rust.stdlib import Json, json_array, json_equal, json_keys, json_string


def empty_info() -> Json:
    return {"roots": [], "contents": []}


def union(left: Json, right: Json) -> list[str]:
    result: list[str] = []
    for item in json_array(left):
        name: str = json_string(item)
        if name not in result:
            result.append(name)
    for item in json_array(right):
        name = json_string(item)
        if name not in result:
            result.append(name)
    return result


def join_info(left: Json, right: Json) -> Json:
    return {"roots": union(left["roots"], right["roots"]), "contents": union(left["contents"], right["contents"])}


def all_names(info: Json) -> list[str]:
    return union(info["roots"], info["contents"])


def expression_info(node: Json, state: dict[str, Json], proof: Json) -> Json:
    typ: str = json_string(node["type"]["name"])
    if typ in [
        "None",
        "builtins.int",
        "builtins.float",
        "builtins.bool",
        "builtins.str",
        "builtins.bytes",
        "builtins.range",
    ]:
        return empty_info()
    operation: str = json_string(node["operation"])
    operands: list[Json] = json_array(node["operands"])
    if operation == "name":
        name: str = json_string(node["value"]["text"])
        if name in state:
            return state[name]
        return empty_info()
    if operation == "index" or operation == "field":
        owner: Json = expression_info(operands[0], state, proof)
        return {"roots": owner["contents"], "contents": owner["contents"]}
    if operation == "slice":
        owner = expression_info(operands[0], state, proof)
        return {"roots": [], "contents": owner["contents"]}
    if operation == "method_call":
        method: str = json_string(node["value"]["text"])
        owner = expression_info(operands[0], state, proof)
        if method == "copy":
            return {"roots": [], "contents": owner["contents"]}
        if method == "pop":
            return {"roots": owner["contents"], "contents": owner["contents"]}
        if method == "split":
            return empty_info()
    if operation == "runtime_call":
        helper: str = json_string(node["value"]["text"])
        if helper in ["json_loads", "json_loads_unique", "json_keys", "python_syntax_tree", "python_statement_tree"]:
            return empty_info()
        if helper == "json_array":
            owner = expression_info(operands[0], state, proof)
            return {"roots": [], "contents": owner["contents"]}
        if helper == "json_get":
            owner = expression_info(operands[0], state, proof)
            return join_info(
                {"roots": owner["contents"], "contents": owner["contents"]}, expression_info(operands[2], state, proof)
            )
    if operation == "call":
        target: str = json_string(node["value"]["text"])
        if target in json_keys(proof["summaries"]):
            summary: Json = proof["summaries"][target]
            parameters: list[Json] = json_array(proof["parameters"][target])
            roots: list[str] = []
            contents: list[str] = []
            for index in range(len(parameters)):
                parameter: str = json_string(parameters[index])
                argument: Json = expression_info(operands[index], state, proof)
                if parameter in union(summary["roots"], []):
                    roots = union(roots, argument["roots"])
                    contents = union(contents, argument["contents"])
                if parameter in union(summary["contents"], []):
                    contents = union(contents, all_names(argument))
            return {"roots": roots, "contents": contents}
    aggregate: Json = empty_info()
    for operand in operands:
        aggregate = join_info(aggregate, expression_info(operand, state, proof))
    if operation in ["list", "dict", "set", "tuple", "construct", "json_object", "json_array_literal"]:
        return {"roots": [], "contents": all_names(aggregate)}
    return aggregate


def join_state(left: dict[str, Json], right: dict[str, Json]) -> dict[str, Json]:
    result: dict[str, Json] = left.copy()
    for name in right:  # noqa: PLC0206 - portable subset has no items unpacking
        if name in result:
            result[name] = join_info(result[name], right[name])
        else:
            result[name] = right[name]
    return result


def expression_effects(node: Json, initial: dict[str, Json], proof: Json) -> dict[str, Json]:
    state: dict[str, Json] = initial.copy()
    operands: list[Json] = json_array(node["operands"])
    for operand in operands:
        state = expression_effects(operand, state, proof)
    if json_string(node["operation"]) == "method_call" and json_string(node["value"]["text"]) in [  # noqa: SIM102
        "append",
        "extend",
        "insert",
        "add",
    ]:
        if json_string(operands[0]["operation"]) == "name":
            name: str = json_string(operands[0]["value"]["text"])
            if name in state:
                owner: Json = state[name]
                contents: list[str] = all_names({"roots": [], "contents": owner["contents"]})
                for index in range(1, len(operands)):
                    contents = union(contents, all_names(expression_info(operands[index], state, proof)))
                state[name] = {"roots": owner["roots"], "contents": contents}
    return state


def block_info(body: list[Json], initial: dict[str, Json], proof: Json) -> Json:
    state: dict[str, Json] = initial.copy()
    returned: Json = empty_info()
    for node in body:
        operation: str = json_string(node["operation"])
        expressions: list[Json] = json_array(node["expressions"])
        for expression in expressions:
            state = expression_effects(expression, state, proof)
        if operation == "assign":
            state[json_string(node["target"])] = expression_info(expressions[0], state, proof)
        elif operation == "return" and len(expressions) > 0:
            returned = join_info(returned, expression_info(expressions[0], state, proof))
        elif operation == "store_index":
            name: str = json_string(expressions[1]["value"]["text"])
            if name in state:
                owner: Json = state[name]
                state[name] = {
                    "roots": owner["roots"],
                    "contents": union(owner["contents"], all_names(expression_info(expressions[0], state, proof))),
                }
        elif operation == "if":
            combined: dict[str, Json] = {}
            for branch in json_array(node["blocks"]):
                outcome: Json = block_info(json_array(branch), state, proof)
                returned = join_info(returned, outcome["returned"])
                branch_state: dict[str, Json] = {}
                for key in json_keys(outcome["state"]):
                    branch_state[key] = outcome["state"][key]
                combined = join_state(combined, branch_state)
            state = combined.copy()
        elif operation in ["for", "while"]:
            loop_state: dict[str, Json] = state.copy()
            if operation == "for":
                iterable: Json = expression_info(expressions[0], state, proof)
                loop_state[json_string(node["target"])] = {
                    "roots": iterable["contents"],
                    "contents": iterable["contents"],
                }
            changed: bool = True
            while changed:
                outcome = block_info(json_array(node["blocks"][0]), loop_state, proof)
                returned = join_info(returned, outcome["returned"])
                next_state: dict[str, Json] = {}
                for key in json_keys(outcome["state"]):
                    next_state[key] = outcome["state"][key]
                next_state = join_state(loop_state, next_state)
                changed = not json_equal(next_state, loop_state)
                loop_state = next_state.copy()
            state = join_state(state, loop_state)
    return {"state": state, "returned": returned}


def alias_summaries(modules: list[Json]) -> Json:
    functions: list[Json] = []
    parameters: dict[str, Json] = {}
    summaries: dict[str, Json] = {}
    for module in modules:
        for function in json_array(module["functions"]):
            functions.append(function)
            name: str = json_string(function["name"])
            names: list[str] = []
            for parameter in json_array(function["parameters"]):
                names.append(json_string(parameter["name"]))
            parameters[name] = names
            summaries[name] = empty_info()
    changed: bool = True
    while changed:
        changed = False
        proof: Json = {"parameters": parameters, "summaries": summaries}
        updated: dict[str, Json] = summaries.copy()
        for function in functions:
            name: str = json_string(function["name"])
            state: dict[str, Json] = {}
            for parameter in json_array(parameters[name]):
                key: str = json_string(parameter)
                state[key] = {"roots": [key], "contents": []}
            outcome: Json = block_info(json_array(function["body"]), state, proof)
            updated[name] = join_info(summaries[name], outcome["returned"])
            if not json_equal(updated[name], summaries[name]):
                changed = True
        summaries = updated
    return {"parameters": parameters, "summaries": summaries}
