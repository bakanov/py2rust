"""Translate analyzed mypy nodes to compiler-owned IR, rejecting unhandled nodes.

This adapter is being expanded before replacing the legacy production emitter.
Never fall back to Any or untyped source for a node whose lowering is missing.
"""

from __future__ import annotations

import codecs
from typing import NoReturn

from mypy import nodes as n
from mypy import types as t
from mypy.traverser import TraverserVisitor

from .. import ir
from ..exception_policy import RESOURCE_TYPES
from ..libraries import BUILTIN_STATIC, CONSTANTS, INTRINSICS, METHODS, resolve
from ..libraries.web import FIELDS
from ..rules.conditions import condition_problem
from .mypy import FrontendError, TypedModule, TypedProgram


def class_method(member: n.Statement) -> n.FuncDef | None:
    if isinstance(member, n.FuncDef):
        return member
    if isinstance(member, n.Decorator):
        return member.func
    return None


def user_class_method(node: n.ClassDef, member: n.Statement) -> n.FuncDef | None:
    method = class_method(member)
    symbol = node.info.names.get(method.name) if method is not None else None
    return method if method is not None and (symbol is None or not symbol.plugin_generated) else None


class FunctionDefinitions(TraverserVisitor):
    def __init__(self) -> None:
        self.nodes: list[n.FuncDef] = []

    def visit_func_def(self, node: n.FuncDef) -> None:
        self.nodes.append(node)
        super().visit_func_def(node)


class CaptureReferences(TraverserVisitor):
    def __init__(self, function: n.FuncDef, known_captures: dict[str, tuple[n.NameExpr, ...]]) -> None:
        self.function = function
        self.known_captures = known_captures
        self.locals = {argument.variable for argument in function.arguments}
        self.references: dict[str, n.NameExpr] = {}

    def visit_assignment_stmt(self, node: n.AssignmentStmt) -> None:
        for lvalue in node.lvalues:
            targets = lvalue.items if isinstance(lvalue, n.TupleExpr) else [lvalue]
            self.locals.update(
                target.node for target in targets if isinstance(target, n.NameExpr) and isinstance(target.node, n.Var)
            )
        super().visit_assignment_stmt(node)

    def visit_for_stmt(self, node: n.ForStmt) -> None:
        targets = node.index.items if isinstance(node.index, n.TupleExpr) else [node.index]
        for target in targets:
            if isinstance(target, n.NameExpr) and isinstance(target.node, n.Var):
                self.locals.add(target.node)
        super().visit_for_stmt(node)

    def visit_try_stmt(self, node: n.TryStmt) -> None:
        self.locals.update(binding.node for binding in node.vars if binding and isinstance(binding.node, n.Var))
        super().visit_try_stmt(node)

    def visit_lambda_expr(self, node: n.LambdaExpr) -> None:
        self.locals.update(argument.variable for argument in node.arguments)
        super().visit_lambda_expr(node)

    def visit_generator_expr(self, node: n.GeneratorExpr) -> None:
        for index in node.indices:
            targets = index.items if isinstance(index, n.TupleExpr) else [index]
            self.locals.update(
                target.node for target in targets if isinstance(target, n.NameExpr) and isinstance(target.node, n.Var)
            )
        super().visit_generator_expr(node)

    def visit_name_expr(self, node: n.NameExpr) -> None:
        if isinstance(node.node, n.FuncDef):
            for name, captures in self.known_captures.items():
                if name.endswith("." + node.node.name):
                    for capture in captures:
                        self.references.setdefault(capture.fullname, capture)
        outer = self.function.fullname.rpartition(".")[0]
        if (
            isinstance(node.node, n.Var)
            and node.node not in self.locals
            and (node.fullname.startswith(outer + ".") or node.fullname == node.name)
        ):
            self.references.setdefault(node.fullname, node)


def binding_pattern(target: n.Expression, *, qualified: bool = False) -> str | None:
    if isinstance(target, n.NameExpr):
        return (target.fullname or target.name) if qualified else target.name
    if isinstance(target, n.TupleExpr):
        parts = [binding_pattern(item, qualified=qualified) for item in target.items]
        if all(part is not None for part in parts):
            return "(" + ", ".join(parts) + ")"
    return None


def integer_constant(node: n.Expression) -> int | None:
    if isinstance(node, n.IntExpr):
        return node.value
    if isinstance(node, n.UnaryExpr) and node.op in {"+", "-"}:
        value = integer_constant(node.expr)
        return None if value is None else value if node.op == "+" else -value
    if isinstance(node, n.OpExpr) and node.op in {"+", "-", "<<", ">>", "|"}:
        left, right = integer_constant(node.left), integer_constant(node.right)
        if left is not None and right is not None:
            return {
                "+": lambda: left + right,
                "-": lambda: left - right,
                "<<": lambda: left << right,
                ">>": lambda: left >> right,
                "|": lambda: left | right,
            }[node.op]()
    return None


def value_type(typ: t.Type | None, seen: frozenset[int] = frozenset()) -> ir.ValueType:
    proper = t.get_proper_type(typ)
    scalar = isinstance(proper, t.Instance) and proper.type.fullname in {
        "builtins.int",
        "builtins.float",
        "builtins.bool",
        "builtins.str",
        "builtins.bytes",
    }
    if id(proper) in seen or len(seen) > 4 and not scalar:
        return ir.ValueType("py2rust.stdlib.Json")
    seen = seen | {id(proper)}
    if isinstance(proper, t.Overloaded):
        results = tuple(dict.fromkeys(value_type(item.ret_type, seen) for item in proper.items))
        return results[0] if len(results) == 1 else ir.ValueType("union", results)
    if isinstance(proper, t.CallableType):
        return ir.ValueType(
            "callable", tuple(value_type(arg, seen) for arg in proper.arg_types) + (value_type(proper.ret_type, seen),)
        )
    if isinstance(proper, t.NoneType):
        return ir.ValueType("None")
    if isinstance(proper, t.Instance):
        name = proper.type.fullname
        if proper.type.is_enum and (proper.type.has_base("enum.IntFlag") or proper.type.has_base("enum.IntEnum")):
            return ir.ValueType("builtins.int")
        if name == "builtins.object":
            return ir.ValueType("py2rust.stdlib.Json")
        if name == "itertools.count":
            return ir.ValueType("builtins.int")
        if name == "random.Random":
            return ir.ValueType("py2rust.stdlib.Random")
        if name == "builtins.frozenset":
            return ir.ValueType("builtins.set", tuple(value_type(arg, seen) for arg in proper.args))
        if name in {"collections.abc.Mapping", "typing.Mapping", "types.MappingProxyType"}:
            return ir.ValueType("builtins.dict", tuple(value_type(arg, seen) for arg in proper.args))
        if name == "collections.defaultdict":
            return ir.ValueType("builtins.dict", tuple(value_type(arg, seen) for arg in proper.args))
        if name == "collections.deque":
            return ir.ValueType("builtins.list", tuple(value_type(arg, seen) for arg in proper.args))
        if name == "collections.Counter":
            return ir.ValueType("builtins.dict", (value_type(proper.args[0], seen), ir.ValueType("builtins.int")))
        if name in {
            "collections.abc.Iterator",
            "collections.abc.Iterable",
            "collections.abc.Sequence",
            "typing.Iterator",
            "typing.Iterable",
            "typing.Sequence",
        }:
            return ir.ValueType("builtins.list", tuple(value_type(arg, seen) for arg in proper.args))
        if name in {"pathlib.Path", "typing.TextIO", "_io.TextIOWrapper"}:
            return ir.ValueType("builtins.str" if name == "pathlib.Path" else "builtins.int")
        return ir.ValueType(name, tuple(value_type(arg, seen) for arg in proper.args))
    if isinstance(proper, t.TupleType):
        return ir.ValueType("tuple", tuple(value_type(item, seen) for item in proper.items))
    if isinstance(proper, t.UnionType):
        variants = tuple(dict.fromkeys(value_type(item, seen) for item in proper.items))
        if len(variants) == 1:
            return variants[0]
        non_none = tuple(variant for variant in variants if variant.name != "None")
        if len(variants) == 2 and len(non_none) == 1:
            return ir.ValueType("optional", non_none)
        return ir.ValueType("union", variants)
    if isinstance(proper, t.TypeVarType):
        return value_type(proper.upper_bound, seen)
    if isinstance(proper, t.LiteralType):
        return value_type(proper.fallback, seen)
    if isinstance(proper, t.AnyType):
        return ir.ValueType("py2rust.stdlib.Json")
    raise FrontendError([f"IR requires a concrete supported type, got {proper}"])


class Lowering:
    def __init__(
        self,
        program: TypedProgram,
        module: TypedModule,
        native_functions: frozenset[str] = frozenset(),
        python_scope: bool = False,
    ) -> None:
        self.program = program
        self.native_functions = native_functions
        self.python_scope = python_scope
        self.module = module
        self.return_type: ir.ValueType | None = None
        enum_nodes = [
            node
            for item in program.modules.values()
            for node in item.tree.defs
            if isinstance(node, n.ClassDef) and node.info.is_enum
        ]
        self.enums = {node.fullname for node in enum_nodes}
        self.int_flags = {
            node.fullname
            for node in enum_nodes
            if node.info.has_base("enum.IntFlag") or node.info.has_base("enum.IntEnum")
        }
        self.enum_members = {}
        for node in enum_nodes:
            if node.fullname not in self.int_flags:
                continue
            next_auto = 1
            for member in node.defs.body:
                if isinstance(member, n.AssignmentStmt) and isinstance(member.lvalues[0], n.NameExpr):
                    automatic = (
                        isinstance(member.rvalue, n.CallExpr)
                        and isinstance(member.rvalue.callee, n.RefExpr)
                        and member.rvalue.callee.fullname == "enum.auto"
                    )
                    value = next_auto if automatic else integer_constant(member.rvalue)
                    if value is None:
                        self.reject(member, "integer enum members require integer constant expressions")
                    self.enum_members[f"{node.fullname}.{member.lvalues[0].name}"] = value
                    next_auto = value + 1
        self.enum_member_names = {
            node.fullname: {
                member.lvalues[0].name
                for member in node.defs.body
                if isinstance(member, n.AssignmentStmt) and isinstance(member.lvalues[0], n.NameExpr)
            }
            for node in enum_nodes
        }
        self.enum_value_types = {}
        for node in enum_nodes:
            values = [
                member.rvalue
                for member in node.defs.body
                if isinstance(member, n.AssignmentStmt) and isinstance(member.rvalue, (n.IntExpr, n.StrExpr))
            ]
            if values and all(isinstance(value, n.IntExpr) for value in values):
                self.enum_value_types[node.fullname] = ir.ValueType("builtins.int")
            elif values and all(isinstance(value, n.StrExpr) for value in values):
                self.enum_value_types[node.fullname] = ir.ValueType("builtins.str")
        classes = [node for item in program.modules.values() for node in item.tree.defs if isinstance(node, n.ClassDef)]
        self.records = {node.fullname for node in classes if not node.info.is_enum}
        self.frozen_records = {
            node.fullname
            for node in classes
            if isinstance(node.info.metadata.get("dataclass"), dict) and node.info.metadata["dataclass"].get("frozen")
        }
        self.record_fields = {
            node.fullname: [
                (name, symbol.node.type)
                for name, symbol in node.info.names.items()
                if isinstance(symbol.node, n.Var) and not symbol.node.is_classvar and not symbol.plugin_generated
            ]
            for node in classes
            if node.fullname in self.records
        }
        for class_node in classes:
            if not class_node.info.is_protocol:
                continue
            properties = self.record_fields.setdefault(class_node.fullname, [])
            for member in class_node.defs.body:
                if (
                    isinstance(member, n.Decorator)
                    and member.func.is_property
                    and isinstance(member.func.type, t.CallableType)
                ):
                    properties.append((member.func.name, member.func.type.ret_type))
        self.function_nodes = {
            node.fullname: node
            for item in program.modules.values()
            for node in item.tree.defs
            if isinstance(node, n.FuncDef)
        } | {
            method.fullname: method
            for node in classes
            for member in node.defs.body
            if (method := user_class_method(node, member)) is not None
        }
        for item in program.modules.values():
            definitions = FunctionDefinitions()
            item.tree.accept(definitions)
            self.function_nodes.update((node.fullname, node) for node in definitions.nodes)
        self.functions = set(self.function_nodes)
        self.captures: dict[str, tuple[n.NameExpr, ...]] = {}
        self.nested_functions: list[ir.Function] = []
        self.function_symbols: dict[n.FuncDef, str] = {}
        self.function_stack: list[str] = []
        self.in_generator = False
        self.properties = {
            member.func.fullname
            for node in classes
            for member in node.defs.body
            if isinstance(member, n.Decorator) and member.func.is_property
        }

    def source(self, node: n.Node) -> ir.Source:
        return ir.Source(self.module.path, node.line, node.column)

    def member_symbol(self, node: n.MemberExpr) -> str:
        if node.fullname:
            return node.fullname
        if isinstance(node.node, n.FuncDef):
            return node.node.fullname
        receiver = t.get_proper_type(self.program.expression_types.get(node.expr))
        if isinstance(receiver, t.LiteralType):
            receiver = t.get_proper_type(receiver.fallback)
        if isinstance(receiver, t.Instance) and receiver.type.fullname in self.records | self.enums:
            return f"{receiver.type.fullname}.{node.name}"
        if isinstance(node.expr, n.RefExpr) and isinstance(node.expr.node, n.TypeInfo):
            candidate = f"{node.expr.node.fullname}.{node.name}"
            if candidate in self.function_nodes:
                return candidate
        if isinstance(node.expr, n.NameExpr) and node.expr.name == "cls" and self.function_stack:
            candidate = f"{self.function_stack[-1].rpartition('.')[0]}.{node.name}"
            if candidate in self.function_nodes:
                return candidate
        return ""

    def function_symbol(self, node: n.FuncDef) -> str:
        if not self.function_stack:
            return node.fullname
        symbol = self.function_symbols.get(node)
        if symbol is None:
            symbol = f"{self.function_stack[-1]}.{node.name}"
            self.function_symbols[node] = symbol
            self.functions.add(symbol)
        return symbol

    def reject(self, node: n.Node, message: str) -> NoReturn:
        raise FrontendError([f"{self.module.path}:{node.line}: {message}"])

    def typed_tuple_target(self, target: n.TupleExpr) -> ir.ValueType:
        try:
            return ir.ValueType("tuple", tuple(value_type(item.node.type) for item in target.items))
        except FrontendError as error:
            self.reject(target, error.diagnostics[0])

    def enum_attribute_type(self, node: n.MemberExpr) -> ir.ValueType | None:
        receiver = t.get_proper_type(self.program.expression_types.get(node.expr))
        if isinstance(receiver, t.LiteralType):
            receiver = t.get_proper_type(receiver.fallback)
        if not isinstance(receiver, t.Instance) or receiver.type.fullname not in self.enums:
            return None
        if node.name == "name":
            return ir.ValueType("builtins.str")
        if node.name == "value":
            return self.enum_value_types.get(receiver.type.fullname)
        return None

    def comprehension(
        self, node: n.GeneratorExpr, source: ir.Source, result_type: ir.ValueType | None = None
    ) -> ir.Expression:
        if any(node.is_async):
            self.reject(node, "comprehensions currently require synchronous targets")
        bindings = []
        for target in node.indices:
            binding = binding_pattern(target)
            if binding is None:
                self.reject(node, "comprehension targets must be names or name tuples")
            bindings.append(binding)
        expected_value = (
            result_type.arguments[0]
            if result_type is not None
            and result_type.name in {"builtins.list", "builtins.set"}
            and result_type.arguments
            else result_type if result_type is not None and result_type.name == "builtins.dict" else None
        )
        value = self.expression(
            node.value if isinstance(node, n.DictionaryComprehension) else node.left_expr,
            expected=expected_value,
        )
        return ir.Expression(
            "comprehend",
            result_type or ir.ValueType("builtins.list", (value.type,)),
            source,
            (
                value,
                *(self.expression(sequence) for sequence in node.sequences),
                *(self.condition(condition) for conditions in node.condlists for condition in conditions),
            ),
            "|".join(bindings),
            (str(len(bindings)), *(str(len(conditions)) for conditions in node.condlists)),
        )

    def json_argument(self, node: n.Expression) -> ir.Expression:
        value = self.expression(node, json_context=True)
        if value.type == ir.ValueType("py2rust.stdlib.Json"):
            return value
        return ir.Expression("json_coerce", ir.ValueType("py2rust.stdlib.Json"), value.source, (value,))

    def condition(self, node: n.Expression) -> ir.Expression:
        expression = self.expression(node)
        if expression.operation == "short_circuit":
            expression = ir.Expression(
                expression.operation,
                ir.ValueType("builtins.bool"),
                expression.source,
                expression.operands,
                expression.value,
                expression.operators,
            )
        problem = condition_problem(expression.type.name)
        if problem and self.python_scope:
            kind = expression.type.name
            if (
                kind in self.records
                or kind in self.enums - self.int_flags
                or (
                    kind == "union"
                    and "None" not in {item.name for item in expression.type.arguments}
                    and all(item.name in self.records | self.enums for item in expression.type.arguments)
                )
            ):
                return ir.Expression("truthy", ir.ValueType("builtins.bool"), expression.source, (expression,))
            if kind in {"builtins.int", "builtins.float"}:
                zero = ir.Expression(
                    "literal",
                    expression.type,
                    expression.source,
                    value=0.0 if kind == "builtins.float" else 0,
                )
                return ir.Expression(
                    "compare_chain",
                    ir.ValueType("builtins.bool"),
                    expression.source,
                    (expression, zero),
                    operators=("!=",),
                )
            if kind in {
                "builtins.str",
                "builtins.bytes",
                "builtins.bytearray",
                "builtins.list",
                "builtins.dict",
                "builtins.set",
                "builtins.tuple",
                "tuple",
            }:
                length = ir.Expression(
                    "call",
                    ir.ValueType("builtins.int"),
                    expression.source,
                    (expression,),
                    "builtins.len",
                )
                zero = ir.Expression("literal", ir.ValueType("builtins.int"), expression.source, value=0)
                return ir.Expression(
                    "compare_chain",
                    ir.ValueType("builtins.bool"),
                    expression.source,
                    (length, zero),
                    operators=("!=",),
                )
            if (
                kind == "optional"
                and expression.type.arguments
                and expression.type.arguments[0].name
                in {
                    "builtins.int",
                    "builtins.float",
                }
            ):
                inner = expression.type.arguments[0]
                zero = ir.Expression(
                    "literal", inner, expression.source, value=0.0 if inner.name == "builtins.float" else 0
                )
                value = ir.Expression("optional_value", inner, expression.source, (expression, zero))
                return ir.Expression(
                    "compare_chain",
                    ir.ValueType("builtins.bool"),
                    expression.source,
                    (value, zero),
                    operators=("!=",),
                )
            if (
                kind == "optional"
                and expression.type.arguments
                and expression.type.arguments[0].name
                in {
                    "builtins.str",
                    "builtins.bytes",
                    "builtins.bytearray",
                    "builtins.list",
                    "builtins.dict",
                    "builtins.set",
                    "builtins.tuple",
                    "tuple",
                }
            ):
                length = ir.Expression("optional_len", ir.ValueType("builtins.int"), expression.source, (expression,))
                zero = ir.Expression("literal", ir.ValueType("builtins.int"), expression.source, value=0)
                return ir.Expression(
                    "compare_chain",
                    ir.ValueType("builtins.bool"),
                    expression.source,
                    (length, zero),
                    operators=("!=",),
                )
            if (
                kind == "optional"
                and expression.type.arguments
                and expression.type.arguments[0].name in self.records | self.enums
                or kind == "union"
                and any(item.name == "None" for item in expression.type.arguments)
                and all(
                    item.name == "None" or item.name in self.records | self.enums for item in expression.type.arguments
                )
            ):
                none = ir.Expression("literal", ir.ValueType("None"), expression.source, value=None)
                return ir.Expression(
                    "compare_chain",
                    ir.ValueType("builtins.bool"),
                    expression.source,
                    (expression, none),
                    operators=("is not",),
                )
        if problem:
            self.reject(node, f"{problem}; got {expression.type}")
        return expression

    def expression(
        self, node: n.Expression, *, json_context: bool = False, expected: ir.ValueType | None = None
    ) -> ir.Expression:
        if (
            isinstance(node, n.RefExpr)
            and node.fullname in CONSTANTS
            and node.fullname.rpartition(".")[0] not in self.program.modules
        ):
            value = CONSTANTS[node.fullname]
            return ir.Expression(
                "literal",
                ir.ValueType("builtins.float" if isinstance(value, float) else "builtins.int"),
                self.source(node),
                value=value,
            )
        if isinstance(node, n.NameExpr) and node.fullname in self.enums:
            prefix = node.fullname + "."
            values = [value for member, value in self.enum_members.items() if member.startswith(prefix)]
            if values:
                return ir.Expression(
                    "int_enum_members",
                    ir.ValueType("builtins.list", (ir.ValueType("builtins.int"),)),
                    self.source(node),
                    value=tuple(values),
                )
        if isinstance(node, n.MemberExpr) and isinstance(node.expr, n.RefExpr) and node.expr.fullname in self.enums:
            member = node.expr.fullname + "." + node.name
            if member in self.enum_members:
                return ir.Expression(
                    "literal", ir.ValueType("builtins.int"), self.source(node), value=self.enum_members[member]
                )
            return ir.Expression(
                "enum_member",
                ir.ValueType(node.expr.fullname),
                self.source(node),
                value=member,
            )
        if isinstance(node, n.MemberExpr):
            receiver = t.get_proper_type(self.program.expression_types.get(node.expr))
            if isinstance(receiver, t.TypeType):
                receiver = t.get_proper_type(receiver.item)
            if (
                isinstance(receiver, t.Instance)
                and receiver.type.fullname in self.enums
                and node.name in self.enum_member_names[receiver.type.fullname]
            ):
                return ir.Expression(
                    "enum_member",
                    ir.ValueType(receiver.type.fullname),
                    self.source(node),
                    value=receiver.type.fullname + "." + node.name,
                )
        if (
            isinstance(node, n.MemberExpr)
            and node.name == "__name__"
            and isinstance(node.expr, n.CallExpr)
            and isinstance(node.expr.callee, n.RefExpr)
            and node.expr.callee.fullname == "builtins.type"
            and len(node.expr.args) == 1
        ):
            value = t.get_proper_type(self.program.expression_types.get(node.expr.args[0]))
            if isinstance(value, t.Instance) and value.type.fullname in self.records:
                return ir.Expression(
                    "literal",
                    ir.ValueType("builtins.str"),
                    self.source(node),
                    value=value.type.name,
                )
            return ir.Expression(
                "class_name",
                ir.ValueType("builtins.str"),
                self.source(node),
                (self.expression(node.expr.args[0]),),
            )
        if node in self.program.json_coercions:
            if (
                not isinstance(node, n.CallExpr)
                or not isinstance(node.callee, n.NameExpr)
                or node.callee.fullname != "py2rust.stdlib._json_coerce"
            ):
                self.reject(node, "JSON coercion must resolve to the runtime Json type")
            return ir.Expression(
                "json_coerce",
                ir.ValueType("py2rust.stdlib.Json"),
                self.source(node),
                (self.expression(node.args[0], json_context=True),),
            )
        if isinstance(node, n.NameExpr) and node.fullname in {"builtins.None", "builtins.True", "builtins.False"}:
            return ir.Expression(
                "literal",
                ir.ValueType("None" if node.fullname == "builtins.None" else "builtins.bool"),
                self.source(node),
                value={"builtins.None": None, "builtins.True": True, "builtins.False": False}[node.fullname],
            )
        json_literal = json_context and isinstance(node, (n.DictExpr, n.ListExpr, n.ConditionalExpr))
        if (
            isinstance(node, n.ComparisonExpr)
            and len(node.operands) == 2
            and isinstance(node.operands[0], n.CallExpr)
            and isinstance(node.operands[0].callee, n.RefExpr)
            and node.operands[0].callee.fullname == "builtins.type"
            and len(node.operands[0].args) == 1
            and isinstance(node.operands[1], (n.NameExpr, n.TupleExpr, n.ListExpr))
            and not isinstance(node.operands[1], n.StrExpr)
            and (
                not isinstance(node.operands[1], (n.TupleExpr, n.ListExpr))
                or all(isinstance(item, n.NameExpr) for item in node.operands[1].items)
            )
        ):
            classes = (
                tuple(item.fullname for item in node.operands[1].items)
                if isinstance(node.operands[1], (n.TupleExpr, n.ListExpr))
                else (node.operands[1].fullname,)
            )
            return ir.Expression(
                "is_type",
                ir.ValueType("builtins.bool"),
                self.source(node),
                (self.expression(node.operands[0].args[0]),),
                "|".join(classes),
                (node.operators[0],),
            )
        inferred = self.program.expression_types.get(node)
        dict_fromkeys = (
            isinstance(node, n.CallExpr) and isinstance(node.callee, n.MemberExpr) and node.callee.name == "fromkeys"
        )
        dict_fromkeys_type = expected
        if dict_fromkeys and (expected is None or expected.name != "builtins.list"):
            source = node.args[0]
            if isinstance(source, n.GeneratorExpr):
                source_hint = ir.ValueType(
                    "builtins.list", (value_type(self.program.expression_types.get(source.left_expr)),)
                )
            else:
                source_hint = value_type(self.program.expression_types.get(source))
            if source_hint.name not in {"builtins.list", "builtins.tuple"} or not source_hint.arguments:
                self.reject(node, "dict.fromkeys requires a typed sequence in this subset")
            dict_fromkeys_type = ir.ValueType("builtins.list", (source_hint.arguments[0],))
        empty_frozenset = (
            isinstance(node, n.CallExpr)
            and isinstance(node.callee, n.RefExpr)
            and node.callee.fullname == "builtins.frozenset"
            and not node.args
            and expected is not None
            and expected.name == "builtins.set"
        )
        empty_set_union = (
            isinstance(node, n.CallExpr)
            and isinstance(node.callee, n.MemberExpr)
            and node.callee.name == "union"
            and isinstance(node.callee.expr, n.CallExpr)
            and not node.callee.expr.args
            and bool(node.args)
        )
        empty_union_type = None
        if empty_set_union:
            first = node.args[0]
            if isinstance(first, n.StarExpr):
                first = first.expr
            element = self.program.expression_types.get(
                first.left_expr if isinstance(first, n.GeneratorExpr) else first
            )
            element_type = value_type(element)
            if (
                element_type.name in {"builtins.list", "builtins.set", "builtins.tuple", "tuple_var"}
                and element_type.arguments
            ):
                element_type = element_type.arguments[0]
            empty_union_type = ir.ValueType("builtins.set", (element_type,))
        string_format_call = (
            isinstance(node, n.CallExpr) and isinstance(node.callee, n.MemberExpr) and node.callee.name == "format"
        )
        path_join_call = (
            isinstance(node, n.OpExpr)
            and node.op == "/"
            and (
                isinstance(inferred, t.Instance)
                and inferred.type.fullname in {"builtins.str", "pathlib.Path"}
                or expected is not None
                and expected.name == "builtins.str"
            )
        )
        float_pack_call = (
            isinstance(node, n.CallExpr)
            and isinstance(node.callee, n.RefExpr)
            and node.callee.name == "pack"
            and len(node.args) == 2
            and isinstance(node.args[0], n.StrExpr)
            and node.args[0].value == "<f"
        )
        float_unpack_call = (
            isinstance(node, n.CallExpr)
            and isinstance(node.callee, n.RefExpr)
            and node.callee.name == "unpack"
            and len(node.args) == 2
            and isinstance(node.args[0], n.StrExpr)
            and node.args[0].value == "<f"
        )
        float_unpack_index = (
            isinstance(inferred, t.AnyType)
            and isinstance(node, n.IndexExpr)
            and isinstance(node.base, n.CallExpr)
            and isinstance(node.base.callee, n.RefExpr)
            and node.base.callee.name == "unpack"
            and isinstance(node.base.args[0], n.StrExpr)
            and node.base.args[0].value == "<f"
        )
        if (
            inferred is None
            and isinstance(node, n.NameExpr)
            and isinstance(node.node, n.Var)
            and node.node.type is not None
        ):
            inferred = node.node.type
        if expected is not None:
            empty_list = isinstance(node, n.ListExpr) and not node.items and expected.name == "builtins.list"
            empty_dict = isinstance(node, n.DictExpr) and not node.items and expected.name == "builtins.dict"
            if empty_list or empty_dict:
                return ir.Expression("list" if empty_list else "dict", expected, self.source(node))
        if inferred is None and isinstance(node, n.TupleExpr):
            item_types: tuple[ir.ValueType | None, ...] = (None,) * len(node.items)
            if expected is not None and expected.name == "tuple" and len(expected.arguments) == len(node.items):
                item_types = expected.arguments
            elif expected is not None and expected.name == "builtins.tuple" and len(expected.arguments) == 1:
                item_types = expected.arguments * len(node.items)
            operands = tuple(self.expression(item, expected=typ) for item, typ in zip(node.items, item_types))
            return ir.Expression(
                "tuple", ir.ValueType("tuple", tuple(item.type for item in operands)), self.source(node), operands
            )
        if (
            inferred is None
            and isinstance(node, n.CallExpr)
            and isinstance(node.callee, n.RefExpr)
            and node.callee.fullname
            in {
                "builtins.ValueError",
                "builtins.RuntimeError",
                "builtins.TypeError",
                "builtins.AssertionError",
                "builtins.OSError",
            }
        ):
            if len(node.args) != 1:
                self.reject(node, "exception constructors require one message in this subset")
            return self.expression(node.args[0])
        if (
            inferred is None
            and isinstance(node, n.CallExpr)
            and isinstance(node.callee, n.MemberExpr)
            and node.callee.name == "join"
        ):
            return ir.Expression(
                "method_call",
                ir.ValueType("builtins.str"),
                self.source(node),
                (
                    self.expression(node.callee.expr),
                    *(
                        self.expression(
                            argument, expected=ir.ValueType("builtins.list", (ir.ValueType("builtins.str"),))
                        )
                        for argument in node.args
                    ),
                ),
                "join",
            )
        # Mypy omits expression types in unreachable tails. Scalar literals have
        # an intrinsic type and can remain in readable output without guessing.
        literal_types = {
            n.IntExpr: "builtins.int",
            n.FloatExpr: "builtins.float",
            n.StrExpr: "builtins.str",
            n.BytesExpr: "builtins.bytes",
        }
        if (
            inferred is None
            and expected is None
            and not string_format_call
            and not json_literal
            and type(node) not in literal_types
        ):
            self.reject(node, f"mypy did not infer a type for {type(node).__name__}")
        enum_attribute = self.enum_attribute_type(node) if isinstance(node, n.MemberExpr) else None
        try:
            typ = (
                ir.ValueType("builtins.str")
                if path_join_call or string_format_call
                else (
                    expected
                    if (inferred is None or isinstance(inferred, t.AnyType)) and expected is not None
                    else (
                        expected
                        if empty_frozenset
                        else (
                            empty_union_type
                            if empty_set_union
                            else (
                                ir.ValueType("builtins.bytes")
                                if float_pack_call
                                else (
                                    dict_fromkeys_type
                                    if dict_fromkeys
                                    else (
                                        ir.ValueType("tuple", (ir.ValueType("builtins.float"),))
                                        if float_unpack_call
                                        else (
                                            ir.ValueType("builtins.float")
                                            if float_unpack_index
                                            else (
                                                enum_attribute
                                                if enum_attribute is not None
                                                else (
                                                    ir.ValueType("py2rust.stdlib.Json")
                                                    if json_literal
                                                    else (
                                                        ir.ValueType(literal_types[type(node)])
                                                        if inferred is None and type(node) in literal_types
                                                        else value_type(inferred)
                                                    )
                                                )
                                            )
                                        )
                                    )
                                )
                            )
                        )
                    )
                )
            )
        except FrontendError as error:
            self.reject(node, error.diagnostics[0])
        source = self.source(node)
        if (
            isinstance(node, n.CallExpr)
            and isinstance(node.callee, n.RefExpr)
            and node.callee.fullname
            in {
                "struct.pack",
                "struct.unpack",
                "struct.unpack_from",
                "_struct.pack",
                "_struct.unpack",
                "_struct.unpack_from",
            }
            and node.args
            and isinstance(node.args[0], n.StrExpr)
        ):
            codes = node.args[0].value.lstrip("@=<>!")
            integer_format = all(code.isdigit() or code in "bBhHiIqQ" for code in codes)
            if integer_format and node.callee.fullname == "struct.pack":
                return ir.Expression(
                    "pack_ints",
                    ir.ValueType("builtins.bytes"),
                    source,
                    tuple(self.expression(arg) for arg in node.args),
                )
            if integer_format:
                offset = (
                    self.expression(node.args[2])
                    if len(node.args) == 3
                    else ir.Expression("literal", ir.ValueType("builtins.int"), source, value=0)
                )
                return ir.Expression(
                    "unpack_ints", typ, source, (self.expression(node.args[0]), self.expression(node.args[1]), offset)
                )
        if float_pack_call:
            return ir.Expression("pack_float", typ, source, (self.expression(node.args[1]),))
        if (
            isinstance(node, n.CallExpr)
            and isinstance(node.callee, n.RefExpr)
            and node.callee.name == "unpack"
            and len(node.args) == 2
            and isinstance(node.args[0], n.StrExpr)
            and node.args[0].value == "<f"
        ):
            return ir.Expression(
                "unpack_float",
                ir.ValueType("tuple", (ir.ValueType("builtins.float"),)),
                source,
                (self.expression(node.args[1]),),
            )
        if isinstance(node, (n.IntExpr, n.FloatExpr, n.StrExpr)):
            return ir.Expression("literal", typ, source, value=node.value)
        if isinstance(node, n.BytesExpr):
            return ir.Expression("literal", typ, source, value=codecs.escape_decode(node.value.encode("ascii"))[0])
        if isinstance(node, n.NameExpr):
            if node.fullname in {"builtins.True", "builtins.False", "builtins.None"}:
                value = {"builtins.True": True, "builtins.False": False, "builtins.None": None}[node.fullname]
                return ir.Expression("literal", typ, source, value=value)
            symbol = self.function_symbols.get(node.node) if isinstance(node.node, n.FuncDef) else None
            return ir.Expression("name", typ, source, value=symbol or node.fullname or node.name)
        if isinstance(node, n.AssignmentExpr):
            if not isinstance(node.target, n.NameExpr) or not isinstance(node.target.node, n.Var):
                self.reject(node, "assignment expressions require a named variable")
            return ir.Expression(
                "assign_expr",
                typ,
                source,
                (self.expression(node.value, expected=typ),),
                node.target.fullname or node.target.name,
            )
        if isinstance(node, n.OpExpr):
            if path_join_call:
                return ir.Expression(
                    "runtime_call",
                    ir.ValueType("builtins.str"),
                    source,
                    (self.expression(node.left), self.expression(node.right)),
                    "path_join",
                )
            if node.op in {"and", "or"} and typ.name != "builtins.bool" and not self.python_scope:
                self.reject(node, condition_problem(typ.name))
            return ir.Expression(
                "short_circuit" if node.op in {"and", "or"} else "binary",
                typ,
                source,
                (
                    (self.condition(node.left), self.condition(node.right))
                    if node.op in {"and", "or"} and typ.name == "builtins.bool"
                    else (self.expression(node.left), self.expression(node.right))
                ),
                node.op,
            )
        if isinstance(node, n.UnaryExpr):
            operand = self.condition(node.expr) if node.op == "not" else self.expression(node.expr)
            return ir.Expression("unary", typ, source, (operand,), node.op)
        if isinstance(node, n.ComparisonExpr):
            if len(node.operands) == 2 and isinstance(node.operands[1], n.MemberExpr):
                enum_metadata = node.operands[1]
                if (
                    enum_metadata.name == "__members__"
                    and isinstance(enum_metadata.expr, n.RefExpr)
                    and enum_metadata.expr.fullname in self.enums
                    and node.operators[0] in {"in", "not in"}
                ):
                    return ir.Expression(
                        "enum_name_exists",
                        ir.ValueType("builtins.bool"),
                        source,
                        (self.expression(node.operands[0]),),
                        enum_metadata.expr.fullname,
                        (
                            node.operators[0],
                            *(name for name in self.enum_member_names.get(enum_metadata.expr.fullname, {})),
                        ),
                    )
            # A chain evaluates its middle operands once and later operands lazily.
            return ir.Expression(
                "compare_chain",
                typ,
                source,
                tuple(self.expression(item) for item in node.operands),
                operators=tuple(node.operators),
            )
        if isinstance(node, n.ConditionalExpr):
            return ir.Expression(
                "conditional",
                typ,
                source,
                (
                    self.condition(node.cond),
                    self.json_argument(node.if_expr) if json_context else self.expression(node.if_expr),
                    self.json_argument(node.else_expr) if json_context else self.expression(node.else_expr),
                ),
            )
        if isinstance(node, n.DictionaryComprehension):
            result = self.comprehension(node, source, typ)
            key = self.expression(node.key)
            value = self.expression(node.value)
            item = ir.Expression("tuple", ir.ValueType("tuple", (key.type, value.type)), source, (key, value))
            return ir.Expression(
                result.operation,
                result.type,
                result.source,
                (item, *result.operands[1:]),
                result.value,
                result.operators,
            )
        if isinstance(node, (n.ListComprehension, n.SetComprehension)):
            return self.comprehension(node.generator, source, expected or typ)
        if isinstance(node, n.GeneratorExpr):
            return self.comprehension(node, source)
        if isinstance(node, n.SetExpr) and any(isinstance(item, n.StarExpr) for item in node.items):
            parts = []
            ordinary = []
            for item in node.items:
                if isinstance(item, n.StarExpr):
                    if ordinary:
                        parts.append(ir.Expression("set", typ, source, tuple(ordinary)))
                        ordinary = []
                    parts.append(self.expression(item.expr))
                else:
                    ordinary.append(self.expression(item))
            if ordinary:
                parts.append(ir.Expression("set", typ, source, tuple(ordinary)))
            return ir.Expression("set_union", typ, source, tuple(parts))
        if isinstance(node, (n.ListExpr, n.TupleExpr)) and any(isinstance(item, n.StarExpr) for item in node.items):
            if json_literal:
                self.reject(node, "JSON array unpacking is not implemented")
            if isinstance(node, n.TupleExpr):
                starred = next(item for item in node.items if isinstance(item, n.StarExpr))
                source_type = self.expression(starred.expr).type
                if source_type.name not in {"builtins.list", "builtins.tuple"} or not source_type.arguments:
                    self.reject(starred, "tuple unpacking requires a typed list or variadic tuple")
                typ = ir.ValueType("builtins.list", (source_type.arguments[0],))
            parts = []
            ordinary = []
            for item in node.items:
                if isinstance(item, n.StarExpr):
                    if ordinary:
                        parts.append(ir.Expression("list", typ, source, tuple(ordinary)))
                        ordinary = []
                    part = self.expression(item.expr)
                    if part.type.name not in {"builtins.list", "builtins.tuple"}:
                        self.reject(item, "unpacking currently requires a typed list or variadic tuple")
                    parts.append(part)
                else:
                    ordinary.append(self.expression(item))
            if ordinary:
                parts.append(ir.Expression("list", typ, source, tuple(ordinary)))
            combined = parts[0]
            for part in parts[1:]:
                combined = ir.Expression("binary", typ, source, (combined, part), "+")
            return combined
        if isinstance(node, (n.ListExpr, n.SetExpr, n.TupleExpr)):
            operation = {n.ListExpr: "list", n.SetExpr: "set", n.TupleExpr: "tuple"}[type(node)]
            return ir.Expression(
                "json_array_literal" if json_literal else operation,
                typ,
                source,
                tuple(self.expression(item, json_context=json_context) for item in node.items),
            )
        if isinstance(node, n.DictExpr):
            if any(key is None for key, _ in node.items):
                parts = []
                ordinary = []
                for key, value in node.items:
                    if key is None:
                        if ordinary:
                            parts.append(ir.Expression("dict", typ, source, tuple(ordinary)))
                            ordinary = []
                        parts.append(self.expression(value))
                    else:
                        ordinary.extend((self.expression(key), self.expression(value)))
                if ordinary:
                    parts.append(ir.Expression("dict", typ, source, tuple(ordinary)))
                return ir.Expression("dict_merge", typ, source, tuple(parts))
            return ir.Expression(
                "json_object" if json_literal else "dict",
                typ,
                source,
                tuple(
                    self.expression(item, json_context=json_context and index == 1)
                    for pair in node.items
                    for index, item in enumerate(pair)
                ),
            )
        if isinstance(node, n.IndexExpr):
            enum_base = None
            if isinstance(node.base, n.RefExpr) and node.base.fullname in self.enums:
                enum_base = node.base.fullname
            if (
                isinstance(node.base, n.MemberExpr)
                and node.base.name == "__members__"
                and isinstance(node.base.expr, n.RefExpr)
                and node.base.expr.fullname in self.enums
            ):
                enum_base = node.base.expr.fullname
            if enum_base is not None:
                variants = tuple(
                    f"{name}={value}" for name, value in self.enum_members.items() if name.startswith(enum_base + ".")
                )
                return ir.Expression("enum_from_name", typ, source, (self.expression(node.index),), enum_base, variants)
            if isinstance(node.index, n.SliceExpr):
                bounds = [
                    (name, value)
                    for name, value in (
                        ("start", node.index.begin_index),
                        ("stop", node.index.end_index),
                        ("step", node.index.stride),
                    )
                    if value is not None
                ]
                return ir.Expression(
                    "slice",
                    typ,
                    source,
                    (self.expression(node.base), *(self.expression(value) for _, value in bounds)),
                    operators=tuple(name for name, _ in bounds),
                )
            if isinstance(node.base, n.RefExpr) and node.base.fullname in self.enums:
                variants = tuple(
                    f"{name}={value}"
                    for name, value in self.enum_members.items()
                    if name.startswith(node.base.fullname + ".")
                )
                return ir.Expression(
                    "enum_from_name", typ, source, (self.expression(node.index),), node.base.fullname, variants
                )
            return ir.Expression("index", typ, source, (self.expression(node.base), self.expression(node.index)))
        if isinstance(node, n.MemberExpr):
            member_fullname = self.member_symbol(node)
            if member_fullname in self.properties:
                protocol_receiver = t.get_proper_type(self.program.expression_types.get(node.expr))
                if isinstance(protocol_receiver, t.Instance) and protocol_receiver.type.is_protocol:
                    return ir.Expression("field", typ, source, (self.expression(node.expr),), node.name)
                return ir.Expression("call", typ, source, (self.expression(node.expr),), member_fullname)
            if member_fullname in self.functions or (
                isinstance(node.node, n.Var) and node.fullname.rpartition(".")[0] in self.program.modules
            ):
                return ir.Expression("name", typ, source, value=member_fullname)
            receiver_type = t.get_proper_type(self.program.expression_types.get(node.expr))
            if (
                isinstance(receiver_type, t.TypeType)
                and receiver_type.item.type.fullname in self.enums
                and node.name == "__members__"
            ):
                return ir.Expression("enum_members", typ, source, value=receiver_type.item.type.fullname)
            if (
                isinstance(receiver_type, t.Instance)
                and receiver_type.type.fullname in self.int_flags
                and node.name in {"name", "value"}
            ):
                if node.name == "value":
                    return self.expression(node.expr)
                variants = tuple(
                    f"{name}={value}"
                    for name, value in self.enum_members.items()
                    if name.startswith(receiver_type.type.fullname + ".")
                )
                return ir.Expression(
                    "enum_name",
                    ir.ValueType("builtins.str"),
                    source,
                    (self.expression(node.expr),),
                    receiver_type.type.fullname,
                    variants,
                )
            receiver = self.expression(node.expr)
            if receiver.type.name == "builtins.str" and node.name == "parent":
                return ir.Expression("runtime_call", typ, source, (receiver,), "path_parent")
            if receiver.type.name == "builtins.str" and node.name == "name":
                return ir.Expression("runtime_call", typ, source, (receiver,), "path_name")
            if receiver.type.name == "builtins.str" and node.name == "suffix":
                return ir.Expression("runtime_call", typ, source, (receiver,), "path_suffix")
            if receiver.type.name in self.enums:
                if node.name == "name":
                    typ = ir.ValueType("builtins.str")
                elif node.name == "value" and receiver.type.name in self.enum_value_types:
                    typ = self.enum_value_types[receiver.type.name]
            web_field = receiver.type.name.startswith("py2rust.stdlib.") and node.name in FIELDS.get(
                receiver.type.name.rsplit(".", 1)[1], {}
            )
            if (
                not web_field
                and receiver.type.name not in self.records | {"union"}
                and not (receiver.type.name in self.enums and node.name in {"value", "name"})
            ):
                self.reject(node, "IR attribute access requires a supported record")
            return ir.Expression("field", typ, source, (receiver,), node.name)
        if isinstance(node, n.CallExpr):
            if not isinstance(node.callee, (n.NameExpr, n.MemberExpr)):
                self.reject(node, "IR currently requires direct calls")
            if (
                isinstance(node.callee, n.NameExpr)
                and node.callee.name != "cls"
                and isinstance(node.callee.node, n.Var)
                and node.callee.fullname not in self.functions
                and isinstance(t.get_proper_type(self.program.expression_types.get(node.callee)), t.CallableType)
            ):
                return ir.Expression(
                    "indirect_call",
                    typ,
                    source,
                    (self.expression(node.callee), *(self.expression(argument) for argument in node.args)),
                )
            symbol = self.member_symbol(node.callee) if isinstance(node.callee, n.MemberExpr) else node.callee.fullname
            if isinstance(node.callee.node, n.FuncDef):
                symbol = self.function_symbols.get(node.callee.node, symbol)
            if symbol in {
                "builtins.ValueError",
                "builtins.RuntimeError",
                "builtins.TypeError",
                "builtins.AssertionError",
                "builtins.OSError",
            }:
                if len(node.args) > 1 or any(kind != n.ARG_POS for kind in node.arg_kinds):
                    self.reject(node, "exception constructors accept at most one positional string")
                if not node.args:
                    return ir.Expression("literal", ir.ValueType("builtins.str"), source, value="")
                message = self.expression(node.args[0])
                if message.type != ir.ValueType("builtins.str"):
                    self.reject(node, "exception messages must be strings")
                return message
            receiver_type = (
                t.get_proper_type(self.program.expression_types.get(node.callee.expr))
                if isinstance(node.callee, n.MemberExpr)
                else None
            )
            member_function = (
                symbol in self.functions
                and isinstance(receiver_type, t.Instance)
                and receiver_type.type.fullname in self.records
            )
            if symbol == "cls" and self.function_stack:
                enclosing = self.function_stack[-1].rpartition(".")[0]
                if enclosing in self.records:
                    symbol = enclosing
            if symbol == "builtins.isinstance" and len(node.args) == 2:
                class_node = node.args[1]
                if not isinstance(class_node, (n.RefExpr, n.TupleExpr, n.ListExpr)):
                    self.reject(node, "isinstance requires literal classes")
                classes = (
                    tuple(item.fullname for item in class_node.items)
                    if isinstance(class_node, (n.TupleExpr, n.ListExpr))
                    else (class_node.fullname,)
                )
                return ir.Expression(
                    "is_type",
                    ir.ValueType("builtins.bool"),
                    source,
                    (self.expression(node.args[0]),),
                    "|".join(classes),
                    ("is",),
                )
            if symbol == "typing.cast" and len(node.args) == 2:
                return self.expression(node.args[1], expected=typ)
            if symbol == "copy.deepcopy" and len(node.args) == 1:
                return self.expression(node.args[0])
            if symbol == "dataclasses.replace" and node.args and typ.name in self.records:
                if node.arg_kinds[0] != n.ARG_POS or any(kind != n.ARG_NAMED for kind in node.arg_kinds[1:]):
                    self.reject(node, "dataclasses.replace requires a record and named field updates")
                return ir.Expression(
                    "replace",
                    typ,
                    source,
                    tuple(self.expression(argument) for argument in node.args),
                    typ.name,
                    tuple(name or "" for name in node.arg_names[1:]),
                )
            if symbol == "itertools.accumulate" and len(node.args) in {1, 2}:
                if len(node.args) == 2 and node.arg_names[1] != "initial":
                    self.reject(node, "accumulate accepts only the initial keyword")
                return ir.Expression(
                    "accumulate",
                    typ,
                    source,
                    tuple(self.expression(argument) for argument in node.args),
                )
            if symbol == "itertools.count" and not node.args:
                return ir.Expression("literal", ir.ValueType("builtins.int"), source, value=0)
            if symbol == "collections.defaultdict":
                if (
                    len(node.args) == 1
                    and isinstance(node.args[0], n.RefExpr)
                    and node.args[0].fullname in {"builtins.list", "builtins.set"}
                ):
                    operation = "defaultdict_list" if node.args[0].fullname == "builtins.list" else "defaultdict_set"
                    return ir.Expression(operation, typ, source)
                self.reject(node, "defaultdict currently requires the list or set factory")
            if symbol == "collections.deque":
                if not node.args:
                    return ir.Expression("list", typ, source)
                if len(node.args) == 1 and node.arg_kinds == [n.ARG_POS]:
                    return self.expression(node.args[0], expected=typ)
                self.reject(node, "deque requires zero arguments or one iterable")
            if symbol == "collections.Counter":
                if not node.args:
                    return ir.Expression("counter", typ, source)
                if len(node.args) == 1 and node.arg_kinds == [n.ARG_POS]:
                    return ir.Expression("counter", typ, source, (self.expression(node.args[0]),))
                self.reject(node, "Counter requires zero arguments or one iterable")
            if symbol in self.enums - self.int_flags:
                if len(node.args) != 1 or node.arg_kinds != [n.ARG_POS]:
                    self.reject(node, "enum construction requires one member value")
                return ir.Expression("enum_from_value", typ, source, (self.expression(node.args[0]),), symbol)
            if symbol in self.int_flags:
                if len(node.args) != 1 or node.arg_kinds != [n.ARG_POS]:
                    self.reject(node, "integer enum construction requires one integer")
                return self.expression(node.args[0], expected=ir.ValueType("builtins.int"))
            if symbol == "random.Random":
                if len(node.args) > 1 or any(kind != n.ARG_POS for kind in node.arg_kinds):
                    self.reject(node, "Random accepts at most one integer seed")
                arguments = tuple(self.expression(argument) for argument in node.args)
                return ir.Expression(
                    "runtime_call", typ, source, arguments, "random_new" if arguments else "random_default"
                )
            if symbol == "pathlib.Path":
                if len(node.args) != 1 or node.arg_kinds != [n.ARG_POS]:
                    self.reject(node, "Path requires one string or path argument")
                return self.expression(node.args[0], expected=ir.ValueType("builtins.str"))
            if symbol in self.records:
                if any(kind not in {n.ARG_POS, n.ARG_NAMED, n.ARG_STAR} for kind in node.arg_kinds):
                    self.reject(node, "record constructors do not support this argument unpacking")
                fields = self.record_fields[symbol]
                arguments = []
                for index, (argument, label) in enumerate(zip(node.args, node.arg_names)):
                    expected = dict(fields).get(label) if label else fields[index][1]
                    proper = t.get_proper_type(expected)
                    is_json = isinstance(proper, t.Instance) and proper.type.fullname == "py2rust.stdlib.Json"
                    value = argument.expr if isinstance(argument, n.StarExpr) else argument
                    arguments.append(self.json_argument(value) if is_json else self.expression(value))
                return ir.Expression(
                    "construct",
                    typ,
                    source,
                    tuple(arguments),
                    symbol,
                    operators=tuple(
                        "*" if kind == n.ARG_STAR else name or "" for kind, name in zip(node.arg_kinds, node.arg_names)
                    ),
                )
            if symbol == "builtins.sorted":
                if any(kind not in {n.ARG_POS, n.ARG_NAMED} for kind in node.arg_kinds):
                    self.reject(node, "sorted does not support argument unpacking")
                if (
                    len(node.args) in {2, 3}
                    and node.arg_names[1] == "key"
                    and (len(node.args) == 2 or node.arg_names[2] == "reverse")
                    and isinstance(node.args[1], n.LambdaExpr)
                    and len(node.args[1].arguments) == 1
                ):
                    return ir.Expression(
                        "key_sorted",
                        typ,
                        source,
                        (
                            self.expression(node.args[0]),
                            self.expression(node.args[1].expr()),
                            *((self.expression(node.args[2]),) if len(node.args) == 3 else ()),
                        ),
                        node.args[1].arguments[0].variable.name,
                    )
                return ir.Expression(
                    "call",
                    typ,
                    source,
                    tuple(self.expression(arg) for arg in node.args),
                    symbol,
                    operators=tuple(name or "" for name in node.arg_names),
                )
            if symbol == "builtins.next" and len(node.args) == 1 and isinstance(node.args[0], n.NameExpr):
                source_type = t.get_proper_type(self.program.expression_types.get(node.args[0]))
                if isinstance(source_type, t.Instance) and source_type.type.fullname == "itertools.count":
                    return ir.Expression(
                        "next_counter",
                        ir.ValueType("builtins.int"),
                        source,
                        (self.expression(node.args[0]),),
                        node.args[0].fullname or node.args[0].name,
                    )
            if symbol == "builtins.next" and len(node.args) == 2 and isinstance(node.args[0], n.GeneratorExpr):
                generator = node.args[0]
                if (
                    any(generator.is_async)
                    or len(generator.indices) != 1
                    or binding_pattern(generator.indices[0]) is None
                ):
                    self.reject(node, "next currently supports one name or name-tuple generator target")
                sequence = self.expression(generator.sequences[0])
                default = self.expression(node.args[1], expected=typ)
                return ir.Expression(
                    "find",
                    typ,
                    source,
                    (
                        sequence,
                        default,
                        self.expression(generator.left_expr, expected=typ),
                        *(self.condition(condition) for conditions in generator.condlists for condition in conditions),
                    ),
                    binding_pattern(generator.indices[0]),
                )
            if symbol in {"builtins.min", "builtins.max"} and len(node.args) == 2 and node.arg_names[1] == "default":
                return ir.Expression(
                    "key_extreme",
                    typ,
                    source,
                    (
                        self.expression(node.args[0]),
                        ir.Expression("name", typ, source, value="extreme_item"),
                        self.expression(node.args[1], expected=typ),
                    ),
                    "extreme_item",
                    (symbol.rsplit(".", 1)[1],),
                )
            if (
                symbol in {"builtins.min", "builtins.max"}
                and len(node.args) in {2, 3}
                and node.arg_names[1] == "key"
                and (len(node.args) == 2 or node.arg_names[2] == "default")
                and isinstance(node.args[1], n.LambdaExpr)
                and len(node.args[1].arguments) == 1
            ):
                return ir.Expression(
                    "key_extreme",
                    typ,
                    source,
                    (
                        self.expression(node.args[0]),
                        self.expression(node.args[1].expr()),
                        *((self.expression(node.args[2], expected=typ),) if len(node.args) == 3 else ()),
                    ),
                    node.args[1].arguments[0].variable.name,
                    (symbol.rsplit(".", 1)[1],),
                )
            if symbol == "builtins.frozenset" and len(node.args) == 1:
                return ir.Expression("set_union", typ, source, (self.expression(node.args[0]),))
            if empty_frozenset:
                return ir.Expression("set", typ, source)
            if empty_set_union:
                return ir.Expression(
                    "set_union",
                    typ,
                    source,
                    tuple(
                        self.expression(argument.expr if isinstance(argument, n.StarExpr) else argument)
                        for argument in node.args
                    ),
                )
            if dict_fromkeys:
                return ir.Expression("unique_sequence", typ, source, (self.expression(node.args[0]),))
            if symbol == "builtins.zip" and len(node.args) in {2, 3}:
                if node.arg_names[:2] != [None, None] or (len(node.args) == 3 and node.arg_names[2] != "strict"):
                    self.reject(node, "zip requires two iterables and optional strict")
                return ir.Expression(
                    "zip_pairs",
                    typ,
                    source,
                    tuple(self.expression(argument) for argument in node.args),
                )
            if (
                isinstance(node.callee, n.MemberExpr)
                and node.callee.name == "read_text"
                and any(name is not None for name in node.arg_names)
            ):
                if len(node.args) != 1 or node.arg_names[0] != "encoding":
                    self.reject(node, "read_text supports only the encoding keyword")
                receiver = self.expression(node.callee.expr)
                if receiver.type.name != "builtins.str":
                    self.reject(node, "encoded read_text requires a path")
                return ir.Expression(
                    "runtime_call",
                    typ,
                    source,
                    (receiver, self.expression(node.args[0])),
                    "read_text_encoding",
                )
            if (
                isinstance(node.callee, n.MemberExpr)
                and node.callee.name == "decode"
                and any(name is not None for name in node.arg_names)
            ):
                receiver = self.expression(node.callee.expr)
                if receiver.type.name not in {"builtins.bytes", "builtins.bytearray"} or not 1 <= len(node.args) <= 2:
                    self.reject(node, "decode with an error policy requires bytes and encoding")
                if node.arg_names[0] is not None or (len(node.args) == 2 and node.arg_names[1] != "errors"):
                    self.reject(node, "decode requires positional encoding and keyword errors")
                arguments = [receiver, self.expression(node.args[0])]
                arguments.append(
                    self.expression(node.args[1])
                    if len(node.args) == 2
                    else ir.Expression("literal", ir.ValueType("builtins.str"), source, value="strict")
                )
                return ir.Expression("runtime_call", typ, source, tuple(arguments), "decode_bytes")
            if (
                isinstance(node.callee, n.MemberExpr)
                and node.callee.name == "from_bytes"
                and "signed" in node.arg_names
            ):
                if len(node.args) != 3 or node.arg_names[:2] != [None, None] or node.arg_names[2] != "signed":
                    self.reject(node, "int.from_bytes requires bytes, byteorder and signed")
                return ir.Expression(
                    "runtime_call",
                    typ,
                    source,
                    tuple(self.expression(argument) for argument in node.args),
                    "int_from_bytes_signed",
                )
            if isinstance(node.callee, n.MemberExpr) and node.callee.name == "choice" and len(node.args) == 1:
                receiver = self.expression(node.callee.expr)
                if receiver.type == ir.ValueType("py2rust.stdlib.Random"):
                    return ir.Expression(
                        "choice",
                        typ,
                        source,
                        (receiver, self.expression(node.args[0])),
                    )
            if isinstance(node.callee, n.MemberExpr) and node.callee.name in {
                "_sample",
                "next",
                "next_double",
                "next_range",
            }:
                receiver = self.expression(node.callee.expr)
                if receiver.type == ir.ValueType("strategy.random.MapRandom"):
                    return ir.Expression(
                        "map_random",
                        typ,
                        source,
                        (receiver, *(self.expression(argument) for argument in node.args)),
                        node.callee.name,
                    )
            if (
                isinstance(node.callee, n.MemberExpr)
                and node.callee.name == "shuffle"
                and len(node.args) == 1
                and isinstance(node.args[0], n.NameExpr)
            ):
                receiver = self.expression(node.callee.expr)
                if receiver.type in {ir.ValueType("py2rust.stdlib.Random"), ir.ValueType("strategy.random.MapRandom")}:
                    return ir.Expression(
                        "shuffle",
                        ir.ValueType("None"),
                        source,
                        (receiver, self.expression(node.args[0])),
                        node.args[0].fullname or node.args[0].name,
                    )
            if any(kind not in {n.ARG_POS, n.ARG_NAMED, n.ARG_STAR} for kind in node.arg_kinds) or (
                any(kind == n.ARG_NAMED for kind in node.arg_kinds) and symbol not in self.functions
            ):
                self.reject(node, "IR argument unpacking and keywords require a direct user function")
            if isinstance(node.callee, n.MemberExpr) and isinstance(node.callee.expr, n.RefExpr):
                owner = node.callee.expr.node
                if isinstance(owner, n.TypeInfo) and owner.fullname.startswith("builtins."):
                    symbol = f"{owner.fullname}.{node.callee.name}"
            if symbol in INTRINSICS and symbol not in self.functions and symbol not in self.native_functions:
                return ir.Expression(
                    "intrinsic_call", typ, source, tuple(self.expression(arg) for arg in node.args), INTRINSICS[symbol]
                )
            if symbol in BUILTIN_STATIC:
                return ir.Expression("call", typ, source, tuple(self.expression(arg) for arg in node.args), symbol)
            if (
                isinstance(node.callee, n.MemberExpr)
                and not resolve(symbol)
                and symbol not in self.native_functions
                and symbol not in self.functions
            ):
                if not symbol or node.callee.name in {"index", "get"}:
                    receiver = self.expression(node.callee.expr)
                    method = METHODS.get((receiver.type.name, node.callee.name))
                    if method:
                        required = len(method.parameters) - len(method.trailing_defaults)
                        if not required <= len(node.args) + 1 <= len(method.parameters):
                            self.reject(node, f"wrong argument count for {method.python_name}")
                        arguments = [receiver, *(self.expression(arg) for arg in node.args)]
                        arguments.extend(
                            ir.Expression("literal", ir.ValueType("builtins.int"), source, value=value)
                            for value in method.trailing_defaults[len(node.args) + 1 - required :]
                        )
                        if method.runtime_name == "random_randrange" and len(node.args) == 1:
                            arguments = [receiver, arguments[2], arguments[1]]
                        return ir.Expression(
                            "runtime_call",
                            typ,
                            source,
                            tuple(arguments),
                            method.runtime_name,
                        )
                    if (
                        receiver.type.name == "builtins.str"
                        and node.callee.name == "format"
                        and len(node.args) in {1, 2}
                    ):
                        template = node.callee.expr.value if isinstance(node.callee.expr, n.StrExpr) else ""
                        spec = ("!r" if template.startswith("{!r") else "") + (
                            node.args[1].value if len(node.args) == 2 and isinstance(node.args[1], n.StrExpr) else ""
                        )
                        return ir.Expression(
                            "format_value",
                            ir.ValueType("builtins.str"),
                            source,
                            (self.expression(node.args[0]),),
                            spec,
                        )
                    if (
                        receiver.type.name in {"builtins.list", "builtins.tuple", "tuple", "tuple_var"}
                        and node.callee.name == "index"
                    ):
                        if len(node.args) != 1:
                            self.reject(node, "sequence index requires one value")
                        return ir.Expression(
                            "sequence_index",
                            ir.ValueType("builtins.int"),
                            source,
                            (receiver, self.expression(node.args[0])),
                        )
                    if receiver.type.name in {
                        "builtins.str",
                        "builtins.bytes",
                        "builtins.bytearray",
                        "builtins.list",
                        "builtins.dict",
                        "builtins.set",
                    }:
                        return ir.Expression(
                            "method_call",
                            typ,
                            source,
                            (
                                receiver,
                                *(
                                    (
                                        self.json_argument(arg)
                                        if receiver.type
                                        == ir.ValueType("builtins.list", (ir.ValueType("py2rust.stdlib.Json"),))
                                        and node.callee.name == "append"
                                        else self.expression(arg)
                                    )
                                    for arg in node.args
                                ),
                            ),
                            node.callee.name,
                        )
                self.reject(node, f"no library replacement for {symbol or node.callee.name}")
            if symbol in self.native_functions:
                return ir.Expression(
                    "native_call", typ, source, tuple(self.expression(arg) for arg in node.args), symbol
                )
            if symbol in self.records:
                return ir.Expression("construct", typ, source, tuple(self.expression(arg) for arg in node.args), symbol)
            replacement = None if symbol in self.functions else resolve(symbol)
            if replacement:
                required = len(replacement.parameters) - len(replacement.trailing_defaults)
                if not required <= len(node.args) <= len(replacement.parameters):
                    self.reject(
                        node, f"{symbol} requires {len(replacement.parameters)} positional arguments in this subset"
                    )
                arguments = [
                    ir.Expression("literal", ir.ValueType("builtins.int"), source, value=level)
                    for level in replacement.leading_integers
                ]
                for argument, expected in zip(node.args, replacement.parameters):
                    value = self.expression(argument, json_context=expected == "Json")
                    if expected == "Json" and value.type != ir.ValueType("py2rust.stdlib.Json"):
                        value = ir.Expression(
                            "json_coerce", ir.ValueType("py2rust.stdlib.Json"), value.source, (value,)
                        )
                    arguments.append(value)
                for index in range(len(node.args), len(replacement.parameters)):
                    arguments.append(
                        ir.Expression(
                            "literal",
                            ir.ValueType("builtins.int"),
                            source,
                            value=replacement.trailing_defaults[index - required],
                        )
                    )
                return ir.Expression("runtime_call", typ, source, tuple(arguments), replacement.runtime_name)
            if symbol and not symbol.startswith("builtins.") and symbol not in self.functions:
                self.reject(node, f"no library replacement for {symbol}")
            function_node = self.function_nodes.get(symbol)
            member_function = member_function and not (function_node is not None and function_node.is_static)
            signature = t.get_proper_type(
                function_node.type if function_node is not None else self.program.expression_types.get(node.callee)
            )
            captures = self.captures.get(symbol, ())
            arguments = [self.expression(node.callee.expr)] if member_function else []
            arguments.extend(self.expression(capture) for capture in captures)
            offset = (1 if member_function and function_node is not None else 0) + len(captures)
            for index, argument in enumerate(node.args):
                expected_index = index + offset
                expected = (
                    t.get_proper_type(signature.arg_types[expected_index])
                    if isinstance(signature, t.CallableType) and expected_index < len(signature.arg_types)
                    else None
                )
                is_json = isinstance(expected, t.Instance) and expected.type.fullname == "py2rust.stdlib.Json"
                value = argument.expr if isinstance(argument, n.StarExpr) else argument
                arguments.append(self.json_argument(value) if is_json else self.expression(value))
            return ir.Expression(
                "call",
                typ,
                source,
                tuple(arguments),
                symbol or node.callee.name,
                operators=(
                    *("" for _ in range((1 if member_function else 0) + len(captures))),
                    *("*" if kind == n.ARG_STAR else name or "" for kind, name in zip(node.arg_kinds, node.arg_names)),
                ),
            )
        self.reject(node, f"IR expression lowering is not implemented for {type(node).__name__}")

    def block(self, block: n.Block) -> tuple[ir.Statement, ...]:
        return tuple(self.statement(node) for node in block.body)

    def statement(self, node: n.Statement) -> ir.Statement:
        source = self.source(node)
        if isinstance(node, (n.Import, n.ImportFrom, n.ImportAll, n.TypeAliasStmt)):
            return ir.Statement("pass", source)
        if isinstance(node, n.DelStmt):
            if not isinstance(node.expr, n.IndexExpr):
                self.reject(node, "deletion requires one indexed collection target")
            if isinstance(node.expr.index, n.SliceExpr):
                if node.expr.index.stride is not None:
                    self.reject(node, "slice deletion does not support a step")
                bounds = tuple(
                    self.expression(bound) if bound is not None else None
                    for bound in (node.expr.index.begin_index, node.expr.index.end_index)
                )
                return ir.Statement(
                    "delete_slice",
                    source,
                    (self.expression(node.expr.base), *(bound for bound in bounds if bound is not None)),
                    target=",".join(name for name, bound in zip(("start", "stop"), bounds) if bound is not None),
                )
            return ir.Statement(
                "delete_index", source, (self.expression(node.expr.base), self.expression(node.expr.index))
            )
        if isinstance(node, n.FuncDef):
            self.nested_functions.append(self.function(node))
            return ir.Statement("pass", source)
        if isinstance(node, n.ReturnStmt):
            expression = (
                ir.Expression("name", self.return_type, source, value="yield_values")
                if node.expr is None and self.in_generator
                else (
                    None
                    if node.expr is None
                    else (
                        self.condition(node.expr)
                        if self.return_type == ir.ValueType("builtins.bool")
                        else self.expression(node.expr, expected=self.return_type)
                    )
                )
            )
            return ir.Statement("return", source, () if expression is None else (expression,))
        if isinstance(node, n.ExpressionStmt) and isinstance(node.expr, n.YieldExpr):
            values = ir.Expression("name", self.return_type, source, value="yield_values")
            append = ir.Expression(
                "method_call",
                ir.ValueType("None"),
                source,
                (
                    values,
                    self.expression(
                        node.expr.expr,
                        expected=(
                            self.return_type.arguments[0]
                            if self.return_type is not None and self.return_type.arguments
                            else None
                        ),
                    ),
                ),
                "append",
            )
            return ir.Statement("expression", source, (append,))
        if isinstance(node, n.ExpressionStmt):
            return ir.Statement("expression", source, (self.expression(node.expr),))
        if isinstance(node, n.AssignmentStmt):
            if isinstance(node.rvalue, n.TempNode):
                return ir.Statement("pass", source)
            if len(node.lvalues) > 1 and all(
                isinstance(target, n.NameExpr) and isinstance(target.node, n.Var) for target in node.lvalues
            ):
                target_type = value_type(node.lvalues[0].node.type)
                temporary = f"chained_locals_{node.line}_{node.column}"
                initial = ir.Statement(
                    "assign",
                    source,
                    (self.expression(node.rvalue, expected=target_type),),
                    target=temporary,
                    target_type=target_type,
                    declaration=True,
                )
                stores = [
                    ir.Statement(
                        "assign",
                        source,
                        (ir.Expression("name", target_type, source, value=temporary),),
                        target=target.fullname or target.name,
                        target_type=target_type,
                        declaration=node.unanalyzed_type is not None,
                    )
                    for target in node.lvalues
                ]
                return ir.Statement("group", source, blocks=((initial, *stores),))
            if len(node.lvalues) > 1 and all(
                isinstance(target, n.MemberExpr) and isinstance(target.expr, n.NameExpr) for target in node.lvalues
            ):
                target_type = value_type(self.program.expression_types.get(node.lvalues[0]))
                temporary = f"chained_fields_{node.line}_{node.column}"
                initial = ir.Statement(
                    "assign",
                    source,
                    (self.expression(node.rvalue, expected=target_type),),
                    target=temporary,
                    target_type=target_type,
                    declaration=True,
                )
                stores = [
                    ir.Statement(
                        "store_field",
                        source,
                        (
                            ir.Expression("name", target_type, source, value=temporary),
                            self.expression(target.expr),
                        ),
                        target=target.name,
                    )
                    for target in node.lvalues
                ]
                return ir.Statement("group", source, blocks=((initial, *stores),))
            if len(node.lvalues) == 1 and isinstance(node.lvalues[0], n.MemberExpr):
                target = node.lvalues[0]
                receiver = self.expression(target.expr)
                if receiver.type.name not in self.records:
                    self.reject(node, "field assignment requires a supported record")
                field_type = value_type(target.def_var.type) if target.def_var else None
                value = (
                    self.json_argument(node.rvalue)
                    if field_type == ir.ValueType("py2rust.stdlib.Json")
                    else self.expression(node.rvalue)
                )
                return ir.Statement("store_field", source, (value, receiver), target=target.name)
            if len(node.lvalues) == 1 and isinstance(node.lvalues[0], n.IndexExpr):
                target = node.lvalues[0]
                receiver = self.expression(target.base)
                if isinstance(target.index, n.SliceExpr):
                    if any(
                        bound is not None
                        for bound in (target.index.begin_index, target.index.end_index, target.index.stride)
                    ):
                        self.reject(node, "slice stores currently require a full slice")
                    return ir.Statement(
                        "store_slice", source, (self.expression(node.rvalue, expected=receiver.type), receiver)
                    )
                key = self.expression(target.index)
                is_json = receiver.type == ir.ValueType("py2rust.stdlib.Json") or (
                    receiver.type.name in {"builtins.list", "builtins.dict"}
                    and receiver.type.arguments[-1:] == (ir.ValueType("py2rust.stdlib.Json"),)
                )
                value = self.expression(node.rvalue, json_context=is_json)
                if is_json and value.type != ir.ValueType("py2rust.stdlib.Json"):
                    value = ir.Expression("json_coerce", ir.ValueType("py2rust.stdlib.Json"), value.source, (value,))
                # Assignment evaluates the RHS before resolving the target place.
                return ir.Statement("store_index", source, (value, receiver, key))
            if len(node.lvalues) == 1 and isinstance(node.lvalues[0], n.TupleExpr):
                target = node.lvalues[0]
                if all(isinstance(item, n.IndexExpr) for item in target.items):
                    item_types = []
                    for item in target.items:
                        container = value_type(self.program.expression_types.get(item.base))
                        item_types.append(
                            container.arguments[0] if container.name == "builtins.list" else container.arguments[1]
                        )
                    target_type = ir.ValueType("tuple", tuple(item_types))
                    temporary = f"tuple_indices_{node.line}_{node.column}"
                    initial = ir.Statement(
                        "assign",
                        source,
                        (self.expression(node.rvalue, expected=target_type),),
                        target=temporary,
                        target_type=target_type,
                        declaration=True,
                    )
                    stores = []
                    for index, item in enumerate(target.items):
                        value = ir.Expression(
                            "index",
                            target_type.arguments[index],
                            source,
                            (
                                ir.Expression("name", target_type, source, value=temporary),
                                ir.Expression("literal", ir.ValueType("builtins.int"), source, value=index),
                            ),
                        )
                        stores.append(
                            ir.Statement(
                                "store_index",
                                source,
                                (value, self.expression(item.base), self.expression(item.index)),
                            )
                        )
                    return ir.Statement("group", source, blocks=((initial, *stores),))
                if all(isinstance(item, n.MemberExpr) and isinstance(item.expr, n.NameExpr) for item in target.items):
                    target_type = ir.ValueType(
                        "tuple",
                        tuple(value_type(self.program.expression_types.get(item)) for item in target.items),
                    )
                    temporary = f"tuple_fields_{node.line}_{node.column}"
                    reference = ir.Expression("name", target_type, source, value=temporary)
                    stores = []
                    for index, item in enumerate(target.items):
                        value = ir.Expression(
                            "index",
                            target_type.arguments[index],
                            source,
                            (
                                reference,
                                ir.Expression("literal", ir.ValueType("builtins.int"), source, value=index),
                            ),
                        )
                        stores.append(
                            ir.Statement(
                                "store_field",
                                source,
                                (value, self.expression(item.expr)),
                                target=item.name,
                            )
                        )
                    initial = ir.Statement(
                        "assign",
                        source,
                        (self.expression(node.rvalue, expected=target_type),),
                        target=temporary,
                        target_type=target_type,
                        declaration=True,
                    )
                    return ir.Statement("group", source, blocks=((initial, *stores),))
                if not all(isinstance(item, n.NameExpr) and isinstance(item.node, n.Var) for item in target.items):
                    self.reject(node, "tuple assignment targets must be simple named variables")
                inferred = t.get_proper_type(self.program.expression_types.get(node.rvalue))
                target_type = (
                    value_type(inferred)
                    if isinstance(inferred, t.TupleType) and len(inferred.items) == len(target.items)
                    else self.typed_tuple_target(target)
                )
                return ir.Statement(
                    "unpack_assign",
                    source,
                    (self.expression(node.rvalue, expected=target_type),),
                    target="(" + ", ".join(item.fullname or item.name for item in target.items) + ")",
                    target_type=target_type,
                    declaration=True,
                )
            if len(node.lvalues) != 1 or not isinstance(node.lvalues[0], n.NameExpr):
                self.reject(node, "IR currently requires one named assignment target")
            target = node.lvalues[0]

            def is_type_union(expression: n.Expression) -> bool:
                return (
                    isinstance(expression, n.RefExpr)
                    and isinstance(expression.node, n.TypeInfo)
                    or isinstance(expression, n.IndexExpr)
                    and (
                        is_type_union(expression.base)
                        or isinstance(expression.base, n.RefExpr)
                        and expression.base.fullname == "typing.Literal"
                    )
                    or isinstance(expression, n.OpExpr)
                    and expression.op == "|"
                    and is_type_union(expression.left)
                    and is_type_union(expression.right)
                )

            if (
                (
                    isinstance(node.rvalue, n.CallExpr)
                    and isinstance(node.rvalue.callee, n.RefExpr)
                    and node.rvalue.callee.fullname == "typing.TypeVar"
                )
                or isinstance(target.node, n.TypeAlias)
                or (
                    getattr(node.unanalyzed_type, "name", "") == "TypeAlias"
                    or getattr(node.unanalyzed_type, "fullname", "") == "typing.TypeAlias"
                )
                or (target.node is None and is_type_union(node.rvalue))
            ):
                return ir.Statement("pass", source)
            if not isinstance(target.node, n.Var):
                self.reject(node, "assignment target must resolve to a variable")
            target_type = value_type(target.node.type)
            return ir.Statement(
                "assign",
                source,
                (self.expression(node.rvalue, expected=target_type),),
                target=target.fullname or target.name,
                target_type=target_type,
                declaration=node.unanalyzed_type is not None,
            )
        if isinstance(node, n.IfStmt):
            if (
                len(node.expr) == 1
                and isinstance(node.expr[0], n.NameExpr)
                and node.expr[0].fullname == "typing.TYPE_CHECKING"
            ):
                return ir.Statement("pass", source)
            return ir.Statement(
                "if",
                source,
                tuple(self.condition(expr) for expr in node.expr),
                tuple(self.block(block) for block in node.body)
                + (self.block(node.else_body) if node.else_body else (),),
            )
        if isinstance(node, n.WithStmt):
            if node.is_async or len(node.expr) != 1 or not isinstance(node.target[0], n.NameExpr):
                self.reject(node, "resource scope requires one synchronous named binding")
            resource = self.expression(node.expr[0])
            if resource.type.name not in {f"py2rust.stdlib.{name}" for name in RESOURCE_TYPES}:
                self.reject(node, "context manager has no supported resource cleanup contract")
            return ir.Statement(
                "resource_scope",
                source,
                (resource,),
                (self.block(node.body),),
                target=node.target[0].fullname or node.target[0].name,
                target_type=resource.type,
            )
        if isinstance(node, n.TryStmt):
            if node.is_star:
                self.reject(node, "exception groups are outside the supported subset")
            handlers = []
            for exception, binding, body in zip(node.types, node.vars, node.handlers):
                exceptions = exception.items if isinstance(exception, n.TupleExpr) else (exception,)
                supported = {
                    "builtins.Exception",
                    "builtins.ValueError",
                    "builtins.RuntimeError",
                    "builtins.TypeError",
                    "builtins.AssertionError",
                    "builtins.OSError",
                }
                if any(not isinstance(item, n.NameExpr) or item.fullname not in supported for item in exceptions):
                    self.reject(node, "exception handlers require supported built-in exception classes")
                handlers.append(
                    ir.Handler(
                        "builtins.Exception",
                        (binding.fullname or binding.name) if binding else None,
                        self.block(body),
                        self.source(body),
                    )
                )
            return ir.Statement(
                "try",
                source,
                blocks=(
                    self.block(node.body),
                    self.block(node.else_body) if node.else_body else (),
                    self.block(node.finally_body) if node.finally_body else (),
                ),
                handlers=tuple(handlers),
            )
        if isinstance(node, n.RaiseStmt):
            if node.from_expr is not None:
                self.reject(node, "exception chaining is outside the supported subset")
            if node.expr is not None:
                return ir.Statement("raise", source, (self.expression(node.expr),))
            return ir.Statement("reraise", source)
        if isinstance(node, n.WhileStmt):
            return ir.Statement(
                "while",
                source,
                (self.condition(node.expr),),
                (self.block(node.body), self.block(node.else_body) if node.else_body else ()),
            )
        if isinstance(node, n.ForStmt):
            if node.is_async or not isinstance(node.index, (n.NameExpr, n.TupleExpr)):
                self.reject(node, "IR for loops require a synchronous name or simple name tuple")
            target_type = value_type(node.inferred_item_type)
            if isinstance(node.index, n.NameExpr):
                target = node.index.fullname or node.index.name
                body = self.block(node.body)
            elif binding_pattern(node.index, qualified=True) is not None:
                target = f"for_target_{node.line}_{node.column}"
                unpacked = ir.Statement(
                    "unpack_assign",
                    source,
                    (ir.Expression("name", target_type, source, value=target),),
                    target=binding_pattern(node.index, qualified=True),
                    target_type=target_type,
                    declaration=True,
                )
                body = (unpacked, *self.block(node.body))
            else:
                self.reject(node, "IR tuple loop targets require name tuples")
            return ir.Statement(
                "for",
                source,
                (self.expression(node.expr),),
                (body, self.block(node.else_body) if node.else_body else ()),
                target=target,
                target_type=target_type,
            )
        if isinstance(node, (n.BreakStmt, n.ContinueStmt)):
            return ir.Statement("break" if isinstance(node, n.BreakStmt) else "continue", source)
        if isinstance(node, n.OperatorAssignmentStmt):
            target = node.lvalue
            if isinstance(target, n.NameExpr) and isinstance(target.node, n.Var):
                target_type = value_type(target.node.type)
                value = ir.Expression(
                    "binary",
                    target_type,
                    source,
                    (self.expression(target), self.expression(node.rvalue)),
                    node.op,
                )
                return ir.Statement(
                    "assign",
                    source,
                    (value,),
                    target=target.fullname or target.name,
                    target_type=target_type,
                )
            if isinstance(target, n.MemberExpr):
                target_type = value_type(self.program.expression_types.get(target))
                value = ir.Expression(
                    "binary",
                    target_type,
                    source,
                    (self.expression(target), self.expression(node.rvalue)),
                    node.op,
                )
                return ir.Statement(
                    "store_field",
                    source,
                    (value, self.expression(target.expr)),
                    target=target.name,
                )
            if isinstance(target, n.IndexExpr):
                target_type = value_type(self.program.expression_types.get(target))
                value = ir.Expression(
                    "binary",
                    target_type,
                    source,
                    (self.expression(target), self.expression(node.rvalue)),
                    node.op,
                )
                return ir.Statement(
                    "store_index",
                    source,
                    (value, self.expression(target.base), self.expression(target.index)),
                )
            self.reject(node, "augmented assignment currently requires a named local or simple record field")
        if isinstance(node, n.AssertStmt):
            return ir.Statement(
                "assert",
                source,
                (self.condition(node.expr),) + (() if node.msg is None else (self.expression(node.msg),)),
            )
        if isinstance(node, n.PassStmt):
            return ir.Statement("pass", source)
        self.reject(node, f"IR statement lowering is not implemented for {type(node).__name__}")

    def enum(self, node: n.ClassDef) -> ir.Enum:
        if (
            len(node.base_type_exprs) != 1
            or not isinstance(node.base_type_exprs[0], n.RefExpr)
            or node.base_type_exprs[0].fullname != "enum.Enum"
        ):
            self.reject(node, "IR enums require the plain Enum base")
        members = []
        next_auto = 1
        for item in node.defs.body:
            if class_method(item) is not None:
                continue
            if isinstance(item, n.ExpressionStmt) and isinstance(item.expr, n.StrExpr):
                continue
            if (
                not isinstance(item, n.AssignmentStmt)
                or len(item.lvalues) != 1
                or not isinstance(item.lvalues[0], n.NameExpr)
            ):
                self.reject(item, "IR enums require named literal members")
            automatic = (
                isinstance(item.rvalue, n.CallExpr)
                and isinstance(item.rvalue.callee, n.RefExpr)
                and item.rvalue.callee.fullname == "enum.auto"
            )
            if not isinstance(item.rvalue, (n.IntExpr, n.StrExpr)) and not automatic:
                self.reject(item, "IR enum values require string or integer literals")
            literal = next_auto if automatic else item.rvalue.value
            value = ir.Expression(
                "literal",
                ir.ValueType("builtins.str" if isinstance(item.rvalue, n.StrExpr) else "builtins.int"),
                self.source(item.rvalue),
                value=literal,
            )
            if isinstance(literal, int):
                next_auto = literal + 1
            members.append((item.lvalues[0].name, value))
        return ir.Enum(node.fullname, tuple(members), self.source(node))

    def record(self, node: n.ClassDef) -> ir.Record:
        if node.fullname not in self.records or node.base_type_exprs and not node.info.is_protocol:
            self.reject(node, "IR classes currently require concrete records without inheritance")
        dataclass = "dataclass" in node.info.metadata
        if dataclass:
            if len(node.decorators) != 1:
                self.reject(node, "IR records require one @dataclass decorator")
            decorator = node.decorators[0]
            if isinstance(decorator, n.CallExpr):
                decorator = decorator.callee
            if not isinstance(decorator, n.RefExpr) or decorator.fullname != "dataclasses.dataclass":
                self.reject(node, "IR records require the @dataclass decorator")
        fields = []
        declared = {name for name, _ in self.record_fields[node.fullname]}
        for member in node.defs.body:
            symbol = node.info.names.get(getattr(member, "name", ""))
            if symbol is not None and symbol.plugin_generated:
                continue  # mypy's synthetic dataclass methods are not user methods.
            if class_method(member) is not None or (
                isinstance(member, n.ExpressionStmt) and isinstance(member.expr, n.StrExpr)
            ):
                continue
            if (
                not isinstance(member, n.AssignmentStmt)
                or len(member.lvalues) != 1
                or not isinstance(member.lvalues[0], n.NameExpr)
            ):
                self.reject(member, "IR classes support fields and methods only")
            variable = member.lvalues[0].node
            if not isinstance(variable, n.Var) or variable.is_classvar or variable.name not in declared:
                self.reject(member, "IR records require instance fields")
            factory = None
            if (
                isinstance(member.rvalue, n.CallExpr)
                and self.member_symbol(member.rvalue.callee) == "dataclasses.field"
            ):
                factory = next(
                    (
                        argument
                        for argument, name in zip(member.rvalue.args, member.rvalue.arg_names)
                        if name == "default_factory" and isinstance(argument, n.RefExpr)
                    ),
                    None,
                )
            if factory is not None and factory.fullname in {
                "builtins.list",
                "builtins.dict",
                "builtins.set",
                "collections.Counter",
            }:
                operation = "dict" if factory.fullname == "collections.Counter" else factory.fullname.rsplit(".", 1)[1]
                default = ir.Expression(operation, value_type(variable.type), self.source(member.rvalue))
            elif factory is not None and factory.fullname in self.records:
                default = ir.Expression(
                    "construct", value_type(variable.type), self.source(member.rvalue), value=factory.fullname
                )
            elif factory is not None and factory.fullname in self.functions:
                default = ir.Expression(
                    "call", value_type(variable.type), self.source(member.rvalue), value=factory.fullname
                )
            elif (
                (
                    value_type(variable.type) == ir.ValueType("py2rust.stdlib.Random")
                    and isinstance(member.rvalue, n.CallExpr)
                    and self.member_symbol(member.rvalue.callee) == "dataclasses.field"
                )
                or factory is not None
                and factory.fullname == "random.Random"
            ):
                default = ir.Expression(
                    "runtime_call", value_type(variable.type), self.source(member.rvalue), value="random_default"
                )
            elif (
                isinstance(member.rvalue, n.CallExpr)
                and self.member_symbol(member.rvalue.callee) == "dataclasses.field"
                and "default" in member.rvalue.arg_names
            ):
                default = self.expression(
                    member.rvalue.args[member.rvalue.arg_names.index("default")],
                    expected=value_type(variable.type),
                )
            else:
                default = None if isinstance(member.rvalue, n.TempNode) else self.expression(member.rvalue)
            fields.append(ir.Field(variable.name, value_type(variable.type), self.source(member), default))
        present = {field.name for field in fields}
        fields.extend(
            ir.Field(name, value_type(typ), self.source(node))
            for name, typ in self.record_fields[node.fullname]
            if name not in present
        )
        return ir.Record(node.fullname, tuple(fields), self.source(node))

    def function(self, node: n.FuncDef) -> ir.Function:
        if node.is_coroutine:
            self.reject(node, "async and generator functions need explicit IR lowering")
        signature = t.get_proper_type(node.type)
        if not isinstance(signature, t.CallableType):
            self.reject(node, "IR functions require a typed signature")
        if (
            any(isinstance(typ, t.TypeVarType) for typ in [*signature.arg_types, signature.ret_type])
            and node.fullname != "strategy.random.MapRandom.shuffle"
        ):
            self.reject(node, "general type variables require a concrete signature")
        if any(
            argument.kind not in {n.ARG_POS, n.ARG_OPT, n.ARG_NAMED, n.ARG_NAMED_OPT} for argument in node.arguments
        ):
            self.reject(node, "IR functions currently require positional or named parameters with literal defaults")
        initializers = [argument.initializer for argument in node.arguments if argument.initializer is not None]

        def literal_default(initializer: n.Expression) -> bool:
            if (
                isinstance(initializer, n.CallExpr)
                and not initializer.args
                and isinstance(initializer.callee, n.RefExpr)
                and initializer.callee.fullname in self.frozen_records
            ):
                return True
            if isinstance(initializer, n.NameExpr):
                return initializer.fullname in {"builtins.None", "builtins.True", "builtins.False"} or (
                    initializer.fullname in self.functions
                )
            if isinstance(initializer, n.UnaryExpr):
                return initializer.op in {"+", "-"} and isinstance(initializer.expr, (n.IntExpr, n.FloatExpr))
            return (
                isinstance(initializer, (n.IntExpr, n.FloatExpr, n.StrExpr, n.BytesExpr))
                or (isinstance(initializer, n.TupleExpr) and all(literal_default(item) for item in initializer.items))
                or (
                    isinstance(initializer, n.CallExpr)
                    and isinstance(initializer.callee, n.RefExpr)
                    and initializer.callee.fullname == "builtins.frozenset"
                    and not initializer.args
                )
            )

        if any(not literal_default(initializer) for initializer in initializers):
            self.reject(node, "IR function defaults currently require literal values")
        symbol = self.function_symbol(node)
        captures: tuple[n.NameExpr, ...] = ()
        if self.function_stack:
            references = CaptureReferences(node, self.captures)
            node.body.accept(references)
            captures = tuple(references.references.values())
            self.captures[symbol] = captures
        result = value_type(signature.ret_type)
        previous_return = self.return_type
        previous_generator = self.in_generator
        self.return_type = result
        self.in_generator = node.is_generator
        defaults = tuple(
            self.expression(initializer, expected=value_type(typ))
            for initializer, typ in zip(
                initializers, signature.arg_types[len(signature.arg_types) - len(initializers) :]
            )
        )
        self.function_stack.append(symbol)
        body = self.block(node.body)
        self.function_stack.pop()
        if node.is_generator:
            initial = ir.Statement(
                "assign",
                self.source(node),
                (ir.Expression("list", result, self.source(node)),),
                target="yield_values",
                target_type=result,
                declaration=True,
            )
            returned = ir.Statement(
                "return",
                self.source(node),
                (ir.Expression("name", result, self.source(node), value="yield_values"),),
            )
            body = (initial, *body, returned)
        self.in_generator = previous_generator
        self.return_type = previous_return
        return ir.Function(
            symbol,
            (
                *(ir.Parameter(capture.name, value_type(capture.node.type)) for capture in captures),
                *(
                    ir.Parameter(arg.variable.name, value_type(typ))
                    for arg, typ in zip(node.arguments, signature.arg_types)
                    if node.is_static or not node.is_class or arg is not node.arguments[0]
                ),
            ),
            result,
            body,
            self.source(node),
            defaults,
        )


def lower(
    program: TypedProgram, *, native_functions: frozenset[str] = frozenset(), python_scope: bool = False
) -> tuple[ir.Module, ...]:
    modules = []
    for module in program.modules.values():
        if not python_scope:
            for node in module.tree.defs:
                if isinstance(node, n.FuncDef) and isinstance(node.type, t.CallableType):
                    if any(isinstance(typ, t.AnyType) for typ in [*node.type.arg_types, node.type.ret_type]):
                        raise FrontendError(
                            [f"{module.path}:{node.line}: IR requires a concrete supported type, got Any"]
                        )
        adapter = Lowering(program, module, native_functions, python_scope)
        functions = []
        records = []
        enums = []
        body = []
        for node in module.tree.defs:
            if isinstance(node, n.TypeAliasStmt) and not python_scope:
                adapter.reject(node, "general type variables require a concrete signature")
            if isinstance(node, n.ExpressionStmt) and isinstance(node.expr, n.StrExpr):
                continue  # Module documentation has no executable behavior.
            if isinstance(node, (n.Import, n.ImportFrom, n.ImportAll, n.TypeAliasStmt)):
                continue  # References already carry resolved symbol names.
            if (
                isinstance(node, n.IfStmt)
                and len(node.expr) == 1
                and isinstance(node.expr[0], n.NameExpr)
                and node.expr[0].name == "TYPE_CHECKING"
            ):
                continue  # Static typing branches are never runtime imports.
            if isinstance(node, n.ClassDef):
                if node.info.is_enum:
                    if node.fullname not in adapter.int_flags:
                        enums.append(adapter.enum(node))
                    functions.extend(
                        adapter.function(method)
                        for member in node.defs.body
                        if (method := user_class_method(node, member)) is not None
                    )
                else:
                    records.append(adapter.record(node))
                    if not node.info.is_protocol:
                        functions.extend(
                            adapter.function(method)
                            for member in node.defs.body
                            if (method := user_class_method(node, member)) is not None
                        )
            elif isinstance(node, n.FuncDef):
                if node.name == "__getattr__":
                    continue  # Static imports never invoke Python's dynamic module hook.
                functions.append(adapter.function(node))
            elif isinstance(node, n.AssignmentStmt) and (
                node.is_alias_def
                or isinstance(node.rvalue, n.CallExpr)
                and isinstance(node.rvalue.callee, n.RefExpr)
                and node.rvalue.callee.name == "TypeVar"
            ):
                if not python_scope:
                    adapter.reject(node, "general type variables require a concrete signature")
                continue  # Type aliases and variables have no runtime representation.
            else:
                statement = adapter.statement(node)
                body.append(statement)
        functions.extend(adapter.nested_functions)
        modules.append(ir.Module(module.name, tuple(functions), tuple(body), tuple(records), tuple(enums)))
    return tuple(modules)
