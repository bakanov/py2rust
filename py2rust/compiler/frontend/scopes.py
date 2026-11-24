"""Preserve the subset's block-local annotated bindings before mypy analysis."""

from mypy import nodes as n
from mypy.traverser import TraverserVisitor


class BlockBindings(TraverserVisitor):
    def __init__(self, used: set[str] | None = None) -> None:
        self.used = set(used or ())
        self.bindings: dict[str, str] = {}
        self.depth = 0
        self.counter = 0
        self.in_function = False

    def fresh_name(self, original: str) -> str:
        base = original.rstrip("'")
        while True:
            self.counter += 1
            candidate = f"{base}__block_{self.counter}"
            if candidate not in self.used and candidate not in self.bindings.values():
                self.used.add(candidate)
                return candidate

    def visit_func_def(self, node: n.FuncDef) -> None:
        before = self.bindings, self.depth, self.in_function
        self.bindings = {arg.variable.name: arg.variable.name for arg in node.arguments}
        self.depth = 0
        self.in_function = True
        super().visit_func_def(node)
        self.bindings, self.depth, self.in_function = before

    def visit_block(self, node: n.Block) -> None:
        before = self.bindings.copy()
        self.depth += 1
        super().visit_block(node)
        self.depth -= 1
        self.bindings = before

    def visit_assignment_stmt(self, node: n.AssignmentStmt) -> None:
        node.rvalue.accept(self)
        if self.in_function:
            for target in node.lvalues:
                if isinstance(target, n.NameExpr) and target.name not in self.bindings:
                    original = target.name
                    if self.depth > 1:
                        candidate = self.fresh_name(original)
                        self.bindings[original] = candidate
                    else:
                        self.bindings[original] = original
        for target in node.lvalues:
            target.accept(self)

    def visit_for_stmt(self, node: n.ForStmt) -> None:
        node.expr.accept(self)
        before = self.bindings.copy()
        if self.in_function and isinstance(node.index, n.NameExpr):
            self.bindings[node.index.name] = self.fresh_name(node.index.name)
        node.index.accept(self)
        node.body.accept(self)
        self.bindings = before
        if node.else_body is not None:
            node.else_body.accept(self)

    def visit_with_stmt(self, node: n.WithStmt) -> None:
        # Resource bindings belong to the with body in the supported subset.
        # Mypy's parser can already produce shadow names such as handle'.
        # Allocate a readable, collision-free identifier for each resource.
        before = self.bindings.copy()
        for expression, target in zip(node.expr, node.target):
            expression.accept(self)
            if isinstance(target, n.NameExpr):
                original = target.name
                candidate = self.fresh_name(original)
                self.bindings[original] = candidate
                target.accept(self)
            elif target is not None:
                target.accept(self)
        node.body.accept(self)
        self.bindings = before

    def visit_name_expr(self, node: n.NameExpr) -> None:
        node.name = self.bindings.get(node.name, node.name)


class SourceNames(TraverserVisitor):
    def __init__(self) -> None:
        self.names: set[str] = set()

    def visit_name_expr(self, node: n.NameExpr) -> None:
        self.names.add(node.name)

    def visit_func_def(self, node: n.FuncDef) -> None:
        self.names.update(arg.variable.name for arg in node.arguments)
        super().visit_func_def(node)
