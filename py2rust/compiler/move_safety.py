"""Move-safety policy: preserve resource lifetimes and backing allocations."""

from dataclasses import dataclass

from . import ir

SCALARS = frozenset({"str", "bytes", "bytearray", "Json", "int", "float", "bool", "None"})
CONTAINERS = frozenset({"list", "dict", "set", "tuple", "tuple_var"})


@dataclass(frozen=True)
class MoveSafetyPlan:
    records: tuple[tuple[str, bool], ...]
    enums: frozenset[str]

    def permits(self, typ: ir.ValueType) -> bool:
        name = typ.name.removeprefix("builtins.").removeprefix("py2rust.stdlib.")
        if name in SCALARS or typ.name in self.enums:
            return True
        if name in CONTAINERS:
            return all(self.permits(argument) for argument in typ.arguments)
        return dict(self.records).get(typ.name, False)


def analyze(modules: tuple[ir.Module, ...]) -> MoveSafetyPlan:
    """Reject resource-bearing records transitively, including recursive graphs.

    Start with record cycles permitted, then remove records containing a resource
    or unknown representation until stable. Resource-free recursive values may
    move; a resource anywhere in a reachable cycle prohibits moving the record.
    """
    records = {record.name: record for module in modules for record in module.records}
    enums = frozenset(enum.name for module in modules for enum in module.enums)
    movable = {name: True for name in records}
    while True:
        plan = MoveSafetyPlan(tuple(movable.items()), enums)
        updated = {name: all(plan.permits(field.type) for field in record.fields) for name, record in records.items()}
        if updated == movable:
            return plan
        movable = updated


@dataclass(frozen=True)
class MoveContext:
    local: bool
    last_use: bool
    borrowed: bool
    is_view: bool
    backs_view: bool
    type_safe: bool


def can_transfer(context: MoveContext) -> bool:
    return (
        context.local
        and context.last_use
        and context.type_safe
        and not context.borrowed
        and not context.is_view
        and not context.backs_view
    )


@dataclass(frozen=True)
class OwnedBoundaryDecision:
    mode: str
    reason: str


def owned_boundary(
    context: MoveContext, type_name: str, copy_reason: str | None = None
) -> OwnedBoundaryDecision | None:
    """Explain a committed owned use using the same eligibility rule as emission.

    Borrowed inputs materialize even when their type contains resources. For
    owned inputs, resource lifetime takes precedence over backing-storage and
    liveness explanations. Scalar/handle ABIs without an owned copy are omitted.
    """
    if type_name in {"int", "float", "bool", "None", "HttpServer"}:
        return None
    if can_transfer(context):
        return OwnedBoundaryDecision("move", "last_use_on_all_successors")
    if context.borrowed or context.is_view:
        return OwnedBoundaryDecision("materialize", "borrowed_value_requires_owned_result")
    if not context.type_safe:
        return OwnedBoundaryDecision("copy", "preserve_resource_lifetime_or_unreviewed_type")
    if context.backs_view:
        return OwnedBoundaryDecision("copy", "retain_view_backing_storage")
    return OwnedBoundaryDecision("copy", copy_reason or "ownership_transfer_not_proven")
