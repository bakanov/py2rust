"""IR effect facts and transitive diagnostics, separate from ownership proofs."""

from collections.abc import Mapping
from dataclasses import dataclass

from . import ir
from .effects import RUNTIME_SUMMARIES, UNKNOWN, Effects, FunctionSummary
from .parameter_policy import write_reasons
from .view_policy import statements

BUILTINS = frozenset(
    {
        "len",
        "range",
        "min",
        "max",
        "int",
        "float",
        "bool",
        "str",
        "bytes",
        "bytearray",
        "list",
        "tuple",
        "sorted",
        "ord",
        "chr",
    }
)
CALLS = frozenset({"call", "runtime_call", "native_call", "method_call", "intrinsic_call", "construct"})


@dataclass(frozen=True)
class FunctionEffects:
    function: str
    source: ir.Source
    parameters_may_write: frozenset[str]
    direct: Effects
    calls: tuple[ir.Expression, ...]


def call_name(value: ir.Expression) -> str:
    if value.operation == "method_call":
        receiver = value.operands[0]
        owner = str(receiver.value) if receiver.operation == "name" else receiver.type.name
        return f"{owner}.{value.value}"
    return str(value.value)


@dataclass(frozen=True)
class EffectPlan:
    functions: tuple[FunctionEffects, ...]

    def summarize(
        self, selections: Mapping[ir.Expression, str], symbols: Mapping[str, str]
    ) -> dict[str, FunctionSummary]:
        names = {function.function for function in self.functions}
        direct = {}
        calls = {}
        unknown = {}
        for function in self.functions:
            effect = function.direct
            callees = set()
            missing = set()
            for call in function.calls:
                target = call_name(call)
                if call.operation == "call" and target in names:
                    callees.add(target)
                elif call.operation == "runtime_call":
                    helper = selections.get(call, target)
                    if helper in RUNTIME_SUMMARIES:
                        effect = effect.join(RUNTIME_SUMMARIES[helper].effects)
                    else:
                        missing.add(helper)
                        effect = effect.join(UNKNOWN)
                elif call.operation == "call" and target == "builtins.print":
                    effect = effect.join(
                        Effects(may_fail=True, io=True, global_state=True, costs=frozenset({"format_output"}))
                    )
                elif call.operation == "call" and target.removeprefix("builtins.") in BUILTINS:
                    effect = effect.join(Effects(may_fail=True, costs=frozenset({"type_dependent_builtin"})))
                else:
                    missing.add(symbols.get(target, target))
                    effect = effect.join(UNKNOWN)
            direct[function.function] = effect
            calls[function.function] = callees
            unknown[function.function] = missing
        for name in names:
            pending = list(calls[name])
            visited = set()
            while pending:
                callee = pending.pop()
                if callee == name:
                    direct[name] = direct[name].join(Effects(may_diverge=True, costs=frozenset({"recursion"})))
                    break
                if callee not in visited:
                    visited.add(callee)
                    pending.extend(calls[callee])
        effects = direct.copy()
        changed = True
        while changed:
            changed = False
            for name in sorted(names):
                combined = direct[name]
                for callee in sorted(calls[name]):
                    combined = combined.join(effects[callee])
                if effects[name] != combined:
                    effects[name] = combined
                    changed = True
        return {
            symbols[function.function]: FunctionSummary(
                symbols[function.function],
                function.source.path,
                function.source.line,
                function.parameters_may_write,
                frozenset(symbols[callee] for callee in calls[function.function]),
                frozenset(unknown[function.function]),
                effects[function.function],
            )
            for function in self.functions
        }


def analyze_function(function: ir.Function) -> FunctionEffects:
    effect = Effects()
    calls = []

    def expression(value: ir.Expression) -> None:
        nonlocal effect
        if value.operation in {"binary", "unary", "index", "slice"}:
            effect = effect.join(Effects(may_fail=True))
        if value.operation in CALLS:
            calls.append(value)
        for operand in value.operands:
            expression(operand)
        return  # noqa: PLR1711

    for item in statements(function.body):
        if item.operation in {"assert", "raise", "reraise", "store_index", "delete_index"}:
            effect = effect.join(Effects(may_fail=True))
        if item.operation in {"for", "while"}:
            effect = effect.join(Effects(may_diverge=True, costs=frozenset({"loop"})))
        if item.operation == "resource_scope":
            effect = effect.join(UNKNOWN.join(Effects(costs=frozenset({"resource_cleanup"}))))
        for value in item.expressions:
            expression(value)
    return FunctionEffects(
        function.name,
        function.source,
        frozenset(write_reasons(function, {p.name for p in function.parameters})),
        effect,
        tuple(calls),
    )


def analyze(modules: tuple[ir.Module, ...]) -> EffectPlan:
    return EffectPlan(tuple(analyze_function(function) for module in modules for function in module.functions))
