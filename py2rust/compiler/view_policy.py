"""Plan borrowed slice and JSON-array locals on typed IR."""

from collections import Counter
from dataclasses import dataclass

from . import ir
from .parameter_policy import place_root, write_reasons

SEQUENCES = frozenset({"builtins.bytes", "builtins.bytearray", "builtins.list", "builtins.tuple"})


@dataclass(frozen=True)
class ViewDecision:
    target: str
    backing: str
    kind: str
    source: ir.Source


@dataclass(frozen=True)
class FunctionViews:
    function: str
    views: tuple[ViewDecision, ...]

    def bindings(self, kind: str) -> dict[str, str]:
        return {view.target: view.backing for view in self.views if view.kind == kind}


def statements(body: tuple[ir.Statement, ...]) -> list[ir.Statement]:
    result = []
    for statement in body:
        result.append(statement)
        for block in statement.blocks:
            result.extend(statements(block))
        for handler in statement.handlers:
            result.extend(statements(handler.body))
    return result


def analyze_function(function: ir.Function, stable_expressions: frozenset[ir.Expression]) -> FunctionViews:
    body = statements(function.body)
    stores = Counter(item.target for item in body if item.operation in {"assign", "for", "resource_scope"})
    stores.update(handler.binding for item in body for handler in item.handlers if handler.binding)
    parameter_names = {parameter.name for parameter in function.parameters}
    declarations = [
        item
        for item in body
        if item.operation == "assign"
        and item.target not in parameter_names
        and stores[item.target] == 1
        and item.expressions
    ]
    views = []
    for kind, types in (
        ("text", {"builtins.str"}),
        ("sequence", SEQUENCES),
        ("array", {"py2rust.stdlib.Json"}),
    ):
        parameters = {parameter.name for parameter in function.parameters if parameter.type.name in types}
        stable = parameters - (stores.keys() if kind == "text" else write_reasons(function, parameters).keys())
        candidates = []
        for item in declarations:
            value = item.expressions[0]
            if kind == "array":
                if (
                    item.target_type == ir.ValueType("builtins.list", (ir.ValueType("py2rust.stdlib.Json"),))
                    and value.operation == "runtime_call"
                    and value.value == "json_array"
                    and len(value.operands) == 1
                    and value.operands[0] in stable_expressions
                    and place_root(value.operands[0]) in stable
                ):
                    candidates.append((item, place_root(value.operands[0])))
            elif (
                item.target_type is not None
                and item.target_type.name in (types | {"tuple"} if kind == "sequence" else types)
                and value.operation == "slice"
                and value.operands[0].operation == "name"
                and (kind == "text" or value in stable_expressions)
            ):
                candidates.append((item, str(value.operands[0].value)))
        writes = (
            write_reasons(function, {item.target for item, _ in candidates}, frozenset(item for item, _ in candidates))
            if kind != "text"
            else {}
        )
        backing = {}
        changed = True
        while changed:
            changed = False
            for item, origin in candidates:
                if item.target not in backing and item.target not in writes and origin in stable | backing.keys():
                    backing[item.target] = origin if origin in stable else backing[origin]
                    views.append(ViewDecision(item.target, backing[item.target], kind, item.source))
                    changed = True
    return FunctionViews(function.name, tuple(views))


def analyze(modules: tuple[ir.Module, ...], stable_expressions: frozenset[ir.Expression]) -> tuple[FunctionViews, ...]:
    return tuple(analyze_function(function, stable_expressions) for module in modules for function in module.functions)
