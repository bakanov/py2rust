"""Dependency ordering decisions for compiler-owned project declarations."""

from graphlib import CycleError, TopologicalSorter

from . import ir


def ordered_records(records: tuple[ir.Record, ...]) -> tuple[ir.Record, ...]:
    """Define referenced record types first, preserving independent input order.

    Direct self-reference is handled by the record representation policy. Mutual
    record cycles require representation support beyond the current backend.
    """
    by_name = {record.name: record for record in records}

    def references(typ: ir.ValueType) -> set[str]:
        result = {typ.name} if typ.name in by_name else set()
        for argument in typ.arguments:
            result.update(references(argument))
        return result

    dependencies = {
        record.name: set().union(*(references(field.type) for field in record.fields)) - {record.name}
        for record in records
    }
    # Sort each predecessor set by source order so output is reproducible.
    rank = {record.name: index for index, record in enumerate(records)}
    graph = {name: sorted(required, key=rank.__getitem__) for name, required in dependencies.items()}
    try:
        return tuple(by_name[name] for name in TopologicalSorter(graph).static_order())
    except CycleError as error:
        cycle = error.args[1]
        source = by_name[cycle[0]].source
        raise ValueError(
            f"{source.path}:{source.line}: mutually recursive records are unsupported: {' -> '.join(cycle)}"
        ) from error


def main_guard(statement: ir.Statement) -> bool:
    """Recognize the subset's module entry guard, using resolved IR names."""
    if statement.operation != "if" or len(statement.expressions) != 1 or statement.blocks[-1]:
        return False
    condition = statement.expressions[0]
    if condition.operation != "compare_chain" or condition.operators != ("==",) or len(condition.operands) != 2:
        return False
    left, right = condition.operands
    return (
        left.operation == "name"
        and isinstance(left.value, str)
        and (left.value == "__name__" or left.value.endswith(".__name__"))
        and right.operation == "literal"
        and right.value == "__main__"
    )


def module_layout(module: ir.Module, entry: str) -> tuple[tuple[ir.Statement, ...], tuple[ir.Statement, ...]]:
    """Separate static declarations from entry execution; never execute imported guards."""
    declarations = []
    executable = []
    guards = 0
    for statement in module.body:
        if main_guard(statement):
            guards += 1
            if guards > 1:
                raise ValueError(
                    f"{statement.source.path}:{statement.source.line}: at most one main guard is supported"
                )
            if module.name == entry:
                executable.extend(statement.blocks[0])
        elif statement.operation == "assign" and (statement.declaration or module.name != entry):
            declarations.append(statement)
        elif module.name == entry:
            executable.append(statement)
        else:
            raise ValueError(
                f"{statement.source.path}:{statement.source.line}: imported module initialization requires project lowering"
            )
    return tuple(declarations), tuple(executable)
