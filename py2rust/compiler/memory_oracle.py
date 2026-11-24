"""Conservative typed-IR proofs for borrowing across application calls.

Failure and allocation are allowed: this plan never permits reordering. The proof
excludes resources, callbacks, native calls and mutation. It does not establish
returned-alias, exclusive-access or ownership-transfer contracts.
"""

from dataclasses import dataclass

from . import ir
from .binding_policy import IterationDecision, iterations
from .libraries.method_effects import stable_string_method
from .library_contracts import RUNTIME_VALUE_READERS
from .liveness import FunctionLiveness
from .liveness import analyze as liveness_plan
from .move_safety import MoveSafetyPlan
from .move_safety import analyze as move_safety_plan
from .mutation_policy import CollectionMutation, direct_mutation
from .parameter_policy import FunctionParameters
from .parameter_policy import analyze as parameter_plan
from .view_policy import FunctionViews
from .view_policy import analyze as view_plan


@dataclass(frozen=True)
class ProofBlocker:
    reason: str
    source: ir.Source
    detail: str


@dataclass(frozen=True)
class FunctionMemoryDecision:
    function: str
    source: ir.Source
    nonmutating: bool
    blocker: ProofBlocker | None = None


@dataclass(frozen=True)
class EvaluationProof:
    stable: bool
    blocker: ProofBlocker | None = None
    mutations: tuple[CollectionMutation, ...] = ()


@dataclass(frozen=True)
class MemoryPlan:
    functions: tuple[FunctionMemoryDecision, ...]
    evaluations: tuple[tuple[ir.Expression, EvaluationProof], ...] = ()
    parameters: tuple[FunctionParameters, ...] = ()
    liveness: tuple[FunctionLiveness, ...] = ()
    move_safety: MoveSafetyPlan | None = None
    views: tuple[FunctionViews, ...] = ()
    iterations: tuple[tuple[ir.Statement, IterationDecision], ...] = ()

    def evaluation_facts(self) -> dict[ir.Expression, EvaluationProof]:
        return dict(self.evaluations)

    @property
    def nonmutating_functions(self) -> frozenset[str]:
        return frozenset(item.function for item in self.functions if item.nonmutating)


def value_type(typ: ir.ValueType) -> bool:
    return typ.name in {
        "None",
        "builtins.int",
        "builtins.float",
        "builtins.bool",
        "builtins.str",
        "builtins.bytes",
        "builtins.list",
        "builtins.dict",
        "builtins.set",
        "builtins.tuple",
        "tuple",
        "py2rust.stdlib.Json",
    } and all(value_type(argument) for argument in typ.arguments)


def expression_blocker(expression: ir.Expression, known: set[str]) -> ProofBlocker | None:
    if not value_type(expression.type):
        return ProofBlocker("unsupported_value_type", expression.source, expression.type.name)
    for operand in expression.operands:
        blocker = expression_blocker(operand, known)
        if blocker is not None:
            return blocker
    if stable_string_method(expression):
        return None
    if expression.operation == "runtime_call" and expression.value in RUNTIME_VALUE_READERS:
        return None
    if expression.operation == "call":
        if expression.value in known or expression.value == "builtins.len":
            return None
        return ProofBlocker("unproven_callee", expression.source, str(expression.value))
    if expression.operation not in {
        "literal",
        "name",
        "binary",
        "unary",
        "short_circuit",
        "compare_chain",
        "conditional",
        "list",
        "tuple",
        "dict",
        "set",
        "index",
        "slice",
        "json_coerce",
        "json_object",
        "json_array_literal",
    }:
        return ProofBlocker("unsupported_expression", expression.source, expression.operation)
    return None


def block_blocker(statements: tuple[ir.Statement, ...], known: set[str]) -> ProofBlocker | None:
    for statement in statements:
        if statement.operation not in {"assign", "return", "expression", "if", "assert", "pass"}:
            return ProofBlocker("unsupported_statement", statement.source, statement.operation)
        if statement.handlers:
            return ProofBlocker("exception_region", statement.source, statement.operation)
        for expression in statement.expressions:
            blocker = expression_blocker(expression, known)
            if blocker is not None:
                return blocker
        for block in statement.blocks:
            blocker = block_blocker(block, known)
            if blocker is not None:
                return blocker
    return None


def function_blocker(function: ir.Function, known: set[str]) -> ProofBlocker | None:
    if not value_type(function.result):
        return ProofBlocker("unsupported_result_type", function.source, function.result.name)
    for parameter in function.parameters:
        if not value_type(parameter.type):
            return ProofBlocker("unsupported_parameter_type", function.source, parameter.name)
    return block_blocker(function.body, known)


def evaluation_facts(
    modules: tuple[ir.Module, ...], known: set[str]
) -> tuple[tuple[ir.Expression, EvaluationProof], ...]:
    """Prove argument evaluation stable without guessing from reconstructed AST.

    A plain place read does not mutate even for a resource or record. Calls require
    an explicit proof; structural len cannot invoke user-defined methods here.
    Errors and allocations remain ordered and are not claims of purity.
    """
    facts: dict[ir.Expression, EvaluationProof] = {}
    structural = {
        "literal",
        "name",
        "binary",
        "unary",
        "short_circuit",
        "compare_chain",
        "conditional",
        "list",
        "tuple",
        "dict",
        "set",
        "index",
        "slice",
        "field",
        "enum_member",
        "json_coerce",
        "json_object",
        "json_array_literal",
    }

    def visit(expression: ir.Expression) -> EvaluationProof:
        if expression in facts:
            return facts[expression]
        operands = [visit(operand) for operand in expression.operands]
        blocker = next((proof.blocker for proof in operands if not proof.stable), None)
        supported = expression.operation in structural or stable_string_method(expression)
        if expression.operation == "runtime_call":
            supported = expression.value in RUNTIME_VALUE_READERS
        if expression.operation == "call":
            supported = expression.value in known or (
                expression.value == "builtins.len"
                and len(expression.operands) == 1
                and value_type(expression.operands[0].type)
            )
        if blocker is None and not supported:
            blocker = ProofBlocker(
                "unproven_argument_evaluation", expression.source, str(expression.value or expression.operation)
            )
        direct = direct_mutation(expression)
        mutations = ((direct,) if direct is not None else ()) + tuple(
            mutation for proof in operands for mutation in proof.mutations
        )
        result = EvaluationProof(blocker is None, blocker, mutations)
        facts[expression] = result
        return result

    def block(statements: tuple[ir.Statement, ...]) -> None:
        for statement in statements:
            for expression in statement.expressions:
                visit(expression)
            for child in statement.blocks:
                block(child)
            for handler in statement.handlers:
                block(handler.body)
        return  # noqa: PLR1711 - explicit return required by repository guidelines

    for module in modules:
        block(module.body)
        for function in module.functions:
            block(function.body)
        for record in module.records:
            for field in record.fields:
                if field.default is not None:
                    visit(field.default)
        for enum in module.enums:
            for _, expression in enum.members:
                visit(expression)
    return tuple(facts.items())


def analyze(modules: tuple[ir.Module, ...]) -> MemoryPlan:
    """Prove callees first; unresolved recursive components stay conservative."""
    functions = [function for module in modules for function in module.functions]
    known: set[str] = set()
    changed = True
    while changed:
        changed = False
        for function in functions:
            if function.name not in known and function_blocker(function, known) is None:
                known.add(function.name)
                changed = True
    evaluations = evaluation_facts(modules, known)
    return MemoryPlan(
        tuple(
            FunctionMemoryDecision(
                function.name,
                function.source,
                function.name in known,
                None if function.name in known else function_blocker(function, known),
            )
            for function in functions
        ),
        evaluations,
        parameter_plan(modules, (expression for expression, _ in evaluations)),
        liveness_plan(modules),
        move_safety_plan(modules),
        view_plan(modules, frozenset(expr for expr, proof in evaluations if proof.stable)),
        iterations(modules),
    )
