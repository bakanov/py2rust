"""Bridge typed IR into the existing Rust emitter during its incremental migration.

The original Python source/AST is never consulted. This bridge is temporary: it
lets complete programs exercise the new frontend while preserving the mature
runtime and ownership implementation. It is not the final IR-native backend.
"""

from __future__ import annotations

import ast

from .. import ir
from ..binding_policy import IterationDecision
from ..effect_policy import EffectPlan
from ..efficiency_policy import FunctionEfficiency, StringAppendDecision
from ..exception_policy import StatementFlow
from ..liveness import FunctionLiveness
from ..memory import IterationUse, OwnershipUse
from ..memory_oracle import EvaluationProof
from ..move_safety import MoveSafetyPlan
from ..optimization import StringAppend
from ..parameter_policy import FunctionParameters, ParameterDecision
from ..project_policy import module_layout, ordered_records
from ..rust_imports import symbol_name
from ..view_policy import FunctionViews


class AdapterError(ValueError):
    pass


def locate(node: ast.AST, source: ir.Source) -> ast.AST:
    node.lineno = source.line
    node.col_offset = max(0, source.column)
    node.end_lineno = source.line
    node.end_col_offset = max(0, source.column)
    node.source_path = source.path
    return node


def name(symbol: str) -> str:
    if symbol == "self":
        return "self_"
    if symbol.endswith(".__name__"):
        return "__name__"
    if symbol.startswith("builtins."):
        return symbol.removeprefix("builtins.")
    if "." in symbol:
        module, local = symbol.rsplit(".", 1)
        return symbol_name(module, local)
    return symbol


def annotation(typ: ir.ValueType) -> ast.expr:
    if typ.name.startswith("py2rust.stdlib."):
        return ast.Name(id=typ.name.rsplit(".", 1)[1], ctx=ast.Load())
    if typ.name == "None":
        return ast.Constant(None)
    if typ.name == "optional":
        return ast.Subscript(value=ast.Name(id="Optional", ctx=ast.Load()), slice=annotation(typ.arguments[0]))
    if typ.name == "union":
        return ast.Subscript(
            value=ast.Name(id="Union", ctx=ast.Load()),
            slice=ast.Tuple(elts=[annotation(item) for item in typ.arguments], ctx=ast.Load()),
        )
    if typ.name == "callable":
        return ast.Subscript(
            value=ast.Name(id="Callable", ctx=ast.Load()),
            slice=ast.Tuple(
                elts=[
                    ast.List(elts=[annotation(item) for item in typ.arguments[:-1]], ctx=ast.Load()),
                    annotation(typ.arguments[-1]),
                ],
                ctx=ast.Load(),
            ),
        )
    base = ast.Name(id=name(typ.name), ctx=ast.Load())
    if not typ.arguments:
        return base
    arguments = [annotation(arg) for arg in typ.arguments]
    if typ.name == "builtins.tuple":
        arguments.append(ast.Constant(Ellipsis))
    return ast.Subscript(
        value=base,
        slice=(arguments[0] if len(arguments) == 1 else ast.Tuple(elts=arguments, ctx=ast.Load())),
        ctx=ast.Load(),
    )


BINARY = {
    "+": ast.Add,
    "-": ast.Sub,
    "*": ast.Mult,
    "/": ast.Div,
    "//": ast.FloorDiv,
    "%": ast.Mod,
    "**": ast.Pow,
    "&": ast.BitAnd,
    "|": ast.BitOr,
    "^": ast.BitXor,
    "<<": ast.LShift,
    ">>": ast.RShift,
}
COMPARE = {
    "==": ast.Eq,
    "!=": ast.NotEq,
    "<": ast.Lt,
    "<=": ast.LtE,
    ">": ast.Gt,
    ">=": ast.GtE,
    "is": ast.Is,
    "is not": ast.IsNot,
    "in": ast.In,
    "not in": ast.NotIn,
}


def expression(
    value: ir.Expression,
    evaluation_facts: dict[ir.Expression, EvaluationProof] | None = None,
) -> ast.expr:
    operands = [expression(item, evaluation_facts) for item in value.operands]
    operation = value.operation
    if operation == "json_coerce":
        node = operands[0]
        node.py2rust_json_coercion = True
    elif operation == "literal":
        node = ast.Constant(value=value.value)
    elif operation == "name":
        node = ast.Name(id=name(str(value.value)), ctx=ast.Load())
    elif operation == "method_call":
        node = ast.Call(
            func=ast.Attribute(value=operands[0], attr=str(value.value), ctx=ast.Load()),
            args=operands[1:],
            keywords=[],
        )
    elif operation == "intrinsic_call":
        module, function = str(value.value).split(".")
        node = ast.Call(
            func=ast.Attribute(value=ast.Name(id=module, ctx=ast.Load()), attr=function, ctx=ast.Load()),
            args=operands,
            keywords=[],
        )
    elif operation == "runtime_call":
        node = ast.Call(
            func=ast.Name(id=str(value.value), ctx=ast.Load()),
            args=operands,
            keywords=[],
        )
    elif operation == "comprehend":
        node = ast.Call(
            func=ast.Name(id="__comprehend", ctx=ast.Load()),
            args=operands[:1],
            keywords=[],
        )
        target_count = int(value.operators[0]) if value.operators else 1
        condition_counts = [int(count) for count in value.operators[1:]] or target_count * [0]
        condition_groups = []
        remaining = operands[1 + target_count :]
        for count in condition_counts:
            condition_groups.append(remaining[:count])
            remaining = remaining[count:]
        node.py2rust_comprehension = (
            str(value.value).split("|"),
            operands[0],
            operands[1 : 1 + target_count],
            condition_groups,
            value.type.name,
        )
    elif operation == "enum_name":
        node = ast.Call(func=ast.Name(id="__enum_name", ctx=ast.Load()), args=operands, keywords=[])
        node.py2rust_enum_name = value.operators
    elif operation == "choice":
        node = ast.Call(func=ast.Name(id="__choice", ctx=ast.Load()), args=operands, keywords=[])
    elif operation == "accumulate":
        node = ast.Call(func=ast.Name(id="__accumulate", ctx=ast.Load()), args=operands, keywords=[])
    elif operation == "dict_merge":
        node = ast.Call(func=ast.Name(id="__dict_merge", ctx=ast.Load()), args=operands, keywords=[])
    elif operation == "next_counter":
        node = ast.Call(func=ast.Name(id="__next_counter", ctx=ast.Load()), args=operands, keywords=[])
        node.py2rust_counter = name(str(value.value))
    elif operation == "defaultdict_list":
        node = ast.Call(func=ast.Name(id="__defaultdict_list", ctx=ast.Load()), args=[], keywords=[])
    elif operation == "defaultdict_set":
        node = ast.Call(func=ast.Name(id="__defaultdict_set", ctx=ast.Load()), args=[], keywords=[])
    elif operation == "format_value":
        node = ast.Call(func=ast.Name(id="__format_value", ctx=ast.Load()), args=operands, keywords=[])
        node.py2rust_format_value = str(value.value)
    elif operation == "enum_members":
        node = ast.Call(func=ast.Name(id="__enum_members", ctx=ast.Load()), args=[], keywords=[])
        node.py2rust_enum_members = name(str(value.value))
    elif operation == "int_enum_members":
        node = ast.List(
            elts=[ast.Constant(value=item) for item in value.value],
            ctx=ast.Load(),
        )
    elif operation == "enum_from_value":
        node = ast.Call(func=ast.Name(id="__enum_from_value", ctx=ast.Load()), args=operands, keywords=[])
        node.py2rust_enum_from_value = name(str(value.value))
    elif operation == "enum_name_exists":
        node = ast.Call(func=ast.Name(id="__enum_name_exists", ctx=ast.Load()), args=operands, keywords=[])
        node.py2rust_enum_name_exists = (name(str(value.value)), value.operators)
    elif operation == "enum_from_name":
        node = ast.Call(func=ast.Name(id="__enum_from_name", ctx=ast.Load()), args=operands, keywords=[])
        node.py2rust_enum_from_name = (name(str(value.value)), value.operators)
    elif operation == "sequence_index":
        node = ast.Call(func=ast.Name(id="__sequence_index", ctx=ast.Load()), args=operands, keywords=[])
    elif operation == "is_type":
        node = ast.Call(func=ast.Name(id="__is_type", ctx=ast.Load()), args=operands, keywords=[])
        node.py2rust_is_type = (str(value.value), value.operators[0])
    elif operation == "set_union":
        node = ast.Call(func=ast.Name(id="__set_union", ctx=ast.Load()), args=operands, keywords=[])
    elif operation == "pack_float":
        node = ast.Call(func=ast.Name(id="__pack_float", ctx=ast.Load()), args=operands, keywords=[])
    elif operation == "pack_ints":
        node = ast.Call(func=ast.Name(id="__pack_ints", ctx=ast.Load()), args=operands, keywords=[])
    elif operation == "unpack_ints":
        node = ast.Call(func=ast.Name(id="__unpack_ints", ctx=ast.Load()), args=operands, keywords=[])
        node.py2rust_tuple_items = len(value.type.arguments)
    elif operation == "unique_sequence":
        node = ast.Call(func=ast.Name(id="__unique_sequence", ctx=ast.Load()), args=operands, keywords=[])
    elif operation == "optional_value":
        node = ast.Call(func=ast.Name(id="__optional_value", ctx=ast.Load()), args=operands, keywords=[])
    elif operation == "counter":
        node = ast.Call(func=ast.Name(id="__counter", ctx=ast.Load()), args=operands, keywords=[])
    elif operation == "unpack_float":
        node = ast.Call(func=ast.Name(id="__unpack_float", ctx=ast.Load()), args=operands, keywords=[])
    elif operation == "shuffle":
        node = ast.Call(func=ast.Name(id="__shuffle", ctx=ast.Load()), args=operands, keywords=[])
        node.py2rust_shuffle = name(str(value.value))
    elif operation == "map_random":
        node = ast.Call(func=ast.Name(id="__map_random", ctx=ast.Load()), args=operands, keywords=[])
        node.py2rust_map_random = str(value.value)
    elif operation == "optional_len":
        node = ast.Call(func=ast.Name(id="__optional_len", ctx=ast.Load()), args=operands, keywords=[])
    elif operation == "optional_unwrap":
        node = ast.Call(func=ast.Name(id="__optional_unwrap", ctx=ast.Load()), args=operands, keywords=[])
    elif operation == "zip_pairs":
        node = ast.Call(func=ast.Name(id="__zip_pairs", ctx=ast.Load()), args=operands, keywords=[])
    elif operation == "truthy":
        node = ast.Call(func=ast.Name(id="__truthy", ctx=ast.Load()), args=operands, keywords=[])
    elif operation == "key_sorted":
        node = ast.Call(func=ast.Name(id="__key_sorted", ctx=ast.Load()), args=operands[:1], keywords=[])
        node.py2rust_key_sorted = (str(value.value), operands[1], operands[2:])
    elif operation == "key_extreme":
        node = ast.Call(func=ast.Name(id="__key_extreme", ctx=ast.Load()), args=operands[:1], keywords=[])
        node.py2rust_key_extreme = (str(value.value), operands[1], value.operators[0], operands[2:])
    elif operation == "class_name":
        node = ast.Call(func=ast.Name(id="__class_name", ctx=ast.Load()), args=operands, keywords=[])
    elif operation == "find":
        node = ast.Call(
            func=ast.Name(id="__find", ctx=ast.Load()),
            args=operands[:2],
            keywords=[],
        )
        node.py2rust_find = (str(value.value), operands[2], operands[3:])
    elif operation == "indirect_call":
        node = ast.Call(func=operands[0], args=operands[1:], keywords=[])
    elif operation == "replace":
        node = ast.Call(func=ast.Name(id="__replace", ctx=ast.Load()), args=operands, keywords=[])
        node.py2rust_replace = (name(str(value.value)), value.operators)
    elif operation in {"construct", "call"}:
        labels = value.operators or ("",) * len(operands)
        node = ast.Call(
            func=ast.Name(id=name(str(value.value)), ctx=ast.Load()),
            args=[
                ast.Starred(value=operand, ctx=ast.Load()) if label == "*" else operand
                for label, operand in zip(labels, operands)
                if not label or label == "*"
            ],
            keywords=[
                ast.keyword(arg=label, value=operand)
                for label, operand in zip(labels, operands)
                if label and label != "*"
            ],
        )
    elif operation == "native_call":
        node = ast.Call(
            func=ast.Name(id=name(str(value.value)), ctx=ast.Load()),
            args=operands,
            keywords=[],
        )
    elif operation == "assign_expr":
        node = ast.NamedExpr(target=ast.Name(id=name(str(value.value)), ctx=ast.Store()), value=operands[0])
    elif operation == "binary":
        node = ast.BinOp(left=operands[0], op=BINARY[value.value](), right=operands[1])
    elif operation == "unary":
        node = ast.UnaryOp(
            op={"-": ast.USub, "+": ast.UAdd, "~": ast.Invert, "not": ast.Not}[value.value](),
            operand=operands[0],
        )
    elif operation == "short_circuit":
        node = ast.BoolOp(op=ast.And() if value.value == "and" else ast.Or(), values=operands)
    elif operation == "compare_chain":
        node = ast.Compare(
            left=operands[0],
            ops=[COMPARE[op]() for op in value.operators],
            comparators=operands[1:],
        )
    elif operation == "conditional":
        node = ast.IfExp(test=operands[0], body=operands[1], orelse=operands[2])
    elif operation in {"list", "json_array_literal"}:
        node = ast.List(elts=operands, ctx=ast.Load())
    elif operation == "tuple":
        node = ast.Tuple(elts=operands, ctx=ast.Load())
    elif operation == "set":
        node = ast.Set(elts=operands)
    elif operation in {"dict", "json_object"}:
        node = ast.Dict(keys=operands[::2], values=operands[1::2])
    elif operation == "enum_member":
        owner, member = str(value.value).rsplit(".", 1)
        node = ast.Attribute(value=ast.Name(id=name(owner), ctx=ast.Load()), attr=member, ctx=ast.Load())
    elif operation == "field":
        node = ast.Attribute(value=operands[0], attr=str(value.value), ctx=ast.Load())
    elif operation == "slice":
        bounds = dict(zip(value.operators, operands[1:]))
        node = ast.Subscript(
            value=operands[0],
            slice=ast.Slice(
                lower=bounds.get("start"),
                upper=bounds.get("stop"),
                step=bounds.get("step"),
            ),
            ctx=ast.Load(),
        )
    elif operation == "index":
        node = ast.Subscript(value=operands[0], slice=operands[1], ctx=ast.Load())
    else:
        raise AdapterError(f"unsupported IR expression {operation} at {value.source}")
    if operation != "json_coerce":
        node.py2rust_value_type = value.type
    if operation == "runtime_call":
        node.py2rust_effect_expression = value
    if operation in {"json_object", "json_array_literal"}:
        node.py2rust_json_coercion = True
    if evaluation_facts is not None:
        node.py2rust_evaluation = evaluation_facts[value]
        node.py2rust_collection_mutations = tuple(
            (name(mutation.root), mutation.source) for mutation in evaluation_facts[value].mutations
        )
    return locate(node, value.source)


class BlockAdapter:
    def __init__(
        self,
        locals: set[str],
        exception_facts: dict[ir.Statement, StatementFlow],
        tail_returns: frozenset[ir.Statement],
        evaluation_facts: dict[ir.Expression, EvaluationProof] | None,
        append_facts: dict[ir.Statement, StringAppendDecision | None] | None = None,
        iteration_facts: dict[ir.Statement, IterationDecision] | None = None,
    ) -> None:
        self.locals = locals
        self.exception_facts = exception_facts
        self.tail_returns = tail_returns
        self.evaluation_facts = evaluation_facts
        self.append_facts = append_facts
        self.iteration_facts = iteration_facts

    def block(self, body: tuple[ir.Statement, ...], *, scoped: bool = True) -> list[ast.stmt]:
        before = self.locals.copy()
        output = [self.statement(item) for item in body]
        if scoped:
            self.locals = before
        return output

    def statement(self, item: ir.Statement) -> ast.stmt:
        values = [expression(value, self.evaluation_facts) for value in item.expressions]
        operation = item.operation
        if operation == "return":
            node = ast.Return(value=values[0] if values else None)
        elif operation == "expression":
            node = ast.Expr(value=values[0])
        elif operation == "delete_slice":
            bounds = dict(zip((item.target or "").split(","), values[1:]))
            node = ast.Delete(
                targets=[
                    ast.Subscript(
                        value=values[0],
                        slice=ast.Slice(lower=bounds.get("start"), upper=bounds.get("stop")),
                        ctx=ast.Del(),
                    )
                ]
            )
        elif operation == "delete_index":
            node = ast.Delete(targets=[ast.Subscript(value=values[0], slice=values[1], ctx=ast.Del())])
        elif operation == "store_field":
            node = ast.Assign(
                targets=[ast.Attribute(value=values[1], attr=item.target, ctx=ast.Store())],
                value=values[0],
            )
        elif operation == "store_index":
            node = ast.Assign(
                targets=[ast.Subscript(value=values[1], slice=values[2], ctx=ast.Store())],
                value=values[0],
            )
        elif operation == "store_slice":
            node = ast.Assign(
                targets=[ast.Subscript(value=values[1], slice=ast.Slice(), ctx=ast.Store())],
                value=values[0],
            )
        elif operation == "unpack_assign":
            target_node = ast.parse(str(item.target), mode="eval").body

            def store(pattern: ast.expr) -> ast.expr:
                if isinstance(pattern, ast.Attribute):
                    return ast.Name(id=name(ast.unparse(pattern)), ctx=ast.Store())
                if isinstance(pattern, ast.Name):
                    pattern.id = name(pattern.id)
                    pattern.ctx = ast.Store()
                elif isinstance(pattern, ast.Tuple):
                    pattern.elts = [store(element) for element in pattern.elts]
                    pattern.ctx = ast.Store()
                return pattern

            target_node = store(target_node)
            node = ast.Assign(targets=[target_node], value=values[0])
            self.locals.update(element.id for element in ast.walk(target_node) if isinstance(element, ast.Name))
            node.py2rust_unpack_annotation = annotation(item.target_type)
        elif operation == "assign":
            if self.append_facts is not None:
                plan = self.append_facts[item]
                values[0].py2rust_string_append = None
                if plan is not None:
                    # Reuse the original operand nodes so liveness/use-site facts
                    # remain attached. The IR policy already selected the split.
                    suffixes = []
                    prefix = values[0]
                    for _ in range(plan.suffix_count):
                        suffixes.append(prefix.right)
                        prefix = prefix.left
                    suffixes.reverse()
                    suffix = suffixes[0]
                    for part in suffixes[1:]:
                        suffix = ast.copy_location(ast.BinOp(left=suffix, op=ast.Add(), right=part), part)
                    values[0].py2rust_string_append = StringAppend(
                        name(plan.target), suffix, plan.source.line, plan.reason
                    )
            target = ast.Name(id=name(item.target), ctx=ast.Store())
            if item.target in self.locals:
                node = ast.Assign(targets=[target], value=values[0])
            else:
                self.locals.add(item.target)
                node = ast.AnnAssign(
                    target=target,
                    annotation=annotation(item.target_type or item.expressions[0].type),
                    value=values[0],
                    simple=1,
                )
        elif operation == "group":
            node = ast.If(test=ast.Constant(value=True), body=self.block(item.blocks[0]), orelse=[])
            node.py2rust_group = True
        elif operation == "if":
            tail = self.block(item.blocks[-1])
            for test, body in reversed(list(zip(values, item.blocks[:-1]))):
                tail = [ast.If(test=test, body=self.block(body), orelse=tail)]
            node = tail[0]
        elif operation == "while":
            node = ast.While(
                test=values[0],
                body=self.block(item.blocks[0]),
                orelse=self.block(item.blocks[1]),
            )
        elif operation == "for":
            before = self.locals.copy()
            self.locals.add(item.target)
            body = self.block(item.blocks[0])
            self.locals = before
            node = ast.For(
                target=ast.parse(item.target, mode="eval").body,
                iter=values[0],
                body=body,
                orelse=self.block(item.blocks[1]),
            )
            if self.iteration_facts is not None:
                plan = self.iteration_facts[item]
                node.py2rust_iteration = IterationUse(
                    plan.mode, plan.borrow_item, plan.reason, name(plan.source) if plan.source is not None else None
                )
        elif operation == "resource_scope":
            before = self.locals.copy()
            self.locals.add(item.target)
            body = self.block(item.blocks[0])
            self.locals = before
            node = ast.With(
                items=[
                    ast.withitem(
                        context_expr=values[0],
                        optional_vars=ast.Name(id=name(item.target), ctx=ast.Store()),
                    )
                ],
                body=body,
            )
        elif operation == "try":
            handlers = []
            for handler in item.handlers:
                before = self.locals.copy()
                if handler.binding:
                    self.locals.add(handler.binding)
                body = self.block(handler.body)
                self.locals = before
                handlers.append(
                    locate(
                        ast.ExceptHandler(
                            type=ast.Name(id=name(handler.exception), ctx=ast.Load()),
                            name=name(handler.binding) if handler.binding else None,
                            body=body,
                        ),
                        handler.source,
                    )
                )
            node = ast.Try(
                body=self.block(item.blocks[0]),
                handlers=handlers,
                orelse=self.block(item.blocks[1]),
                finalbody=self.block(item.blocks[2]),
            )
        elif operation == "assert":
            node = ast.Assert(test=values[0], msg=values[1] if len(values) > 1 else None)
        elif operation == "raise":
            node = ast.Raise(exc=values[0], cause=None)
        elif operation == "reraise":
            node = ast.Raise(exc=None, cause=None)
        elif operation in {"pass", "break", "continue"}:
            node = {"pass": ast.Pass, "break": ast.Break, "continue": ast.Continue}[operation]()
        else:
            raise AdapterError(f"unsupported IR statement {operation} at {item.source}")
        node.py2rust_flow = self.exception_facts[item]
        node.py2rust_tail_return = item in self.tail_returns
        return locate(node, item.source)


def linked_tree(
    modules: tuple[ir.Module, ...],
    entry: str,
    *,
    nonmutating_calls: frozenset[str] = frozenset(),
    exception_facts: dict[ir.Statement, StatementFlow],
    tail_returns: frozenset[ir.Statement] = frozenset(),
    evaluation_facts: dict[ir.Expression, EvaluationProof] | None = None,
    parameter_plans: tuple[FunctionParameters, ...] | None = None,
    liveness: tuple[FunctionLiveness, ...] | None = None,
    move_safety: MoveSafetyPlan | None = None,
    view_plans: tuple[FunctionViews, ...] | None = None,
    efficiency_plans: tuple[FunctionEfficiency, ...] | None = None,
    append_facts: dict[ir.Statement, StringAppendDecision | None] | None = None,
    effect_plan: EffectPlan | None = None,
    iteration_facts: dict[ir.Statement, IterationDecision] | None = None,
    binding_plans: tuple[tuple[str, frozenset[str]], ...] = (),
    entry_bindings: frozenset[str] | None = None,
) -> ast.Module:
    prepared_bindings = dict(binding_plans)
    prepared_efficiency = {plan.function: plan for plan in efficiency_plans} if efficiency_plans is not None else None
    prepared_views = {plan.function: plan for plan in view_plans} if view_plans is not None else None
    prepared_parameters = {plan.function: plan for plan in parameter_plans} if parameter_plans is not None else None
    if entry not in {module.name for module in modules}:
        raise AdapterError(f"entry module {entry!r} is absent")
    # Runtime contracts are explicitly available; application imports still resolve
    # through mypy. The service emitter validates every selected runtime signature.
    from ..libraries import RUNTIME

    definitions = [
        ast.Import(names=[ast.alias(name="heapq")]),
        ast.ImportFrom(
            module="py2rust.stdlib",
            names=[ast.alias(name=item) for item in sorted({contract.runtime_name for contract in RUNTIME.values()})],
            level=0,
        ),
    ]
    if any(module.enums for module in modules):
        definitions.append(ast.ImportFrom(module="enum", names=[ast.alias(name="Enum")], level=0))
    for module in modules:
        for enum in module.enums:
            members = [
                locate(
                    ast.Assign(
                        targets=[ast.Name(id=member, ctx=ast.Store())],
                        value=expression(value, evaluation_facts),
                    ),
                    value.source,
                )
                for member, value in enum.members
            ]
            definitions.append(
                locate(
                    ast.ClassDef(
                        name=name(enum.name),
                        bases=[ast.Name(id="Enum", ctx=ast.Load())],
                        keywords=[],
                        body=members,
                        decorator_list=[],
                    ),
                    enum.source,
                )
            )
    if any(module.records for module in modules):
        definitions.append(ast.ImportFrom(module="dataclasses", names=[ast.alias(name="dataclass")], level=0))
    for record in ordered_records(tuple(record for module in modules for record in module.records)):
        fields = [
            locate(
                ast.AnnAssign(
                    target=ast.Name(id=field.name, ctx=ast.Store()),
                    annotation=annotation(field.type),
                    value=expression(field.default, evaluation_facts) if field.default else None,
                    simple=1,
                ),
                field.source,
            )
            for field in record.fields
        ]
        definitions.append(
            locate(
                ast.ClassDef(
                    name=name(record.name),
                    bases=[],
                    keywords=[],
                    body=fields,
                    decorator_list=[ast.Name(id="dataclass", ctx=ast.Load())],
                ),
                record.source,
            )
        )
    for module in modules:
        for function in module.functions:
            args = ast.arguments(
                posonlyargs=[],
                args=[ast.arg(arg=name(p.name), annotation=annotation(p.type)) for p in function.parameters],
                kwonlyargs=[],
                kw_defaults=[],
                defaults=[expression(default) for default in function.defaults],
            )
            body = BlockAdapter(
                {name(p.name) for p in function.parameters},
                exception_facts,
                tail_returns,
                evaluation_facts,
                append_facts,
                iteration_facts,
            ).block(function.body, scoped=False)
            definitions.append(
                locate(
                    ast.FunctionDef(
                        name=name(function.name),
                        args=args,
                        body=body,
                        decorator_list=[],
                        returns=annotation(function.result),
                    ),
                    function.source,
                )
            )
            if function.name in prepared_bindings:
                definitions[-1].py2rust_mutable_bindings = frozenset(name(n) for n in prepared_bindings[function.name])
            if prepared_efficiency is not None:
                definitions[-1].py2rust_efficiency_plan = prepared_efficiency[function.name]
            if prepared_views is not None:
                definitions[-1].py2rust_view_plan = prepared_views[function.name]
            if prepared_parameters is not None:
                plan = prepared_parameters[function.name]
                definitions[-1].py2rust_parameter_plan = FunctionParameters(
                    name(plan.function),
                    plan.callback,
                    tuple(
                        ParameterDecision(name(item.name), item.mode, item.reason, item.line)
                        for item in plan.parameters
                    ),
                )
        declarations, executable = module_layout(module, entry)
        definitions.extend(
            BlockAdapter(set(), exception_facts, tail_returns, evaluation_facts, append_facts, iteration_facts).block(
                declarations, scoped=False
            )
        )
        if module.name == entry:
            guard = ast.parse("if __name__ == '__main__':\n    pass\n").body[0]
            guard.body = BlockAdapter(
                set(), exception_facts, tail_returns, evaluation_facts, append_facts, iteration_facts
            ).block(executable, scoped=False) or [ast.Pass()]
            if entry_bindings is not None:
                guard.py2rust_mutable_bindings = frozenset(name(n) for n in entry_bindings)
            definitions.append(guard)
    tree = ast.fix_missing_locations(ast.Module(body=definitions, type_ignores=[]))
    if effect_plan is not None:
        tree.py2rust_effect_plan = effect_plan
        targets = {function.function for function in effect_plan.functions}
        targets.update(
            str(call.value)
            for function in effect_plan.functions
            for call in function.calls
            if call.operation in {"call", "native_call", "construct"}
        )
        tree.py2rust_effect_symbols = {target: name(target) for target in targets}
    if move_safety is not None:
        tree.py2rust_move_safety = MoveSafetyPlan(
            tuple((name(record), permitted) for record, permitted in move_safety.records),
            frozenset(name(enum) for enum in move_safety.enums),
        )
    if liveness is not None:
        plans = {name(plan.function): plan for plan in liveness}
        for function in tree.body:
            if not isinstance(function, ast.FunctionDef):
                continue
            uses = {}
            for decision in plans[function.name].uses:
                source = decision.expression.source
                key = (source.path, source.line, max(0, source.column), name(str(decision.expression.value)))
                # If lowering duplicated a source place, any required copy wins.
                if key not in uses or decision.mode == "copy":
                    uses[key] = decision
            mapped = {}
            for node in ast.walk(function):
                if isinstance(node, ast.Name):
                    key = (getattr(node, "source_path", None), node.lineno, node.col_offset, node.id)
                    if key in uses:
                        decision = uses[key]
                        mapped[id(node)] = OwnershipUse(node.id, node.lineno, decision.mode, decision.reason)
            function.py2rust_ownership_uses = mapped
    proven = {name(symbol) for symbol in nonmutating_calls}
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in proven:
            node.py2rust_nonmutating_call = True
    return tree
