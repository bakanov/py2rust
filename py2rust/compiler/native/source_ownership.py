"""Conservative ownership checks for the source frontend's owned-value backend.

Only fresh outer containers can be mutated. Parameters, extracted children and
uncertain call results remain borrowed. Escaping a mutable name protects it from
later mutation; branch and loop joins preserve that protection. This deliberately
rejects some safe programs until more precise return-alias summaries are available.
"""

from py2rust.stdlib import Json, json_array, json_bool, json_int, json_keys, json_string

from .source_aliases import alias_summaries, all_names


def mutable(node: Json) -> bool:
    name: str = json_string(node["type"]["name"])
    return name not in [
        "None",
        "builtins.int",
        "builtins.float",
        "builtins.bool",
        "builtins.str",
        "builtins.bytes",
        "builtins.range",
    ]


def origins(node: Json, proof: Json) -> list[str]:
    if not mutable(node):
        return []
    operation: str = json_string(node["operation"])
    if operation == "name":
        return [json_string(node["value"]["text"])]
    if operation in ["index", "field", "slice"]:
        return []
    if operation == "runtime_call":
        helper: str = json_string(node["value"]["text"])
        if helper == "json_get":
            return origins(node["operands"][2], proof)
        if helper in [
            "json_loads",
            "json_loads_unique",
            "json_array",
            "json_keys",
            "python_syntax_tree",
            "python_statement_tree",
        ]:
            return []
    if operation == "method_call" and json_string(node["value"]["text"]) in ["copy", "pop"]:
        return []
    if operation == "call":
        target: str = json_string(node["value"]["text"])
        if target in json_keys(proof["summaries"]):
            parameters: list[Json] = json_array(proof["parameters"][target])
            retained: list[str] = all_names(proof["summaries"][target])
            names: list[str] = []
            for index in range(len(parameters)):
                if json_string(parameters[index]) in retained:
                    for name in origins(node["operands"][index], proof):
                        if name not in names:
                            names.append(name)
            return names
    names: list[str] = []
    for operand in json_array(node["operands"]):
        for name in origins(operand, proof):
            if name not in names:
                names.append(name)
    return names


def fresh(node: Json) -> bool:
    operation: str = json_string(node["operation"])
    if operation in ["list", "dict", "set", "construct", "json_object", "json_array_literal", "slice"]:
        return True
    if operation == "method_call":
        method: str = json_string(node["value"]["text"])
        if method == "copy":
            return True
        return method == "split" and json_string(node["operands"][0]["type"]["name"]) == "builtins.str"
    if operation == "runtime_call":
        return json_string(node["value"]["text"]) in [
            "json_loads",
            "json_loads_unique",
            "json_array",
            "json_keys",
            "python_syntax_tree",
            "python_statement_tree",
        ]
    return False


def label(node: Json) -> str:
    source: Json = node["source"]
    return json_string(source["path"]) + ":" + str(json_int(source["line"])) + ":" + str(json_int(source["column"]))


def merge(left: dict[str, bool], right: dict[str, bool]) -> dict[str, bool]:
    result: dict[str, bool] = left.copy()
    for key in right:  # noqa: PLC0206 - portable subset has no items unpacking
        if key not in result or right[key]:
            result[key] = right[key]
    return result


def require_owned(receiver: Json, state: dict[str, bool], barriers: list[str]) -> None:
    assert json_string(receiver["operation"]) == "name", label(receiver) + ": mutation requires a named owner"
    name: str = json_string(receiver["value"]["text"])
    assert name in state and not state[name] and name not in barriers, (
        label(receiver) + ": mutation requires an unshared local owner: " + name
    )
    return


def check_expression(node: Json, initial: dict[str, bool], barriers: list[str], proof: Json) -> dict[str, bool]:
    state: dict[str, bool] = initial.copy()
    operation: str = json_string(node["operation"])
    operands: list[Json] = json_array(node["operands"])
    mutating: bool = operation == "method_call" and json_string(node["value"]["text"]) in [
        "append",
        "extend",
        "insert",
        "pop",
        "clear",
        "reverse",
        "add",
    ]
    active: list[str] = barriers.copy()
    for index in range(len(operands)):
        state = check_expression(operands[index], state, active, proof)
        if not (mutating and index == 0):
            active.extend(origins(operands[index], proof))
    if mutating:
        # Inserted values retain aliases. A self-containing container is not an
        # owned tree and must not be mistaken for an independent Rust copy.
        if json_string(node["value"]["text"]) in ["append", "extend", "insert", "add"]:
            for index in range(1, len(operands)):
                for name in origins(operands[index], proof):
                    state[name] = True
        require_owned(operands[0], state, barriers)
    return state


def check_block(body: list[Json], initial: dict[str, bool], known: list[str], proof: Json) -> dict[str, bool]:
    state: dict[str, bool] = initial.copy()
    for node in body:
        operation: str = json_string(node["operation"])
        expressions: list[Json] = json_array(node["expressions"])
        barriers: list[str] = []
        for index in range(len(expressions)):
            state = check_expression(expressions[index], state, barriers, proof)
            if operation == "store_index" and index == 0:
                barriers.extend(origins(expressions[index], proof))
        if operation == "assign" and mutable(expressions[0]):
            for name in origins(expressions[0], proof):
                state[name] = True
            state[json_string(node["target"])] = not expression_fresh(expressions[0], known, {})
        elif operation == "store_index":
            for name in origins(expressions[0], proof):
                state[name] = True
            require_owned(expressions[1], state, [])
        elif operation == "delete_index":
            require_owned(expressions[0], state, [])
        elif operation == "if":
            branches: list[Json] = json_array(node["blocks"])
            combined: dict[str, bool] = {}
            for branch in branches:
                combined = merge(combined, check_block(json_array(branch), state, known, proof))
            state = combined.copy()
        elif operation == "for" or operation == "while":
            loop_body: list[Json] = json_array(node["blocks"][0])
            loop_state: dict[str, bool] = state.copy()
            if operation == "for":
                loop_state[json_string(node["target"])] = True
                for name in origins(expressions[0], proof):
                    loop_state[name] = True
            changed: bool = True
            while changed:
                condition_state: dict[str, bool] = loop_state.copy()
                if operation == "while":
                    condition_state = check_expression(expressions[0], condition_state, [], proof)
                updated: dict[str, bool] = merge(loop_state, check_block(loop_body, condition_state, known, proof))
                changed = updated != loop_state
                loop_state = updated
            state = merge(state, loop_state)
    return state


def validate_ownership(modules: list[Json]) -> None:
    known: list[str] = fresh_functions(modules)
    proof: Json = alias_summaries(modules)
    for module in modules:
        for function in json_array(module["functions"]):
            state: dict[str, bool] = {}
            for parameter in json_array(function["parameters"]):
                state[json_string(parameter["name"])] = True
            check_block(json_array(function["body"]), state, known, proof)
        check_block(json_array(module["body"]), {}, known, proof)
    return


def expression_fresh(node: Json, known: list[str], owned: dict[str, bool]) -> bool:
    if not mutable(node) or fresh(node):
        return True
    operation: str = json_string(node["operation"])
    if operation == "name":
        name: str = json_string(node["value"]["text"])
        return name in owned and owned[name]
    if operation == "call":
        return json_string(node["value"]["text"]) in known
    if operation == "conditional":
        return expression_fresh(node["operands"][1], known, owned) and expression_fresh(
            node["operands"][2], known, owned
        )
    return False


def return_freshness(body: list[Json], initial: dict[str, bool], known: list[str]) -> Json:
    owned: dict[str, bool] = initial.copy()
    all_fresh: bool = True
    for node in body:
        operation: str = json_string(node["operation"])
        expressions: list[Json] = json_array(node["expressions"])
        if operation == "assign":
            owned[json_string(node["target"])] = expression_fresh(expressions[0], known, owned)
        elif operation == "return" and len(expressions) > 0:
            all_fresh = all_fresh and expression_fresh(expressions[0], known, owned)
        elif operation == "if":
            branches: list[Json] = json_array(node["blocks"])
            outcomes: list[Json] = []
            for branch in branches:
                outcome: Json = return_freshness(json_array(branch), owned, known)
                all_fresh = all_fresh and json_bool(outcome["fresh"])
                outcomes.append(outcome["owned"])
            joined: dict[str, bool] = {}
            for key in json_keys(outcomes[0]):
                safe: bool = True
                for outcome in outcomes:
                    safe = safe and key in json_keys(outcome) and json_bool(outcome[key])
                joined[key] = safe
            owned = joined.copy()
        elif operation == "for" or operation == "while":
            loop_owned: dict[str, bool] = owned.copy()
            if operation == "for":
                loop_owned[json_string(node["target"])] = False
            changed: bool = True
            while changed:
                outcome = return_freshness(json_array(node["blocks"][0]), loop_owned, known)
                all_fresh = all_fresh and json_bool(outcome["fresh"])
                joined: dict[str, bool] = {}
                for key in loop_owned:  # noqa: PLC0206 - portable subset has no items unpacking
                    joined[key] = (
                        loop_owned[key] and key in json_keys(outcome["owned"]) and json_bool(outcome["owned"][key])
                    )
                changed = joined != loop_owned
                loop_owned = joined.copy()
            for key in owned.copy():
                owned[key] = loop_owned[key]
    return {"fresh": all_fresh, "owned": owned}


def fresh_functions(modules: list[Json]) -> list[str]:
    functions: list[Json] = []
    known: list[str] = []
    for module in modules:
        for function in json_array(module["functions"]):
            functions.append(function)
            known.append(json_string(function["name"]))
    changed: bool = True
    while changed:
        changed = False
        retained: list[str] = []
        for function in functions:
            name: str = json_string(function["name"])
            if name not in known:
                continue
            parameters: dict[str, bool] = {}
            for parameter in json_array(function["parameters"]):
                parameters[json_string(parameter["name"])] = False
            result: Json = return_freshness(json_array(function["body"]), parameters, known)
            if json_bool(result["fresh"]):
                retained.append(name)
            else:
                changed = True
        known = retained
    return known
