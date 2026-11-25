"""Backward liveness and move eligibility on compiler-owned IR.

Repeated reads within one evaluation remain copies. Exception/resource regions
are conservative atomic barriers until cleanup-aware ownership is implemented.
"""

from collections import Counter
from dataclasses import dataclass

from . import ir


@dataclass(frozen=True)
class UseDecision:
    expression: ir.Expression
    mode: str
    reason: str


@dataclass(frozen=True)
class FunctionLiveness:
    function: str
    uses: tuple[UseDecision, ...]


@dataclass
class FlowNode:
    reads: list[ir.Expression]
    writes: set[str]
    successors: set[int]
    protected: bool = False


def outer_bindings(function: ir.Function) -> set[str]:
    """Collect declarations, respecting loop/resource/handler binding scopes."""
    result = {param.name for param in function.parameters}

    def block(statements: tuple[ir.Statement, ...], bindings: set[str]) -> None:
        for statement in statements:
            if statement.operation == "assign" and statement.target is not None and statement.target not in bindings:
                result.add(statement.target)
                bindings.add(statement.target)
            for index, child in enumerate(statement.blocks):
                nested = bindings.copy()
                if index == 0 and statement.operation in {"for", "resource_scope"} and statement.target is not None:
                    nested.add(statement.target)
                block(child, nested)
            for handler in statement.handlers:
                nested = bindings.copy()
                if handler.binding is not None:
                    nested.add(handler.binding)
                block(handler.body, nested)
        return  # noqa: PLR1711

    block(function.body, result.copy())
    return result


def analyze_function(function: ir.Function) -> FunctionLiveness:
    graph: list[FlowNode] = []
    bindings = outer_bindings(function)

    def reads(expression: ir.Expression) -> list[ir.Expression]:
        result = [expression] if expression.operation == "name" else []
        for operand in expression.operands:
            result.extend(reads(operand))
        return result

    def statement_reads(statement: ir.Statement) -> list[ir.Expression]:
        result = [name for expression in statement.expressions for name in reads(expression)]
        for child in statement.blocks:
            for item in child:
                result.extend(statement_reads(item))
        for handler in statement.handlers:
            for item in handler.body:
                result.extend(statement_reads(item))
        return result

    def add(names: list[ir.Expression], writes: set[str], successors: set[int], protected: bool = False) -> int:
        graph.append(FlowNode(names, writes, successors, protected))
        return len(graph) - 1

    def block(statements: tuple[ir.Statement, ...], following: set[int], stop: set[int], again: set[int]) -> set[int]:
        entry = following
        for statement in reversed(statements):
            operation = statement.operation
            if operation == "if":
                branches = block(statement.blocks[-1], entry, stop, again)
                for condition, child in reversed(list(zip(statement.expressions, statement.blocks[:-1]))):
                    branches = {add(reads(condition), set(), block(child, entry, stop, again) | branches)}
                entry = branches
            elif operation in {"for", "while"}:
                expression = statement.expressions[0]
                writes = (
                    {statement.target}
                    if operation == "for" and statement.target is not None and statement.target not in bindings
                    else set()
                )
                header = add([] if operation == "for" else reads(expression), writes, set())
                normal_exit = block(statement.blocks[1], entry, stop, again)
                body = block(statement.blocks[0], {header}, entry, {header})
                graph[header].successors = body | normal_exit
                entry = {add(reads(expression), set(), {header})} if operation == "for" else {header}
            elif operation in {"break", "continue"}:
                entry = {add([], set(), stop if operation == "break" else again)}
            else:
                protected = operation in {"try", "resource_scope"} or bool(statement.blocks or statement.handlers)
                writes = {statement.target} if operation == "assign" and statement.target is not None else set()
                successors = set() if operation in {"return", "reraise"} else entry
                entry = {add(statement_reads(statement), set() if protected else writes, successors, protected)}
        return entry

    block(function.body, set(), set(), set())
    live_in: list[set[str]] = [set() for _ in graph]
    live_out: list[set[str]] = [set() for _ in graph]
    changed = True
    while changed:
        changed = False
        for index, node in enumerate(graph):
            outgoing = set().union(*(live_in[successor] for successor in node.successors))
            incoming = {str(name.value) for name in node.reads} | (outgoing - node.writes)
            if incoming != live_in[index] or outgoing != live_out[index]:
                live_in[index], live_out[index] = incoming, outgoing
                changed = True
    decisions = []
    for index, node in enumerate(graph):
        counts = Counter(name.value for name in node.reads)
        for name in node.reads:
            reason = (
                "protected_control_flow"
                if node.protected
                else (
                    "value_live_after_use"
                    if name.value in live_out[index] - node.writes
                    else "repeated_use_in_expression" if counts[name.value] != 1 else "last_use_on_all_successors"
                )
            )
            decisions.append(UseDecision(name, "move" if reason == "last_use_on_all_successors" else "copy", reason))
    return FunctionLiveness(function.name, tuple(decisions))


def analyze(modules: tuple[ir.Module, ...]) -> tuple[FunctionLiveness, ...]:
    return tuple(analyze_function(function) for module in modules for function in module.functions)
