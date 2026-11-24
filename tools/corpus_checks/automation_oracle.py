"""Independent arithmetic AST and lexical environment oracle for generated programs."""

# ruff: noqa: PLR1711 - explicit repository returns
import ast
import operator
import random


def render(nodes: list[dict], depth: int = 0, line: int = 1) -> list[str]:
    lines = []
    for node in nodes:
        node["location"] = f"{line+len(lines)}:{depth*2+1}: "
        prefix = "  " * depth
        kind = node["kind"]
        text = prefix + kind + " "
        if kind in ["let", "set"]:
            text += node["name"] + " = "
        text += node["expr"]
        if kind in ["if", "repeat"]:
            lines.append(text + " {")
            lines.extend(render(node["body"], depth + 1, line + len(lines)))
            if kind == "if":
                lines.append(prefix + "} else {")
                lines.extend(render(node["other"], depth + 1, line + len(lines)))
            lines.append(prefix + "}")
        else:
            lines.append(text)
    return lines


class Halt(Exception):
    pass


def reference(nodes: list[dict], budget: int) -> dict:
    frames = [{}]
    output = []
    steps = 0
    failure = ""

    def frame(name: str, location: str) -> dict[str, int]:
        for scope in reversed(frames):
            if name in scope:
                return scope
        raise Halt(location + "undefined variable: " + name)

    def expression(source: str, location: str) -> int:
        def visit(node: ast.AST) -> int:
            if isinstance(node, ast.Constant):
                value = node.value
            elif isinstance(node, ast.Name):
                value = frame(node.id, location)[node.id]
            elif isinstance(node, ast.UnaryOp):
                # Signed-literal folding permits the minimum i64, as the grammar specifies.
                if isinstance(node.op, ast.USub) and isinstance(node.operand, ast.Constant):
                    value = -node.operand.value
                else:
                    value = visit(node.operand)
                    if isinstance(node.op, ast.USub):
                        value = -value
            elif isinstance(node, ast.BinOp):
                a, b = visit(node.left), visit(node.right)
                if isinstance(node.op, (ast.FloorDiv, ast.Mod)) and b == 0:
                    raise Halt(location + "division by zero")
                value = {
                    ast.Add: operator.add,
                    ast.Sub: operator.sub,
                    ast.Mult: operator.mul,
                    ast.FloorDiv: operator.floordiv,
                    ast.Mod: operator.mod,
                }[type(node.op)](a, b)
            elif isinstance(node, ast.Compare):
                a, b = visit(node.left), visit(node.comparators[0])
                value = int(
                    {
                        ast.Eq: operator.eq,
                        ast.NotEq: operator.ne,
                        ast.Lt: operator.lt,
                        ast.LtE: operator.le,
                        ast.Gt: operator.gt,
                        ast.GtE: operator.ge,
                    }[type(node.ops[0])](a, b)
                )
            else:
                raise TypeError(node)
            if not -(1 << 63) <= value < 1 << 63:
                raise Halt(location + "integer outside signed 64-bit range")
            return value

        return visit(ast.parse(source, mode="eval").body)

    def charge(location: str) -> None:
        nonlocal steps
        if steps == budget:
            raise Halt(location + "step budget exhausted")
        steps += 1
        return

    def execute(items: list[dict]) -> None:
        for node in items:
            loc = node["location"]
            kind = node["kind"]
            charge(loc)
            # Cases with runtime arithmetic/lookup errors below use a lone expression
            # whose coordinate equals its expression start, handled separately later.
            value = expression(node["expr"], loc)
            if kind == "let":
                if node["name"] in frames[-1]:
                    raise Halt(loc + "variable already declared: " + node["name"])
                frames[-1][node["name"]] = value
            elif kind == "set":
                frame(node["name"], loc)[node["name"]] = value
            elif kind == "emit":
                output.append(value)
            else:
                if kind == "repeat" and value < 0:
                    raise Halt(loc + "repeat count must be nonnegative")
                body = node["body"] if kind == "repeat" or value else node["other"]
                count = value if kind == "repeat" else 1
                for _ in range(count):
                    if kind == "repeat":
                        charge(loc)
                    frames.append({})
                    try:
                        execute(body)
                    finally:
                        frames.pop()
        return

    try:
        execute(nodes)
    except Halt as error:
        failure = str(error)
    return {
        "variables": frames[0],
        "emitted": output,
        "steps": steps,
        "error": failure,
        "status": "error" if failure else "ok",
    }


def statement(kind: str, expr: str, name: str = "") -> dict:
    return {"kind": kind, "expr": expr, "name": name}


def generated() -> list:
    programs = []
    rng = random.Random(79079)
    for index in range(160):
        n = rng.randrange(7)
        seed = rng.randrange(-10, 11)
        budget = rng.randrange(100)
        body = [
            statement("let", "seed + 1", "local"),
            statement("set", "total + local", "total"),
            statement("set", "seed + 1", "seed"),
        ]
        choice = {
            "kind": "if",
            "expr": rng.choice(["local % 2 == 0", "local < 0", "seed >= 3", "local != 4"]),
            "body": [statement("let", "local + 10", "total"), statement("emit", "total")],
            "other": [statement("emit", "local"), statement("set", "total - 1", "total")],
        }
        body.append(choice)
        if index % 3 == 0:
            body.append(
                {
                    "kind": "repeat",
                    "expr": str(rng.randrange(3)),
                    "body": [statement("let", "local * 2", "local"), statement("emit", "local")],
                }
            )
        nodes = [
            statement("let", str(seed), "seed"),
            statement("let", "0", "total"),
            {"kind": "repeat", "expr": str(n), "body": body},
            statement("emit", "total"),
        ]
        source = "\n".join(render(nodes)) + "\n"
        programs.append((source, budget, reference(nodes, budget)))
    return programs
