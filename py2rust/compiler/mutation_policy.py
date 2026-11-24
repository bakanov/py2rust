"""Known collection mutations that can invalidate a selected element.

These are local detachment facts, not a proof of exclusive access or a complete
alias analysis. Unknown calls remain governed by separate effect/ABI policies.
"""

from dataclasses import dataclass

from . import ir
from .parameter_policy import place_root

MUTATING_METHODS = frozenset({"append", "extend", "pop", "remove", "clear", "sort", "reverse", "insert", "add"})
HEAP_MUTATIONS = frozenset(f"heapq.{name}" for name in ("heapify", "heappush", "heappop", "heapreplace", "heappushpop"))


@dataclass(frozen=True)
class CollectionMutation:
    root: str
    source: ir.Source
    reason: str = "collection_element_may_detach_or_reorder"


def direct_mutation(expression: ir.Expression) -> CollectionMutation | None:
    root = None
    if expression.operation == "method_call" and expression.value in MUTATING_METHODS:
        root = place_root(expression.operands[0])
    elif expression.operation == "intrinsic_call" and expression.value in HEAP_MUTATIONS and expression.operands:
        argument = expression.operands[0]
        if argument.operation == "name":
            root = str(argument.value)
    return CollectionMutation(root, expression.source) if root is not None else None
