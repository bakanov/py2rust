"""Make subset JSON conversions explicit before mypy type checking.

The shared frontend's pre-analysis dependency hook is isolated here. We retain
node locations and record each inserted node; user casts never acquire this
compiler-only conversion behavior.
"""

from mypy import nodes as n
from mypy import types as t
from mypy.plugin import AttributeContext, FunctionSigContext, MethodSigContext, Plugin
from mypy.traverser import TraverserVisitor

from ..libraries import resolve
from .scopes import BlockBindings, SourceNames


class AttributeNullComparisons(TraverserVisitor):
    """Locate comparisons before checking; only a resolved Json field activates them."""

    def __init__(self, comparisons: dict[n.MemberExpr, list[tuple[n.ComparisonExpr, int]]]) -> None:
        self.comparisons = comparisons

    def visit_comparison_expr(self, node: n.ComparisonExpr) -> None:
        for index, operation in enumerate(node.operators):
            if operation not in {"is", "is not"}:
                continue
            for field_index, null_index in ((index, index + 1), (index + 1, index)):
                field, other = node.operands[field_index], node.operands[null_index]
                if isinstance(field, n.MemberExpr) and isinstance(other, n.NameExpr) and other.name == "None":
                    self.comparisons.setdefault(field, []).append((node, null_index))
        super().visit_comparison_expr(node)


class JsonAssignments(TraverserVisitor):
    def __init__(self, aliases: set[str], inserted: set[n.Expression], helper: str) -> None:
        self.aliases = aliases
        self.helper = helper
        self.inserted = inserted
        self.return_type: t.Type | None = None
        self.local_types: dict[str, t.Type] = {}

    def convert(self, expression: n.Expression) -> n.CallExpr:
        conversion = n.CallExpr(n.NameExpr(self.helper), [expression], [n.ARG_POS], [None])
        conversion.set_line(expression)
        self.inserted.add(conversion)
        return conversion

    def visit_func_def(self, node: n.FuncDef) -> None:
        before = self.return_type, self.local_types
        signature = node.unanalyzed_type
        result = signature.ret_type if isinstance(signature, t.CallableType) else None
        self.local_types = (
            {argument.variable.name: typ for argument, typ in zip(node.arguments, signature.arg_types)}
            if isinstance(signature, t.CallableType)
            else {}
        )
        self.return_type = result
        super().visit_func_def(node)
        self.return_type, self.local_types = before

    def convert_result(self, expression: n.Expression, expected: t.Type | None) -> n.Expression:
        if isinstance(expected, t.UnboundType):
            if expected.name in self.aliases:
                return self.convert(expression)
            if (
                expected.name in {"list", "builtins.list"}
                and isinstance(expression, n.ListExpr)
                and len(expected.args) == 1
            ):
                expression.items = [self.convert_result(item, expected.args[0]) for item in expression.items]
            if (
                expected.name in {"dict", "builtins.dict"}
                and isinstance(expression, n.DictExpr)
                and len(expected.args) == 2
            ):
                expression.items = [
                    (key, self.convert_result(value, expected.args[1])) for key, value in expression.items
                ]
            if (
                expected.name in {"tuple", "builtins.tuple"}
                and isinstance(expression, n.TupleExpr)
                and len(expression.items) == len(expected.args)
            ):
                expression.items = [
                    self.convert_result(item, typ) for item, typ in zip(expression.items, expected.args)
                ]
        return expression

    def visit_return_stmt(self, node: n.ReturnStmt) -> None:
        if node.expr is not None:
            node.expr = self.convert_result(node.expr, self.return_type)
        super().visit_return_stmt(node)

    def known_type(self, expression: n.Expression) -> t.Type | None:
        if isinstance(expression, n.NameExpr):
            return self.local_types.get(expression.name)
        if isinstance(expression, n.IndexExpr):
            base = self.known_type(expression.base)
            if isinstance(base, t.UnboundType):
                if base.name in self.aliases:
                    return base
                if base.name in {"list", "builtins.list", "dict", "builtins.dict"} and base.args:
                    return base.args[-1]
                if base.name in {"tuple", "builtins.tuple"} and isinstance(expression.index, n.IntExpr):
                    index = expression.index.value
                    if -len(base.args) <= index < len(base.args):
                        return base.args[index]
        return None

    def known_json(self, expression: n.Expression) -> bool:
        typ = self.known_type(expression)
        return isinstance(typ, t.UnboundType) and typ.name in self.aliases

    def visit_comparison_expr(self, node: n.ComparisonExpr) -> None:
        # Nominal Json can represent null. Comparing it to Python None would
        # otherwise cause mypy to prune a valid branch as statically impossible.
        for index, operation in enumerate(node.operators):
            if operation not in {"is", "is not"}:
                continue
            left, right = node.operands[index : index + 2]
            if self.known_json(left) and isinstance(right, n.NameExpr) and right.name == "None":
                node.operands[index + 1] = self.convert(right)
            elif self.known_json(right) and isinstance(left, n.NameExpr) and left.name == "None":
                node.operands[index] = self.convert(left)
        super().visit_comparison_expr(node)

    def visit_assignment_stmt(self, node: n.AssignmentStmt) -> None:
        typ = node.unanalyzed_type
        targets = [target.name for target in node.lvalues if isinstance(target, n.NameExpr)]
        if typ is not None:
            self.local_types.update({target: typ for target in targets})
        expected = typ or next((self.local_types[target] for target in targets if target in self.local_types), None)
        if not isinstance(node.rvalue, n.TempNode):
            node.rvalue = self.convert_result(node.rvalue, expected)
        super().visit_assignment_stmt(node)


class SubsetCoercions(Plugin):
    def __init__(self, options, modules: set[str]) -> None:
        super().__init__(options)
        self.modules = modules
        self.inserted: set[n.Expression] = set()
        self.visited: set[str] = set()
        self.attribute_comparisons: dict[n.MemberExpr, list[tuple[n.ComparisonExpr, int]]] = {}

    def convert_checked_literal(self, expression: n.Expression, expected: t.Type) -> n.Expression:
        """Insert bound conversion nodes in literal arguments during type checking.

        Signature hooks run after semantic analysis, so helper references must
        already resolve to their compiler-owned symbol. Nonliteral containers
        retain their original types and normal invariance checks.
        """
        if expression in self.inserted:
            return expression
        proper = t.get_proper_type(expected)
        if isinstance(proper, t.Instance):
            if proper.type.fullname == "py2rust.stdlib.Json":
                symbol = self.lookup_fully_qualified("py2rust.stdlib._json_coerce")
                assert symbol is not None
                helper = n.NameExpr("_json_coerce")
                helper.node = symbol.node
                helper.kind = symbol.kind
                helper.fullname = "py2rust.stdlib._json_coerce"
                helper.set_line(expression)
                conversion = n.CallExpr(helper, [expression], [n.ARG_POS], [None])
                conversion.set_line(expression)
                self.inserted.add(conversion)
                return conversion
            if proper.type.fullname == "builtins.list" and isinstance(expression, n.ListExpr):
                expression.items = [self.convert_checked_literal(item, proper.args[0]) for item in expression.items]
            elif proper.type.fullname == "builtins.dict" and isinstance(expression, n.DictExpr):
                expression.items = [
                    (key, self.convert_checked_literal(value, proper.args[1])) for key, value in expression.items
                ]
            elif proper.type.fullname == "builtins.tuple" and isinstance(expression, n.TupleExpr):
                expression.items = [self.convert_checked_literal(item, proper.args[0]) for item in expression.items]
        elif (
            isinstance(proper, t.TupleType)
            and isinstance(expression, n.TupleExpr)
            and len(proper.items) == len(expression.items)
        ):
            expression.items = [
                self.convert_checked_literal(item, typ) for item, typ in zip(expression.items, proper.items)
            ]
        return expression

    def json_call_signature(self, context: FunctionSigContext | MethodSigContext) -> t.CallableType:
        parameters = []
        for index, argument in enumerate(context.default_signature.arg_types):
            proper = t.get_proper_type(argument)
            if not (isinstance(proper, t.Instance) and proper.type.fullname == "py2rust.stdlib.Json"):
                for expression in context.args[index]:
                    self.convert_checked_literal(expression, argument)
            parameters.append(
                context.api.named_generic_type("builtins.object", [])
                if isinstance(proper, t.Instance) and proper.type.fullname == "py2rust.stdlib.Json"
                else argument
            )
        return context.default_signature.copy_modified(arg_types=parameters)

    def get_function_signature_hook(self, fullname: str):
        if resolve(fullname) is not None or any(fullname.startswith(module + ".") for module in self.modules):
            return self.json_call_signature
        return None

    def get_method_signature_hook(self, fullname: str):
        if fullname in {
            "builtins.list.append",
            "builtins.list.insert",
            "builtins.list.__setitem__",
            "builtins.dict.__setitem__",
        }:
            return self.json_call_signature
        return None

    def json_attribute_type(self, context: AttributeContext) -> t.Type:
        proper = t.get_proper_type(context.default_attr_type)
        if isinstance(proper, t.Instance) and proper.type.fullname == "py2rust.stdlib.Json":
            for comparison, index in self.attribute_comparisons.get(context.context, []):
                original = comparison.operands[index]
                if isinstance(original, n.NameExpr) and original.fullname == "builtins.None":
                    converted = self.convert_checked_literal(original, proper)
                    comparison.operands[index] = converted
                    # In `None is record.field`, the left operand was already
                    # visited. Type the replacement before narrowing sees it.
                    context.api.get_expression_type(converted)
        return context.default_attr_type

    def get_attribute_hook(self, fullname: str):
        if any(fullname.startswith(module + ".") for module in self.modules):
            return self.json_attribute_type
        return None

    def get_additional_deps(self, file: n.MypyFile) -> list[tuple[int, str, int]]:
        if file.fullname not in self.modules or file.fullname in self.visited:
            return []
        self.visited.add(file.fullname)
        names = SourceNames()
        file.accept(names)
        file.accept(BlockBindings(names.names))
        file.accept(AttributeNullComparisons(self.attribute_comparisons))
        aliases = set()
        for item in file.imports:
            if isinstance(item, n.ImportFrom) and item.id == "py2rust.stdlib" and item.relative == 0:
                aliases.update(alias or name for name, alias in item.names if name == "Json")
            elif isinstance(item, n.Import):
                aliases.update(f"{alias or name}.Json" for name, alias in item.ids if name == "py2rust.stdlib")
        if aliases:
            helper = "__py2rust_json_coerce"
            imported = n.ImportFrom("py2rust.stdlib", 0, [("_json_coerce", helper)])
            imported.set_line(1)
            file.defs.insert(0, imported)
            file.imports.append(imported)
            file.accept(JsonAssignments(aliases, self.inserted, helper))
        return []
