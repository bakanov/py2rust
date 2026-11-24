"""Translate analyzed mypy nodes to compiler-owned IR, rejecting unhandled nodes.

This adapter is being expanded before replacing the legacy production emitter.
Never fall back to Any or untyped source for a node whose lowering is missing.
"""

from __future__ import annotations

import codecs
from typing import NoReturn

from mypy import nodes as n
from mypy import types as t

from .. import ir
from ..exception_policy import RESOURCE_TYPES
from ..libraries import BUILTIN_STATIC, CONSTANTS, INTRINSICS, METHODS, resolve
from ..libraries.web import FIELDS
from ..rules.conditions import condition_problem
from .mypy import FrontendError, TypedModule, TypedProgram


def value_type(typ: t.Type | None) -> ir.ValueType:
    proper = t.get_proper_type(typ)
    if isinstance(proper, t.CallableType):
        return ir.ValueType(
            "callable", tuple(value_type(arg) for arg in proper.arg_types) + (value_type(proper.ret_type),)
        )
    if isinstance(proper, t.NoneType):
        return ir.ValueType("None")
    if isinstance(proper, t.Instance):
        name = proper.type.fullname
        return ir.ValueType(name, tuple(value_type(arg) for arg in proper.args))
    if isinstance(proper, t.TupleType):
        return ir.ValueType("tuple", tuple(value_type(item) for item in proper.items))
    if isinstance(proper, t.UnionType):
        variants = tuple(dict.fromkeys(value_type(item) for item in proper.items))
        return variants[0] if len(variants) == 1 else ir.ValueType("union", variants)
    if isinstance(proper, t.LiteralType):
        return value_type(proper.fallback)
    raise FrontendError([f"IR requires a concrete supported type, got {proper}"])


class Lowering:
    def __init__(
        self, program: TypedProgram, module: TypedModule, native_functions: frozenset[str] = frozenset()
    ) -> None:
        self.program = program
        self.native_functions = native_functions
        self.module = module
        self.return_type: ir.ValueType | None = None
        self.enums = {
            node.fullname
            for item in program.modules.values()
            for node in item.tree.defs
            if isinstance(node, n.ClassDef) and node.info.is_enum
        }
        self.records = {
            node.fullname
            for item in program.modules.values()
            for node in item.tree.defs
            if isinstance(node, n.ClassDef) and "dataclass" in node.info.metadata
        }
        self.record_fields = {
            node.fullname: [
                (member.lvalues[0].name, member.lvalues[0].node.type)
                for member in node.defs.body
                if isinstance(member, n.AssignmentStmt)
                and len(member.lvalues) == 1
                and isinstance(member.lvalues[0], n.NameExpr)
                and isinstance(member.lvalues[0].node, n.Var)
            ]
            for item in program.modules.values()
            for node in item.tree.defs
            if isinstance(node, n.ClassDef) and node.fullname in self.records
        }
        self.functions = {
            node.fullname for item in program.modules.values() for node in item.tree.defs if isinstance(node, n.FuncDef)
        }

    def source(self, node: n.Node) -> ir.Source:
        return ir.Source(self.module.path, node.line, node.column)

    def reject(self, node: n.Node, message: str) -> NoReturn:
        raise FrontendError([f"{self.module.path}:{node.line}: {message}"])

    def json_argument(self, node: n.Expression) -> ir.Expression:
        value = self.expression(node, json_context=True)
        if value.type == ir.ValueType("py2rust.stdlib.Json"):
            return value
        return ir.Expression("json_coerce", ir.ValueType("py2rust.stdlib.Json"), value.source, (value,))

    def condition(self, node: n.Expression) -> ir.Expression:
        expression = self.expression(node)
        problem = condition_problem(expression.type.name)
        if problem:
            self.reject(node, problem)
        return expression

    def expression(
        self, node: n.Expression, *, json_context: bool = False, expected: ir.ValueType | None = None
    ) -> ir.Expression:
        if (
            isinstance(node, n.RefExpr)
            and node.fullname in CONSTANTS
            and node.fullname.rpartition(".")[0] not in self.program.modules
        ):
            return ir.Expression(
                "literal", ir.ValueType("builtins.int"), self.source(node), value=CONSTANTS[node.fullname]
            )
        if isinstance(node, n.MemberExpr) and isinstance(node.expr, n.RefExpr) and node.expr.fullname in self.enums:
            return ir.Expression(
                "enum_member",
                ir.ValueType(node.expr.fullname),
                self.source(node),
                value=node.expr.fullname + "." + node.name,
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
        inferred = self.program.expression_types.get(node)
        if (
            inferred is None
            and isinstance(node, n.NameExpr)
            and isinstance(node.node, n.Var)
            and not node.node.is_inferred
        ):
            inferred = node.node.type
        if inferred is None and expected is not None:
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
        # Mypy omits expression types in unreachable tails. Scalar literals have
        # an intrinsic type and can remain in readable output without guessing.
        literal_types = {
            n.IntExpr: "builtins.int",
            n.FloatExpr: "builtins.float",
            n.StrExpr: "builtins.str",
            n.BytesExpr: "builtins.bytes",
        }
        if inferred is None and not json_literal and type(node) not in literal_types:
            self.reject(node, f"mypy did not infer a type for {type(node).__name__}")
        typ = (
            ir.ValueType("py2rust.stdlib.Json")
            if json_literal
            else (
                ir.ValueType(literal_types[type(node)])
                if inferred is None and type(node) in literal_types
                else value_type(inferred)
            )
        )
        source = self.source(node)
        if isinstance(node, (n.IntExpr, n.FloatExpr, n.StrExpr)):
            return ir.Expression("literal", typ, source, value=node.value)
        if isinstance(node, n.BytesExpr):
            return ir.Expression("literal", typ, source, value=codecs.escape_decode(node.value.encode("ascii"))[0])
        if isinstance(node, n.NameExpr):
            if node.fullname in {"builtins.True", "builtins.False", "builtins.None"}:
                value = {"builtins.True": True, "builtins.False": False, "builtins.None": None}[node.fullname]
                return ir.Expression("literal", typ, source, value=value)
            return ir.Expression("name", typ, source, value=node.fullname or node.name)
        if isinstance(node, n.OpExpr):
            return ir.Expression(
                "short_circuit" if node.op in {"and", "or"} else "binary",
                typ,
                source,
                (
                    (self.condition(node.left), self.condition(node.right))
                    if node.op in {"and", "or"}
                    else (self.expression(node.left), self.expression(node.right))
                ),
                node.op,
            )
        if isinstance(node, n.UnaryExpr):
            operand = self.condition(node.expr) if node.op == "not" else self.expression(node.expr)
            return ir.Expression("unary", typ, source, (operand,), node.op)
        if isinstance(node, n.ComparisonExpr):
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
                self.reject(node, "IR dictionary unpacking is not supported")
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
            return ir.Expression("index", typ, source, (self.expression(node.base), self.expression(node.index)))
        if isinstance(node, n.MemberExpr):
            if node.fullname in self.functions or (
                isinstance(node.node, n.Var) and node.fullname.rpartition(".")[0] in self.program.modules
            ):
                return ir.Expression("name", typ, source, value=node.fullname)
            receiver = self.expression(node.expr)
            web_field = receiver.type.name.startswith("py2rust.stdlib.") and node.name in FIELDS.get(
                receiver.type.name.rsplit(".", 1)[1], {}
            )
            if (
                not web_field
                and receiver.type.name not in self.records
                and not (receiver.type.name in self.enums and node.name in {"value", "name"})
            ):
                self.reject(node, "IR attribute access requires a supported record")
            return ir.Expression("field", typ, source, (receiver,), node.name)
        if isinstance(node, n.CallExpr):
            if not isinstance(node.callee, (n.NameExpr, n.MemberExpr)):
                self.reject(node, "IR currently requires direct calls")
            symbol = node.callee.fullname
            if symbol in self.records:
                if any(kind not in {n.ARG_POS, n.ARG_NAMED} for kind in node.arg_kinds):
                    self.reject(node, "record constructors do not support argument unpacking")
                fields = self.record_fields[symbol]
                arguments = []
                for index, (argument, label) in enumerate(zip(node.args, node.arg_names)):
                    expected = dict(fields).get(label) if label else fields[index][1]
                    proper = t.get_proper_type(expected)
                    is_json = isinstance(proper, t.Instance) and proper.type.fullname == "py2rust.stdlib.Json"
                    arguments.append(self.json_argument(argument) if is_json else self.expression(argument))
                return ir.Expression(
                    "construct",
                    typ,
                    source,
                    tuple(arguments),
                    symbol,
                    operators=tuple(name or "" for name in node.arg_names),
                )
            if symbol == "builtins.sorted":
                if any(kind not in {n.ARG_POS, n.ARG_NAMED} for kind in node.arg_kinds):
                    self.reject(node, "sorted does not support argument unpacking")
                return ir.Expression(
                    "call",
                    typ,
                    source,
                    tuple(self.expression(arg) for arg in node.args),
                    symbol,
                    operators=tuple(name or "" for name in node.arg_names),
                )
            if any(kind != n.ARG_POS for kind in node.arg_kinds):
                self.reject(node, "IR currently requires positional function calls")
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
                if not symbol:
                    receiver = self.expression(node.callee.expr)
                    method = METHODS.get((receiver.type.name, node.callee.name))
                    if method:
                        if len(node.args) + 1 != len(method.parameters):
                            self.reject(node, f"{method.python_name} requires explicit length and byte order")
                        return ir.Expression(
                            "runtime_call",
                            typ,
                            source,
                            (receiver, *(self.expression(arg) for arg in node.args)),
                            method.runtime_name,
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
            signature = t.get_proper_type(node.callee.node.type) if isinstance(node.callee.node, n.FuncDef) else None
            arguments = []
            for index, argument in enumerate(node.args):
                expected = (
                    t.get_proper_type(signature.arg_types[index])
                    if isinstance(signature, t.CallableType) and index < len(signature.arg_types)
                    else None
                )
                is_json = isinstance(expected, t.Instance) and expected.type.fullname == "py2rust.stdlib.Json"
                arguments.append(self.json_argument(argument) if is_json else self.expression(argument))
            return ir.Expression("call", typ, source, tuple(arguments), node.callee.fullname or node.callee.name)
        self.reject(node, f"IR expression lowering is not implemented for {type(node).__name__}")

    def block(self, block: n.Block) -> tuple[ir.Statement, ...]:
        return tuple(self.statement(node) for node in block.body)

    def statement(self, node: n.Statement) -> ir.Statement:
        source = self.source(node)
        if isinstance(node, n.DelStmt):
            if not isinstance(node.expr, n.IndexExpr):
                self.reject(node, "deletion requires one indexed collection target")
            return ir.Statement(
                "delete_index", source, (self.expression(node.expr.base), self.expression(node.expr.index))
            )
        if isinstance(node, n.ReturnStmt):
            return ir.Statement(
                "return", source, () if node.expr is None else (self.expression(node.expr, expected=self.return_type),)
            )
        if isinstance(node, n.ExpressionStmt):
            return ir.Statement("expression", source, (self.expression(node.expr),))
        if isinstance(node, n.AssignmentStmt):
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
            if len(node.lvalues) != 1 or not isinstance(node.lvalues[0], n.NameExpr):
                self.reject(node, "IR currently requires one named assignment target")
            target = node.lvalues[0]
            if not isinstance(target.node, n.Var):
                self.reject(node, "assignment target must resolve to a variable")
            return ir.Statement(
                "assign",
                source,
                (self.expression(node.rvalue),),
                target=target.fullname or target.name,
                target_type=value_type(target.node.type),
                declaration=node.unanalyzed_type is not None,
            )
        if isinstance(node, n.IfStmt):
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
                if not isinstance(exception, n.NameExpr) or exception.fullname != "builtins.Exception":
                    self.reject(node, "the supported exception handler is except Exception")
                handlers.append(
                    ir.Handler(
                        exception.fullname,
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
            if node.expr is not None or node.from_expr is not None:
                self.reject(node, "only bare re-raising is supported")
            return ir.Statement("reraise", source)
        if isinstance(node, n.WhileStmt):
            return ir.Statement(
                "while",
                source,
                (self.condition(node.expr),),
                (self.block(node.body), self.block(node.else_body) if node.else_body else ()),
            )
        if isinstance(node, n.ForStmt):
            if node.is_async or not isinstance(node.index, n.NameExpr):
                self.reject(node, "IR for loops require a synchronous named target")
            return ir.Statement(
                "for",
                source,
                (self.expression(node.expr),),
                (self.block(node.body), self.block(node.else_body) if node.else_body else ()),
                target=node.index.fullname or node.index.name,
                target_type=value_type(node.inferred_item_type),
            )
        if isinstance(node, (n.BreakStmt, n.ContinueStmt)):
            return ir.Statement("break" if isinstance(node, n.BreakStmt) else "continue", source)
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
        for item in node.defs.body:
            if isinstance(item, n.ExpressionStmt) and isinstance(item.expr, n.StrExpr):
                continue
            if (
                not isinstance(item, n.AssignmentStmt)
                or len(item.lvalues) != 1
                or not isinstance(item.lvalues[0], n.NameExpr)
            ):
                self.reject(item, "IR enums require named literal members")
            if not isinstance(item.rvalue, (n.IntExpr, n.StrExpr)):
                self.reject(item, "IR enum values require string or integer literals")
            value = ir.Expression(
                "literal",
                ir.ValueType("builtins.str" if isinstance(item.rvalue, n.StrExpr) else "builtins.int"),
                self.source(item.rvalue),
                value=item.rvalue.value,
            )
            members.append((item.lvalues[0].name, value))
        return ir.Enum(node.fullname, tuple(members), self.source(node))

    def record(self, node: n.ClassDef) -> ir.Record:
        if node.fullname not in self.records or node.base_type_exprs:
            self.reject(node, "IR records require dataclasses without inheritance")
        if (
            len(node.decorators) != 1
            or not isinstance(node.decorators[0], n.RefExpr)
            or node.decorators[0].fullname != "dataclasses.dataclass"
        ):
            self.reject(node, "IR records require the plain @dataclass decorator")
        fields = []
        for member in node.defs.body:
            symbol = node.info.names.get(getattr(member, "name", ""))
            if symbol is not None and symbol.plugin_generated:
                continue  # mypy's synthetic dataclass methods are not user methods.
            if isinstance(member, n.ExpressionStmt) and isinstance(member.expr, n.StrExpr):
                continue
            if (
                not isinstance(member, n.AssignmentStmt)
                or len(member.lvalues) != 1
                or not isinstance(member.lvalues[0], n.NameExpr)
            ):
                self.reject(member, "IR records support annotated fields only")
            variable = member.lvalues[0].node
            if not isinstance(variable, n.Var) or variable.is_classvar:
                self.reject(member, "IR records require instance fields")
            default = None if isinstance(member.rvalue, n.TempNode) else self.expression(member.rvalue)
            fields.append(ir.Field(variable.name, value_type(variable.type), self.source(member), default))
        return ir.Record(node.fullname, tuple(fields), self.source(node))

    def function(self, node: n.FuncDef) -> ir.Function:
        if node.is_coroutine or node.is_generator:
            self.reject(node, "async and generator functions need explicit IR lowering")
        signature = t.get_proper_type(node.type)
        if not isinstance(signature, t.CallableType):
            self.reject(node, "IR functions require a typed signature")
        if any(argument.kind != n.ARG_POS or argument.initializer is not None for argument in node.arguments):
            self.reject(node, "IR currently requires positional parameters without defaults")
        result = value_type(signature.ret_type)
        self.return_type = result
        body = self.block(node.body)
        self.return_type = None
        return ir.Function(
            node.fullname,
            tuple(
                ir.Parameter(arg.variable.name, value_type(typ))
                for arg, typ in zip(node.arguments, signature.arg_types)
            ),
            result,
            body,
            self.source(node),
        )


def lower(program: TypedProgram, *, native_functions: frozenset[str] = frozenset()) -> tuple[ir.Module, ...]:
    modules = []
    for module in program.modules.values():
        adapter = Lowering(program, module, native_functions)
        functions = []
        records = []
        enums = []
        body = []
        for node in module.tree.defs:
            if isinstance(node, n.ExpressionStmt) and isinstance(node.expr, n.StrExpr):
                continue  # Module documentation has no executable behavior.
            if isinstance(node, (n.Import, n.ImportFrom, n.ImportAll)):
                continue  # References already carry resolved symbol names.
            if isinstance(node, n.ClassDef):
                if node.info.is_enum:
                    enums.append(adapter.enum(node))
                else:
                    records.append(adapter.record(node))
            elif isinstance(node, n.FuncDef):
                functions.append(adapter.function(node))
            else:
                statement = adapter.statement(node)
                body.append(statement)
        modules.append(ir.Module(module.name, tuple(functions), tuple(body), tuple(records), tuple(enums)))
    return tuple(modules)
