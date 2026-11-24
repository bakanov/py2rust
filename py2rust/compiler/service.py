"""Typed service subset using py2rust's Rust AST and a versioned library boundary."""

import ast
import sys
from pathlib import Path

from .backend.binding_emission import emit_assignment, emit_delete, emit_local
from .backend.call_emission import emit_call
from .backend.exception_emission import render_finally
from .backend.expression_emission import emit_expression
from .backend.loop_emission import emit_for
from .backend.module_emission import emit_module
from .backend.protected_emission import emit_resource, emit_try
from .backend.readable_emission import render_reference, render_return
from .backend.values import Expr as Expr
from .backend.values import Type as Type
from .exceptions import always_returns, invalid_try_jump, plan_try
from .libraries import serialization
from .library_contracts import LIBRARY, RUNTIME_PARAMETERS
from .memory import (
    RuntimeParameter,
    runtime_argument_use,
)
from .move_safety import MoveContext, MoveSafetyPlan, can_transfer, owned_boundary
from .place_policy import BorrowOptions, projection
from .project_output import write_service_project as write_service_project
from .readability import reference_style, return_style
from .rules.access import (
    render_text_slice,
)
from .rules.assignment import (
    render_indexed_list_mutation,
    render_nested_assignment,
)
from .rules.byte_methods import render_byte_method, select_byte_method
from .rules.collection_methods import render_collection_method, select_collection_method
from .rules.comparisons import (
    membership_rule,
    render_comparison,
    render_empty_string,
    render_membership,
    render_null_identity,
    render_set_order,
    set_order_rule,
)
from .rules.control_flow import render_assert, render_if, render_reraise, render_while
from .rules.ordering import orderable_shape, render_sorting, sorting_rule
from .rules.records import (
    borrowed_runtime_field,
    dictionary_get_style,
    runtime_field_type,
)
from .rules.strings import render_string_call, select_string_rule
from .rust_text import quote as quote


class ServiceError(ValueError):
    def __init__(self, message: str, node: ast.AST) -> None:
        self.lineno = getattr(node, "lineno", 1)
        self.filename = getattr(node, "source_path", None)
        super().__init__(message)


class ServiceCompiler:
    def __init__(self, external_functions: dict | None = None, *, optimize: bool = True) -> None:
        self.collect_costs = False
        self.lowering_decisions: list = []
        self.optimization_report: dict = {}
        self.runtime_effect_selections: dict = {}
        self.current_function: str | None = None
        self.optimize = optimize
        self.optimize_text = optimize
        self.optimize_json_views = optimize
        self.optimize_iteration = optimize
        self.optimize_slices = optimize
        self.optimize_serialization = optimize
        self.optimize_idioms = optimize
        self.mutable_bindings: set[str] = set()
        self.cached_lengths: dict = {}
        self.parameter_uses: dict = {}
        self.borrowed_parameters: set[str] = set()
        self.borrowed_str_parameters: set[str] = set()
        self.ownership_uses: dict = {}
        self.move_safety: MoveSafetyPlan | None = None
        self.indexed_text: dict = {}
        self.slice_views: dict[str, str] = {}
        self.array_views: dict[str, str] = {}
        self.sequence_views: dict[str, str] = {}
        self.imports: set[str] = set()
        self.modules: set[str] = set()
        self.enums: dict[str, dict[str, str | int]] = {}
        self.records: dict[str, dict[str, tuple[Type, Expr | None]]] = {}
        self.functions: dict[str, tuple] = dict(external_functions or {})
        self.constants: dict[str, Expr] = {}
        self.locals: dict[str, Type] = {}
        self.result = Type("None")
        self.try_depth = 0
        self.active_errors: list[str] = []
        self.error_counter = 0

    def error(self, message: str, node: ast.AST) -> None:
        raise ServiceError(message, node)

    def typ(self, node: ast.AST, self_type: str | None = None) -> Type:
        if isinstance(node, ast.Constant) and node.value is None:
            return Type("None")
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            try:
                annotation = ast.parse(node.value, mode="eval").body
            except SyntaxError:
                self.error("invalid quoted type annotation", node)
            for child in ast.walk(annotation):
                ast.copy_location(child, node)
                if hasattr(node, "source_path"):
                    child.source_path = node.source_path
            return self.typ(annotation, self_type)
        if isinstance(node, ast.Name) and node.id in {
            "int",
            "float",
            "bool",
            "str",
            "bytes",
            "bytearray",
            "Json",
            "DateTime",
            "Rational",
            "HttpServer",
            "HttpResponse",
            "WebRequest",
            "WebResponse",
            "StreamChunk",
            "FileHandle",
            "GzipReader",
            "GzipWriter",
            "LineReader",
            "HttpReader",
            "TcpListener",
            "TcpStream",
            "UnixListener",
            "UnixStream",
            "UdpSocket",
            "ProcessPool",
            "Sha256",
            *self.enums,
            *self.records,
            self_type,
        }:
            return Type(node.id)
        if isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name):
            args = node.slice.elts if isinstance(node.slice, ast.Tuple) else [node.slice]
            name = node.value.id
            if name == "tuple" and len(args) == 2 and isinstance(args[1], ast.Constant) and args[1].value is Ellipsis:
                element = self.typ(args[0], self_type)
                if element.name in {"None", "HttpServer"}:
                    self.error("unsupported collection element type", node)
                return Type("tuple_var", (element,))
            if (
                (name in {"list", "set"} and len(args) == 1)
                or (name == "dict" and len(args) == 2)
                or (name == "tuple" and args)
            ):
                types = tuple(self.typ(arg, self_type) for arg in args)
                if name in {"set", "dict"} and not self.hashable(types[0]):
                    self.error("collection keys must be str, int, bool, enums or immutable tuples of those types", node)
                if any(t.name in {"None", "HttpServer"} for t in types):
                    self.error("unsupported collection element type", node)
                return Type(name, types)
        self.error("unsupported or missing type annotation", node)

    def hashable(self, typ: Type) -> bool:
        if typ.name in {"str", "int", "bool", *self.enums}:
            return True
        return (
            typ.name in {"tuple", "tuple_var"}
            and (typ.name != "tuple" or len(typ.args) <= 12)
            and all(self.hashable(item) for item in typ.args)
        )

    def named_type(self, name: str) -> Type:
        return self.typ(ast.parse(name, mode="eval").body)

    def check_name(self, name: str, node: ast.AST) -> None:
        if name in {
            *LIBRARY,
            *self.imports,
            *self.modules,
            *self.enums,
            *self.records,
            *self.functions,
            *self.constants,
            "rt",
            "main",
            "print",
            "len",
            "ord",
            "sorted",
            "range",
            "str",
            "int",
            "bytes",
            "bytearray",
            "list",
            "dict",
            "tuple",
            "set",
            "min",
            "max",
            "Exception",
        } or name.startswith("__"):
            self.error(f"reserved binding: {name}", node)
        # A small explicit Rust keyword guard is preferable to ambiguous name mangling.
        if name in {
            "Self",
            "true",
            "false",
            "abstract",
            "become",
            "box",
            "do",
            "dyn",
            "final",
            "let",
            "macro",
            "override",
            "priv",
            "try",
            "typeof",
            "unsized",
            "virtual",
            "yield",
            "match",
            "type",
            "loop",
            "move",
            "ref",
            "mut",
            "fn",
            "impl",
            "trait",
            "enum",
            "struct",
            "use",
            "mod",
            "crate",
            "pub",
            "where",
            "self",
            "super",
            "extern",
            "unsafe",
            "const",
            "static",
        }:
            self.error(f"Rust keyword cannot be a binding: {name}", node)

    def convert(self, expression: Expr, expected: Type, node: ast.AST) -> Expr:
        if expression.type == expected:
            return expression
        if (
            expected.name == "tuple_var"
            and expression.type.name == "tuple"
            and all(item == expected.args[0] for item in expression.type.args)
        ):
            fields = ", ".join(f"__tuple_value.{index}.clone()" for index in range(len(expression.type.args)))
            return Expr(f"{{ let __tuple_value = {self.reference(expression)}; vec![{fields}] }}", expected)
        if expected.name == "Json" and self.serializable(expression.type):
            if self.optimize_idioms and expression.type.name in {"str", "int", "bool"}:
                value = expression.code
                if expression.borrowed:
                    value = f"({value}).to_owned()" if expression.type.name == "str" else f"*({value})"
                return Expr(f"serde_json::Value::from({value})", expected)
            return Expr(f"rt::to_json(&({expression.code}))?", expected)
        if expected.name == "float" and expression.type.name == "int":
            return Expr(f"({expression.code} as f64)", expected)
        self.error(f"expected {expected}, got {expression.type}", node)

    def move_context(self, node: ast.Name, typ: Type) -> MoveContext:
        use = self.ownership_uses.get(id(node))
        views = (self.slice_views, self.array_views, self.sequence_views)
        return MoveContext(
            local=node.id in self.locals,
            last_use=use is not None and use.mode == "move",
            borrowed=node.id in self.borrowed_parameters,
            is_view=any(node.id in mapping for mapping in views),
            backs_view=node.id in self.indexed_text or any(node.id in mapping.values() for mapping in views),
            type_safe=self.move_safe_type(typ),
        )

    def can_move_local(self, node: ast.Name, typ: Type) -> bool:
        return can_transfer(self.move_context(node, typ))

    def move_safe_type(self, typ: Type, seen: frozenset[str] = frozenset()) -> bool:
        if self.move_safety is not None:
            return self.move_safety.permits(typ.value_type())
        return self._legacy_move_safe_type(typ, seen)

    def _legacy_move_safe_type(self, typ: Type, seen: frozenset[str] = frozenset()) -> bool:
        """Legacy recursive type walk; typed input uses the prepared IR plan."""
        if typ.name in {"str", "bytes", "bytearray", "Json", "int", "float", "bool", "None", *self.enums}:
            return True
        if typ.name in {"list", "dict", "set", "tuple", "tuple_var"}:
            return all(self.move_safe_type(item, seen) for item in typ.args)
        if typ.name in self.records:
            if typ.name in seen:
                return True
            return all(self.move_safe_type(field[0], seen | {typ.name}) for field in self.records[typ.name].values())
        return False

    def serializable(self, typ: Type) -> bool:
        return serialization.serializable(typ.value_type())

    def expr(self, node: ast.AST, expected: Type | None = None) -> Expr:
        coercion = Type("Json") if getattr(node, "py2rust_json_coercion", False) else None
        value = self._expr(node, coercion or expected)
        if coercion:
            value = self.convert(value, coercion, node)
        return self.convert(value, expected, node) if expected else value

    def read_value(self, node: ast.AST) -> Expr:
        """Borrow local collection paths; callers must return owned results."""
        borrowed = self.local_read(node)
        return borrowed if borrowed is not None else self.expr(node)

    def record_decision(self, node: ast.AST, operation: str, mode: str, reason: str) -> None:
        if self.collect_costs and self.current_function is not None:
            from .diagnostics import LoweringDecision

            self.lowering_decisions.append(
                LoweringDecision(
                    self.current_function,
                    getattr(node, "lineno", 0),
                    getattr(node, "col_offset", 0),
                    operation,
                    mode,
                    reason,
                )
            )
        return  # noqa: PLR1711 - explicit-return convention

    def record_owned_boundary(self, node: ast.AST | None) -> None:
        """Explain direct local reads committed to assignments or returns.

        Do not call from speculative expression/type probes or discarded receivers.
        """
        if not self.collect_costs or not isinstance(node, ast.Name) or node.id not in self.locals:
            return
        typ = self.locals[node.id]
        use = self.ownership_uses.get(id(node))
        decision = owned_boundary(
            self.move_context(node, typ), typ.name, use.reason if use is not None and use.mode == "copy" else None
        )
        if decision is not None:
            self.record_decision(node, "owned_boundary", decision.mode, decision.reason)
        return

    def argument_place(self, node: ast.AST, *, allow_place: bool = True) -> Expr | None:
        if self.optimize_idioms and isinstance(node, ast.Constant) and isinstance(node.value, str):
            return Expr(quote(node.value), Type("str"), borrowed=True)
        return self.local_read(node) if allow_place else None

    def binding(self, name: str) -> str:
        return ("mut " if not self.optimize_idioms or name in self.mutable_bindings else "") + name

    def reference(self, value: Expr) -> str:
        style = reference_style(
            borrowed=value.borrowed, simple_name=value.code.isidentifier(), optimize=self.optimize_idioms
        )
        return render_reference(value.code, style)

    def local_read(self, node: ast.AST) -> Expr | None:
        """A reference can escape this expression only when rooted in a live local."""
        options = BorrowOptions(self.optimize_text, self.optimize_slices, self.optimize_json_views)
        if (
            self.optimize_json_views
            and isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "json_array"
            and "json_array" in self.imports
            and len(node.args) == 1
            and not node.keywords
        ):
            parent = self.local_read(node.args[0])
            if projection("json_array", parent.type.value_type() if parent else None, options=options, stable=True):
                if self.collect_costs:
                    self.record_runtime_helper(node, "json_array_ref")
                return Expr(
                    f"rt::json_array_ref({self.reference(parent)})?", Type("list", (Type("Json"),)), borrowed=True
                )
        if isinstance(node, ast.Name) and node.id in self.locals:
            return Expr(
                node.id,
                self.locals[node.id],
                borrowed=node.id in self.borrowed_parameters
                or node.id in self.slice_views
                or node.id in self.array_views
                or node.id in self.sequence_views,
            )
        if isinstance(node, ast.Attribute):
            parent = self.local_read(node.value)
            if self.optimize and parent is not None and borrowed_runtime_field(parent.type.name, node.attr):
                return Expr(
                    f"&({parent.code}).{node.attr}",
                    self.named_type(runtime_field_type(parent.type.name, node.attr)),
                    borrowed=True,
                )
            if projection(
                "field",
                parent.type.value_type() if parent else None,
                options=options,
                stable=True,
                record=parent is not None and parent.type.name in self.records,
            ):
                field = self.records[parent.type.name].get(node.attr)
                if field is None:
                    self.error("unknown dataclass field: " + node.attr, node)
                return Expr(f"&({parent.code}).{node.attr}", field[0], borrowed=True)
        if self.optimize_slices and isinstance(node, ast.Subscript) and isinstance(node.slice, ast.Slice):
            use = runtime_argument_use(RuntimeParameter("bytes", "shared"), [node], 0)
            if use.mode != "borrow":
                return None
            parent = self.local_read(node.value)
            if projection("slice", parent.type.value_type() if parent else None, options=options, stable=True):
                if node.slice.step is not None:
                    self.error("slice steps are unsupported", node)
                start = self.expr(node.slice.lower, Type("int")).code if node.slice.lower else "0i64"
                end = self.expr(node.slice.upper, Type("int")).code if node.slice.upper else "i64::MAX"
                return Expr(f"rt::slice_view({self.reference(parent)}, {start}, {end})", parent.type, borrowed=True)
        if isinstance(node, ast.Subscript) and not isinstance(node.slice, ast.Slice):
            parent = self.local_read(node.value)
            kind = projection(
                "index",
                parent.type.value_type() if parent else None,
                options=options,
                stable=runtime_argument_use(RuntimeParameter("*", "shared"), [node], 0).mode == "borrow",
                indexed_text=isinstance(node.value, ast.Name) and node.value.id in self.indexed_text,
            )
            if kind in {"text", "indexed_text"}:
                position = self.expr(node.slice, Type("int"))
                if kind == "indexed_text":
                    code = f"{self.text_index(node.value.id)}.at_view({position.code})?"
                else:
                    code = f"rt::char_at_view({self.reference(parent)}, {position.code})?"
                return Expr(code, Type("str"), borrowed=True)
            if kind == "json":
                key = self.expr(node.slice)
                if key.type.name not in {"str", "int"}:
                    self.error("JSON index must be str or int", node)
                if key.type.name == "str":
                    argument = quote(node.slice.value) if isinstance(node.slice, ast.Constant) else f"&({key.code})"
                    helper = "json_key_ref"
                else:
                    argument = key.code
                    helper = "json_index_ref"
                return Expr(f"rt::{helper}({self.reference(parent)}, {argument})?", Type("Json"), borrowed=True)
            if kind == "tuple":
                if (
                    not isinstance(node.slice, ast.Constant)
                    or type(node.slice.value) is not int
                    or not 0 <= node.slice.value < len(parent.type.args)
                ):
                    self.error("tuple index must be a nonnegative constant in bounds", node)
                return Expr(f"&({parent.code}).{node.slice.value}", parent.type.args[node.slice.value], borrowed=True)
            if kind == "sequence":
                key = self.expr(node.slice, Type("int"))
                return Expr(
                    f"{{ let __source = {self.reference(parent)}; let __key = {key.code}; "
                    f"&__source[rt::index(__source.len(), __key)?] }}",
                    parent.type.args[0],
                    borrowed=True,
                )
            if kind == "mapping":
                key = self.expr(node.slice, parent.type.args[0])
                return Expr(
                    f'({parent.code}).get(&({key.code})).ok_or("missing dict key")?',
                    parent.type.args[1],
                    borrowed=True,
                )
        return None

    def text_index(self, name: str) -> str:
        return f"__text_{name}.get_or_init(|| rt::{self.indexed_text[name].representation}::new(&{name}))"

    def string_slice(self, node: ast.Subscript, obj: Expr, *, view: bool = False) -> Expr:
        if node.slice.step is not None:
            self.error("string slice steps are unsupported", node)
        start = self.expr(node.slice.lower, Type("int")).code if node.slice.lower else "0i64"
        end = self.expr(node.slice.upper, Type("int")).code if node.slice.upper else "i64::MAX"
        prepared_index = (
            self.text_index(node.value.id)
            if isinstance(node.value, ast.Name) and node.value.id in self.indexed_text
            else ""
        )
        return Expr(
            render_text_slice(self.reference(obj), start, end, prepared_index, view), Type("str"), borrowed=view
        )

    def _expr(self, node: ast.AST, expected: Type | None) -> Expr:
        return emit_expression(self, node, expected)

    def comparison(
        self, left: Expr, right: Expr, operation: ast.cmpop, left_node: ast.AST, right_node: ast.AST, node: ast.AST
    ) -> Expr:
        """Compare already-evaluated operands using the same rules in simple and chained expressions."""
        membership = isinstance(operation, (ast.In, ast.NotIn))
        if isinstance(operation, (ast.Is, ast.IsNot)):
            literal_left = isinstance(left_node, ast.Constant) and left_node.value is None
            literal_right = isinstance(right_node, ast.Constant) and right_node.value is None
            value = right if literal_left else left
            if not (literal_left or literal_right) or value.type.name not in {"Json", "None"}:
                self.error("identity comparison requires literal None and a JSON or None value", node)
            return Expr(
                render_null_identity(value.code, value.type.name == "Json", isinstance(operation, ast.IsNot)),
                Type("bool"),
            )
        compared_type = right.type
        if isinstance(operation, (ast.In, ast.NotIn)) and right.type.name in {"dict", "list", "set", "tuple_var"}:
            compared_type = right.type.args[0]
        if self.contains_record(left.type) or self.contains_record(compared_type):
            self.error("compare dataclass fields explicitly; record comparison and membership are unsupported", node)
        if membership:
            rule = membership_rule(left.type.name, right.type.name)
            if not rule:
                if right.type.name in {"bytes", "bytearray"}:
                    self.error("byte membership requires an integer or byte buffer", node)
                self.error("unsupported membership test", node)
            if right.type.name in {"dict", "list", "set", "tuple_var"}:
                left = self.convert(left, right.type.args[0], node)
            return Expr(
                render_membership(rule, left.code, self.reference(right), isinstance(operation, ast.NotIn)),
                Type("bool"),
            )
        if left.type.name == "tuple_var" and right.type.name == "tuple":
            right = self.convert(right, left.type, node)
        elif right.type.name == "tuple_var" and left.type.name == "tuple":
            left = self.convert(left, right.type, node)
        if left.type != right.type and not {left.type.name, right.type.name} <= {"bytes", "bytearray"}:
            self.error("comparison needs equal types", node)
        if self.optimize_idioms and left.type.name == "str" and isinstance(operation, (ast.Eq, ast.NotEq)):
            empty_left = isinstance(left_node, ast.Constant) and left_node.value == ""
            empty_right = isinstance(right_node, ast.Constant) and right_node.value == ""
            if empty_left or empty_right:
                value = right if empty_left else left
                return Expr(render_empty_string(value.code, isinstance(operation, ast.NotEq)), Type("bool"))
        if self.contains_set(left.type) and isinstance(operation, (ast.Lt, ast.LtE, ast.Gt, ast.GtE)):
            return self.set_sequence_order(left, right, operation, node)
        ops = {
            ast.Eq: "==",
            ast.NotEq: "!=",
            ast.Lt: "<",
            ast.LtE: "<=",
            ast.Gt: ">",
            ast.GtE: ">=",
        }
        if type(operation) not in ops:
            self.error("unsupported comparison", node)
        return Expr(render_comparison(ops[type(operation)], left.code, right.code), Type("bool"))

    def contains_set(self, typ: Type) -> bool:
        return typ.name == "set" or any(self.contains_set(child) for child in typ.args)

    def set_sequence_order(self, left: Expr, right: Expr, operation: ast.cmpop, node: ast.AST) -> Expr:
        """Rust's BTreeSet ordering is lexicographic; Python compares set inclusion.

        Lists/tuples containing sets must also use inclusion at their first
        unequal element rather than inheriting BTreeSet's total ordering.
        """
        symbol = {ast.Lt: "<", ast.LtE: "<=", ast.Gt: ">", ast.GtE: ">="}[type(operation)]
        rule = set_order_rule(left.type.name, self.contains_set(left.type))
        if not rule:
            self.error("set ordering supports sets and nested list/tuple sequences", node)
        children: list[str] = []
        if rule == "sequence.first_unequal":
            typ = left.type.args[0]
            compared = self.set_sequence_order(
                Expr("__item_left", typ, borrowed=True), Expr("__item_right", typ, borrowed=True), operation, node
            )
            children.append(compared.code)
        elif rule == "tuple.first_unequal":
            for index, typ in enumerate(left.type.args):
                compared = self.set_sequence_order(
                    Expr(f"&__left.{index}", typ, borrowed=True),
                    Expr(f"&__right.{index}", typ, borrowed=True),
                    operation,
                    node,
                )
                children.append(compared.code)
        return Expr(render_set_order(rule, symbol, self.reference(left), self.reference(right), children), Type("bool"))

    def direct_json_output(self, typ: Type) -> bool:
        return serialization.direct_output(typ.value_type())

    def library_call(self, name: str, args: list, node: ast.AST) -> Expr:
        result, params, fallible = LIBRARY[name]
        if len(args) != len(params):
            self.error(f"{name} expects {len(params)} arguments", node)
        values = []
        output_helper = name
        for index, (arg, param, metadata) in enumerate(zip(args, params, RUNTIME_PARAMETERS[name])):
            expected = None if param == "*" else self.named_type(param)
            if param == "*" and isinstance(arg, (ast.Dict, ast.List, ast.Tuple)):
                expected = Type("Json")
            use = runtime_argument_use(metadata, args, index)
            place = self.argument_place(arg, allow_place=use.mode == "borrow") if self.optimize else None
            # Representation-changing conversions still produce an owned temporary.
            if place is not None and (expected is None or place.type == expected):
                value = place
            else:
                value = self.expr(arg, expected)
            if param == "*" and not self.serializable(value.type):
                self.error("value is not JSON serializable; convert it explicitly", arg)
            output_helper = serialization.select_output(
                name, value.type.value_type(), optimize=self.optimize_serialization
            ).helper
            if metadata.passing == "shared":
                values.append(self.reference(value))
            else:
                values.append(value.code)
        if self.collect_costs:
            self.record_runtime_helper(node, output_helper)
        call = f"rt::{output_helper}({', '.join(values)})"
        return Expr(call + ("?" if fallible else ""), self.named_type(result), result_call=call if fallible else None)

    def record_runtime_helper(self, node: ast.Call, helper: str) -> None:
        node.lowered_runtime_helper = helper
        expression = getattr(node, "py2rust_effect_expression", None)
        if expression is not None:
            self.runtime_effect_selections[expression] = helper
        return  # noqa: PLR1711

    def call(self, node: ast.Call, expected: Type | None = None) -> Expr:
        return emit_call(self, node, expected)

    def sorted_call(self, node: ast.Call, expected: Type | None) -> Expr:
        """Sort a list or dictionary keys with an optional named key and stable direction."""
        if len(node.args) != 1 or isinstance(node.args[0], ast.Starred):
            self.error("sorted requires one positional list", node)
        keywords = {item.arg: item.value for item in node.keywords}
        if len(keywords) != len(node.keywords) or not set(keywords) <= {"key", "reverse"}:
            self.error("sorted accepts only unique key and reverse keywords", node)
        key = keywords.get("key")
        callback = None
        if key is not None and not (isinstance(key, ast.Constant) and key.value is None):
            if not isinstance(key, ast.Name) or key.id not in self.functions:
                self.error("sort key must be a named annotated function or None", key)
            callback = key.id
            params, result = self.functions[callback]
            if len(params) != 1 or not self.orderable(result):
                self.error("sort key requires one argument and an ordered non-float result", key)
        hint = expected if expected is not None and expected.name == "list" else None
        if hint is None and callback is not None:
            hint = Type("list", self.functions[callback][0])
        argument = node.args[0]
        # Context is needed to infer an empty list, but a typed dictionary expression
        # must retain its key type until its keys have been materialized below.
        infer_list = isinstance(argument, ast.List) or (
            isinstance(argument, ast.Call)
            and isinstance(argument.func, ast.Name)
            and argument.func.id == "list"
            and not argument.args
        )
        values = self.expr(argument, hint if infer_list else None)
        if values.type.name == "dict":
            values = Expr(f"({values.code}).keys().cloned().collect::<Vec<_>>()", Type("list", (values.type.args[0],)))
        if values.type.name != "list":
            self.error("sorted requires a typed list or dictionary", node.args[0])
        if hint is not None:
            values = self.convert(values, hint, node.args[0])
        if callback is not None:
            if self.functions[callback][0] != (values.type.args[0],):
                self.error("sort key argument must match the list element type", key)
        elif not self.orderable(values.type.args[0]):
            self.error("sorted requires a list of ordered non-float values without a key", node)
        reverse = self.expr(keywords["reverse"], Type("bool")).code if "reverse" in keywords else "false"
        rule = sorting_rule(callback is not None, "reverse" in keywords)
        return Expr(render_sorting(rule, values.code, callback or "", reverse), values.type)

    def contains_record(self, typ: Type) -> bool:
        return typ.name in self.records or any(self.contains_record(item) for item in typ.args)

    def set_operation(self, left: Expr, right: Expr, operation: str) -> Expr:
        """Evaluate both owned operands once, then construct an independent set."""
        return Expr(
            f"{{ let __set_left = {left.code}; let __set_right = {right.code}; "
            f"__set_left.{operation}(&__set_right).cloned().collect::<std::collections::BTreeSet<_>>() }}",
            left.type,
        )

    def record_constructor(self, name: str, node: ast.Call) -> Expr:
        fields = self.records[name]
        if len(node.args) > len(fields) or any(isinstance(arg, ast.Starred) for arg in node.args):
            self.error("invalid positional dataclass arguments", node)
        supplied = list(zip(fields, node.args))
        supplied.extend((keyword.arg, keyword.value) for keyword in node.keywords)
        values = {}
        for field, expression in supplied:
            if field is None or field not in fields or field in values:
                self.error("unknown, expanded or duplicate dataclass argument", node)
            values[field] = self.expr(expression, fields[field][0]).code
        for field, (_, default) in fields.items():
            if field not in values:
                if default is None:
                    self.error("missing required dataclass argument: " + field, node)
                values[field] = default.code
        # Rust evaluates field initializers in this supplied order, including reordered keywords.
        return Expr(
            name + " { " + ", ".join(field + ": " + value for field, value in values.items()) + " }", Type(name)
        )

    def record_definition(self, node: ast.ClassDef) -> None:
        if (
            node.bases
            or node.keywords
            or getattr(node, "type_params", [])
            or len(node.decorator_list) != 1
            or ast.unparse(node.decorator_list[0]) != "dataclass"
            or "dataclass" not in self.imports
        ):
            self.error("dataclasses require the plain @dataclass decorator and no inheritance", node)
        self.check_name(node.name, node)
        fields = {}
        saw_default = False
        for member in node.body:
            if (
                isinstance(member, ast.Expr)
                and isinstance(member.value, ast.Constant)
                and isinstance(member.value.value, str)
            ):
                continue
            if not isinstance(member, ast.AnnAssign) or not isinstance(member.target, ast.Name):
                self.error(
                    "dataclasses support annotated fields only; methods and class statements are unsupported", member
                )
            field = member.target.id
            self.check_name(field, member)
            if field in fields:
                self.error("duplicate dataclass field: " + field, member)
            typ = self.typ(member.annotation, node.name)
            if self.inline_self_reference(typ, node.name):
                self.error("recursive record fields require list, dict or variadic tuple indirection", member)
            if typ.name in {"None", "HttpServer"}:
                self.error("unsupported dataclass field type", member)
            default = None
            if member.value is not None:
                if typ.name not in {"int", "float", "bool", "str", "bytes"} or not (
                    isinstance(member.value, ast.Constant)
                    or isinstance(member.value, ast.UnaryOp)
                    and isinstance(member.value.op, ast.USub)
                    and isinstance(member.value.operand, ast.Constant)
                ):
                    self.error("dataclass defaults require scalar literals", member)
                default = self.expr(member.value, typ)
                saw_default = True
            elif saw_default:
                self.error("required dataclass fields must precede defaulted fields", member)
            fields[field] = (typ, default)
        if not fields:
            self.error("dataclasses require at least one typed field", node)
        self.records[node.name] = fields
        return  # noqa: PLR1711 - explicit return required by repository guidelines

    def inline_self_reference(self, typ: Type, name: str) -> bool:
        """Fixed tuples have inline storage; collection elements have indirect storage."""
        return typ.name == name or (
            typ.name == "tuple" and any(self.inline_self_reference(item, name) for item in typ.args)
        )

    def orderable(self, typ: Type) -> bool:
        return orderable_shape(typ.name, typ.name in self.enums, [self.orderable(item) for item in typ.args])

    def collection_mutation_in(self, node: ast.AST, name: str) -> ast.AST | None:
        prepared = getattr(node, "py2rust_collection_mutations", None)
        if prepared is not None:
            source = next((source for root, source in prepared if root == name), None)
            if source is None:
                return None
            location = ast.Constant(value=None)
            location.lineno = source.line
            location.col_offset = max(0, source.column)
            location.source_path = source.path
            return location
        return self._legacy_collection_mutation_in(node, name)

    def _legacy_collection_mutation_in(self, node: ast.AST, name: str) -> ast.Call | None:
        """Find an operation that can detach or reorder a selected collection element."""
        for operation in ast.walk(node):
            if isinstance(operation, ast.Call) and isinstance(operation.func, ast.Attribute):
                root = operation.func.value
                while isinstance(root, (ast.Attribute, ast.Subscript)):
                    root = root.value
                if (
                    isinstance(root, ast.Name)
                    and root.id == name
                    and operation.func.attr
                    in {"append", "extend", "pop", "remove", "clear", "sort", "reverse", "insert", "add"}
                ):
                    return operation
                if (
                    ast.unparse(operation.func)
                    in {"heapq.heapify", "heapq.heappush", "heapq.heappop", "heapq.heapreplace", "heapq.heappushpop"}
                    and operation.args
                    and isinstance(operation.args[0], ast.Name)
                    and operation.args[0].id == name
                ):
                    return operation
        return None

    def indexed_list_mutation(self, node: ast.Call, obj: Expr) -> Expr:
        """Mutate one list element of a named list/dictionary, without cloning it."""
        target = node.func.value
        name = target.value.id
        parent = self.locals[name]
        # Resolving the list before an argument removes it would require alias identity.
        mutation = self.collection_mutation_in(node.args[0], name)
        if mutation is not None:
            self.error("indexed list mutation argument cannot mutate its parent collection", mutation)
        expected = obj.type if node.func.attr == "extend" else obj.type.args[0]
        value = self.expr(node.args[0], expected)
        method = "extend" if node.func.attr == "extend" else "push"
        key = self.expr(target.slice, Type("int") if parent.name == "list" else parent.args[0])
        return Expr(render_indexed_list_mutation(parent.name, name, key.code, value.code, method), Type("None"))

    def nested_list_assignment(self, target: ast.Subscript, value: ast.AST) -> str:
        """Update a nested typed list in place, resolving each parent before its child index."""
        indices = []
        root = target
        while isinstance(root, ast.Subscript):
            if isinstance(root.slice, ast.Slice):
                self.error("nested list assignment requires integer indices", root.slice)
            indices.append(root.slice)
            root = root.value
        if not isinstance(root, ast.Name) or root.id not in self.locals:
            self.error("nested list assignment requires a named local list", target)
        indices.reverse()
        typ = self.locals[root.id]
        for index in indices:
            if typ.name != "list":
                self.error("nested list assignment requires lists at every index", index)
            typ = typ.args[0]
        # After resolving a parent, an inner index must not detach/reorder it.
        # Keeping references to removed objects requires Python alias identity,
        # which is outside the owned-value subset. The outer index may mutate
        # the root: no element has been selected at that point.
        for index in indices[1:]:
            mutation = self.collection_mutation_in(index, root.id)
            if mutation is not None:
                self.error("nested list assignment inner index cannot mutate its parent collection", mutation)
        replacement = self.expr(value, typ)
        keys = [self.expr(index, Type("int")).code for index in indices]
        return render_nested_assignment(root.id, keys, replacement.code)

    def string_method(self, node: ast.Call, receiver: Expr) -> Expr:
        """Adapt checked operands to portable string rules; never infer effects here."""
        rule = select_string_rule(receiver.type.name, node.func.attr, len(node.args))
        if not rule.key:
            self.error("unsupported string overload: " + node.func.attr, node)
        if rule.form == "trim":
            setup = f"let __strip_value: &str = {self.reference(receiver)}; "
            characters = "None"
            if node.args:
                argument = self.expr(node.args[0])
                if argument.type.name not in {"str", "None"}:
                    self.error("string trimming requires a string or None", node.args[0])
                setup += f"let __strip_chars = {argument.code}; "
                if argument.type.name == "str":
                    characters = "Some(&__strip_chars)"
            left = "false" if node.func.attr == "rstrip" else "true"
            right = "false" if node.func.attr == "lstrip" else "true"
            return Expr(
                f"{{ {setup}rt::{rule.target}(__strip_value, {characters}, {left}, {right}) }}",
                Type("str"),
            )
        arguments = []
        for index, node_argument in enumerate(node.args):
            expected = self.named_type(rule.argument)
            use = runtime_argument_use(RuntimeParameter(rule.argument, "shared"), node.args, index)
            place = self.argument_place(node_argument, allow_place=use.mode == "borrow") if self.optimize else None
            argument = place if place is not None and place.type == expected else self.expr(node_argument, expected)
            arguments.append(self.reference(argument))
        call = render_string_call(rule, self.reference(receiver), arguments)
        if not call:
            self.error("unsupported string rule form: " + rule.form, node)
        return Expr(
            call + ("?" if rule.fallible else ""),
            self.named_type(rule.result),
            result_call=call if rule.fallible else None,
        )

    def method(self, node: ast.Call) -> Expr:
        obj = self.expr(node.func.value)
        if self.optimize_text and obj.type.name == "str":
            use = runtime_argument_use(RuntimeParameter("str", "shared"), [node.func.value, *node.args], 0)
            place = self.local_read(node.func.value) if use.mode == "borrow" else None
            if place is not None:
                obj = place
        name = node.func.attr
        if obj.type.name == "set" and name in {"union", "intersection", "difference", "symmetric_difference"}:
            if len(node.args) != 1:
                self.error("set algebra methods require one typed set operand", node)
            other = self.expr(node.args[0], obj.type)
            return self.set_operation(obj, other, name)
        if (
            obj.type.name == "list"
            and name in {"append", "extend"}
            and len(node.args) == 1
            and isinstance(node.func.value, ast.Subscript)
            and not isinstance(node.func.value.slice, ast.Slice)
            and isinstance(node.func.value.value, ast.Name)
            and self.locals.get(node.func.value.value.id, Type("None")).name in {"list", "dict"}
        ):
            return self.indexed_list_mutation(node, obj)
        if obj.type.name == "int" and name == "to_bytes":
            return self.library_call("int_to_bytes", [node.func.value, *node.args], node)
        if obj.type.name == "str":
            return self.string_method(node, obj)
        if obj.type.name in {"bytes", "bytearray"} and name == "decode":
            encoding = "utf-8"
            if node.args:
                if (
                    len(node.args) != 1
                    or not isinstance(node.args[0], ast.Constant)
                    or not isinstance(node.args[0].value, str)
                ):
                    self.error("decode accepts one literal encoding and strict errors only", node)
                encoding = node.args[0].value.lower().replace("_", "-")
            rule = select_byte_method(obj.type.name, name, len(node.args), encoding)
            if not rule.key:
                self.error("decode supports only UTF-8, Latin-1, CP437 and ASCII", node)
            return Expr(render_byte_method(rule, obj.code, ""), self.named_type(rule.result))
        byte_rule = select_byte_method(obj.type.name, name, len(node.args), "")
        if byte_rule.key:
            argument = self.expr(node.args[0], self.named_type(byte_rule.argument)).code if byte_rule.argument else ""
            return Expr(render_byte_method(byte_rule, obj.code, argument), self.named_type(byte_rule.result))
        collection = self.collection_method(node, obj)
        if collection is not None:
            return collection
        if obj.type.name == "dict" and name == "get" and len(node.args) == 2:
            return self.dictionary_get(node, obj)
        self.error(f"unsupported method {obj.type.name}.{name}", node)

    def collection_method(self, node: ast.Call, obj: Expr) -> Expr | None:
        named = isinstance(node.func.value, ast.Name)
        rule = select_collection_method(obj.type.name, node.func.attr, len(node.args), named)
        if not rule.key:
            if (
                named
                and obj.type.name in {"list", "set"}
                and node.func.attr in {"append", "add"}
                and len(node.args) == 1
            ):
                self.error("unsupported collection method", node)
            return None
        if rule.form == "copy":
            return obj  # The checked collection read already produced its owned copy.
        if rule.key == "list.sort" and not self.orderable(obj.type.args[0]):
            self.error("list.sort requires ordered non-float elements", node)
        arguments = []
        for index, argument in enumerate(node.args):
            label = rule.first if index == 0 else rule.second
            if label == "byteslike":
                value = self.expr(argument)
                if value.type.name not in {"bytes", "bytearray"}:
                    self.error("bytearray.extend requires bytes or bytearray", node)
            else:
                expected = obj.type.args[0] if label == "item" else obj.type if label == "receiver" else Type(label)
                value = self.expr(argument, expected)
            arguments.append(value.code)
        result = obj.type.args[0] if rule.result == "item" else Type(rule.result)
        return Expr(render_collection_method(rule, node.func.value.id, arguments), result)

    def dictionary_get(self, node: ast.Call, obj: Expr) -> Expr:
        key = self.expr(node.args[0], obj.type.args[0])
        default = self.expr(node.args[1], obj.type.args[1])
        operands = [node.func.value, *node.args]
        stable = runtime_argument_use(RuntimeParameter("*", "shared"), operands, 0).mode == "borrow"
        place = self.local_read(node.func.value) if self.optimize and stable else None
        literal_key = isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str)
        empty_default = isinstance(node.args[1], ast.Constant) and node.args[1].value == ""
        style = dictionary_get_style(stable, place is not None, literal_key, empty_default)
        if style == "literal_default":
            return Expr(
                f"({place.code}).get({quote(node.args[0].value)}).cloned().unwrap_or_default()",
                obj.type.args[1],
            )
        # Defaults stay eager, including calls that fail even when the key exists.
        # Named dictionaries retain identity if an argument mutates them.
        receiver = node.func.value.id if isinstance(node.func.value, ast.Name) else "__mapping"
        value = place if style == "borrow" else obj
        binding = "" if isinstance(node.func.value, ast.Name) else f"let __mapping = {value.code}; "
        return Expr(
            f"{{ {binding}let __key = {key.code}; let __default = {default.code}; "
            f"{receiver}.get(&__key).cloned().unwrap_or(__default) }}",
            obj.type.args[1],
        )

    def block(self, statements: list, scoped: bool = True) -> list[str]:
        before = self.locals.copy()
        output = [
            self.statement(
                stmt,
                tail=self.optimize_idioms
                and (getattr(stmt, "py2rust_tail_return", False) or (not scoped and index == len(statements) - 1)),
            )
            for index, stmt in enumerate(statements)
        ]
        if scoped:
            self.locals = before
        return output

    always_returns = staticmethod(always_returns)

    def validate_try_jumps(self, statements: list, loops: int = 0) -> None:
        invalid = invalid_try_jump(statements, loops)
        if invalid is not None:
            self.error("break/continue across a try boundary is unsupported", invalid)

    def try_finally(self, node: ast.Try) -> str:
        """Keep a pending result/return until cleanup completes; cleanup may replace either."""
        if not hasattr(node, "py2rust_flow"):
            self.validate_try_jumps(node.body)
            self.validate_try_jumps(node.orelse)
            self.validate_try_jumps(node.finalbody)
            for handler in node.handlers:
                self.validate_try_jumps(handler.body)
        self.error_counter += 1
        region = self.error_counter
        active = f"__finally_error_{self.error_counter}"
        plan = plan_try(node)
        protected = plan.protected
        self.try_depth += 1
        if protected.handlers:
            body = self.statement(protected)
        else:
            body = "\n".join(self.block(protected.body))
        inherited = (
            self.active_errors[-1] + ".to_string()"
            if self.active_errors
            else '"No active exception to reraise".to_string()'
        )
        self.active_errors.append(active)
        cleanup = "\n".join(self.block(node.finalbody))
        self.active_errors.pop()
        self.try_depth -= 1
        return render_finally(
            body=body,
            cleanup=cleanup,
            result_type=self.result.rust(),
            region=region,
            inherited_error=inherited,
            nested_return=bool(self.try_depth),
            body_terminates=plan.body_terminates,
            cleanup_terminates=plan.cleanup_terminates,
            statement_terminates=plan.statement_terminates,
        )

    def statement(self, node: ast.AST, *, tail: bool = False) -> str:
        if isinstance(node, ast.Delete) and len(node.targets) == 1:
            return emit_delete(self, node)
        if isinstance(node, ast.With):
            return emit_resource(self, node)
        if isinstance(node, ast.Try):
            return emit_try(self, node)
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.value is not None:
            return emit_local(self, node)
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            return emit_assignment(self, node)
        if isinstance(node, ast.Expr):
            return self.expr(node.value).code + ";"
        if isinstance(node, ast.Return):
            expression = None if node.value is None else self.expr(node.value, self.result)
            self.record_owned_boundary(node.value)
            value = "()" if expression is None else expression.code
            if node.value is None and self.result != Type("None"):
                self.error("missing return value", node)
            call = expression.result_call if expression is not None else None
            style = return_style(
                optimize=self.optimize_idioms,
                protected=bool(self.try_depth),
                tail=tail,
                result_call=bool(call),
            )
            return render_return(value, call, style)
        if isinstance(node, ast.Raise):
            if node.exc is not None or node.cause is not None or not self.active_errors:
                self.error("raise supports only bare re-raising inside an except Exception handler", node)
            # Exceptions in this profile expose their message, not object identity
            # or traceback. Borrow the active error so a nested catch can re-raise
            # it again later without moving the original out of its handler.
            return render_reraise(self.active_errors[-1])
        if isinstance(node, ast.Assert):
            message = self.expr(node.msg, Type("str")).code if node.msg else '"".to_string()'
            return render_assert(self.expr(node.test, Type("bool")).code, message)
        if isinstance(node, ast.If):
            return str(
                render_if(
                    self.expr(node.test, Type("bool")).code,
                    self.block(node.body),
                    self.block(node.orelse),
                )
            )
        if isinstance(node, ast.While) and not node.orelse:
            return str(render_while(self.expr(node.test, Type("bool")).code, self.block(node.body)))
        if isinstance(node, ast.For) and isinstance(node.target, ast.Name) and not node.orelse:
            return emit_for(self, node)
        if isinstance(node, (ast.Break, ast.Continue, ast.Pass)):
            return {ast.Break: "break;", ast.Continue: "continue;", ast.Pass: ""}[type(node)]
        self.error(f"unsupported statement: {type(node).__name__}", node)

    def compile(self, source: str) -> str:
        return self.compile_tree(ast.parse(source))

    def compile_tree(self, tree: ast.Module) -> str:
        """Compile an AST while retaining project source locations."""
        return emit_module(self, tree)


def create_service_project(source: str, output: Path) -> None:
    """Generate a standalone Cargo project, including the runtime and locked dependencies."""
    code = ServiceCompiler().compile(source)
    write_service_project(code, output)


def main() -> int:
    from .service_cli import main as run_cli

    return run_cli()


if __name__ == "__main__":
    sys.exit(main())
