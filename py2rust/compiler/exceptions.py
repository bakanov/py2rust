"""Legacy AST policy and bridge to prepared compiler-owned exception decisions."""

from __future__ import annotations

import ast
from dataclasses import dataclass


def always_returns(statements: list[ast.stmt]) -> bool:
    """Use prepared IR facts when present; legacy input retains its AST analysis."""
    for statement in statements:
        flow = getattr(statement, "py2rust_flow", None)
        if flow is not None:
            if flow.terminates:
                return True
        elif _always_returns_ast([statement]):
            return True
    return False


def _always_returns_ast(statements: list[ast.stmt]) -> bool:
    for statement in statements:
        if isinstance(statement, (ast.Return, ast.Raise)):
            return True
        if isinstance(statement, ast.With) and always_returns(statement.body):
            return True
        if isinstance(statement, ast.If) and always_returns(statement.body) and always_returns(statement.orelse):
            return True
        if isinstance(statement, ast.Try):
            if always_returns(statement.finalbody):
                return True
            succeeds = always_returns(statement.body) or always_returns(statement.orelse)
            if succeeds and all(always_returns(handler.body) for handler in statement.handlers):
                return True
    return False


@dataclass(frozen=True)
class TryPlan:
    protected: ast.Try
    cleanup: tuple[ast.stmt, ...]
    body_terminates: bool
    cleanup_terminates: bool
    statement_terminates: bool


def invalid_try_jump(statements: list[ast.stmt], loops: int = 0) -> ast.stmt | None:
    """Find a jump that would cross the closure used to preserve pending returns."""
    for statement in statements:
        if isinstance(statement, ast.Try):
            if not statement.finalbody:
                regions = [statement.orelse, *(handler.body for handler in statement.handlers)]
                for region in regions:
                    invalid = invalid_try_jump(region, loops)
                    if invalid is not None:
                        return invalid
            continue
        if isinstance(statement, (ast.Break, ast.Continue)) and loops == 0:
            return statement
        for child in ast.iter_child_nodes(statement):
            if isinstance(child, ast.stmt):
                invalid = invalid_try_jump([child], loops + isinstance(statement, (ast.For, ast.While)))
                if invalid is not None:
                    return invalid
    return None


def plan_try(node: ast.Try) -> TryPlan:
    """Preserve pending errors/returns until cleanup; cleanup can replace either."""
    import copy

    protected = copy.copy(node)
    protected.finalbody = []
    flow = getattr(node, "py2rust_flow", None)
    if flow is not None:
        from .exception_policy import StatementFlow

        completion = flow.protected
        if completion is None:
            raise ValueError("prepared try statement has no exception completion plan")
        protected.py2rust_flow = StatementFlow(completion.body_terminates, completion)
        return TryPlan(
            protected,
            tuple(node.finalbody),
            completion.body_terminates,
            completion.cleanup_terminates,
            completion.statement_terminates,
        )
    return TryPlan(
        protected,
        tuple(node.finalbody),
        always_returns([protected]) if protected.handlers else always_returns(protected.body),
        always_returns(node.finalbody),
        always_returns([node]),
    )
