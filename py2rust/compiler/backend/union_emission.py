"""Safe owned representations for Python unions of otherwise supported values."""

from __future__ import annotations

import ast
from typing import TYPE_CHECKING

from ..rust_text import quote
from .values import Expr, Type

if TYPE_CHECKING:
    from ..service import ServiceCompiler


def variants(typ: Type) -> tuple[Type, ...]:
    return tuple(item for item in typ.args if item.name != "None")


def nullable(typ: Type) -> bool:
    return any(item.name == "None" for item in typ.args)


def clone_any(source: str, typ: Type) -> str:
    result = 'return Err("unsupported union value".into())'
    for item in reversed(variants(typ)):
        result = (
            f"if let Some(__value) = ({source}).downcast_ref::<{item.rust()}>() {{ "
            f"Box::new(__value.clone()) as Box<dyn std::any::Any> }} else {{ {result} }}"
        )
    return result


def clone_union(expression: Expr) -> Expr:
    typ = expression.type
    if nullable(typ):
        code = (
            f"match ({expression.code}).as_ref() {{ Some(__value) => Some({clone_any('__value', typ)}), None => None }}"
        )
    else:
        code = clone_any(f"&({expression.code})", typ)
    return Expr(code, typ)


def clone_dynamic(expression: Expr) -> Expr | None:
    typ = expression.type
    if typ.name == "union":
        code = clone_union(expression).code.replace(
            'return Err("unsupported union value".into())', 'panic!("unsupported union value")'
        )
        return Expr(code, typ)
    if typ.name == "optional" and clone_dynamic(Expr("None", typ.args[0])) is not None:
        inner = clone_dynamic(Expr("__value", typ.args[0]))
        return Expr(f"({expression.code}).as_ref().map(|__value| {inner.code})", typ)
    if typ.name in {"list", "tuple_var"} and clone_dynamic(Expr("None", typ.args[0])) is not None:
        inner = clone_dynamic(Expr("__value", typ.args[0]))
        return Expr(f"({expression.code}).iter().map(|__value| {inner.code}).collect::<Vec<_>>()", typ)
    if typ.name == "dict" and clone_dynamic(Expr("None", typ.args[1])) is not None:
        inner = clone_dynamic(Expr("__value", typ.args[1]))
        return Expr(
            f"({expression.code}).iter().map(|(__key, __value)| (__key.clone(), {inner.code}))"
            ".collect::<indexmap::IndexMap<_, _>>()",
            typ,
        )
    return None


def convert_union(compiler: ServiceCompiler, expression: Expr, expected: Type, node: ast.AST) -> Expr | None:
    if expected.name == "optional" and expected.args[0].name == "union":
        allowed = variants(expected.args[0])
        if expression.type.name == "optional" and expression.type.args[0] in allowed:
            return Expr(
                f"match ({expression.code}).as_ref() {{ Some(__value) => "
                f"Some(Box::new(__value.clone()) as Box<dyn std::any::Any>), None => None }}",
                expected,
            )
        if expression.type in allowed:
            return Expr(f"Some(Box::new({expression.code}) as Box<dyn std::any::Any>)", expected)
    if expected.name == "union":
        allowed = variants(expected)
        if expression.type == Type("None") and nullable(expected):
            return Expr("None", expected)
        if expression.type.name == "optional" and expression.type.args[0] in allowed:
            if nullable(expected):
                return Expr(
                    f"match ({expression.code}).as_ref() {{ Some(__value) => "
                    f"Some(Box::new(__value.clone()) as Box<dyn std::any::Any>), None => None }}",
                    expected,
                )
            return Expr(
                f"match ({expression.code}).as_ref() {{ Some(__value) => "
                f'Box::new(__value.clone()) as Box<dyn std::any::Any>, None => return Err("expected a union value".into()) }}',
                expected,
            )
        if expression.type in allowed:
            boxed = f"Box::new({expression.code}) as Box<dyn std::any::Any>"
            return Expr(f"Some({boxed})" if nullable(expected) else boxed, expected)
        if expression.type.name == "union":
            source = (
                f'({expression.code}).as_ref().ok_or("expected a union value")?'
                if nullable(expression.type)
                else f"&({expression.code})"
            )
            cloned = clone_any(source, expected)
            return Expr(f"Some({cloned})" if nullable(expected) else cloned, expected)
        if expression.type.name == "optional" and expression.type.args[0].name == "union":
            cloned = clone_any("__value", expected)
            if nullable(expected):
                cloned = f"Some({cloned})"
            return Expr(
                f"match ({expression.code}).as_ref() {{ Some(__value) => {cloned}, "
                'None => return Err("expected a union value".into()) }',
                expected,
            )
        compiler.error(f"value of type {expression.type} is not a member of {expected}", node)
    if expression.type.name == "union" and expected.name in {"int", "float"} and variants(expression.type):
        source = (
            f'({expression.code}).as_ref().ok_or("expected a union value")?'
            if nullable(expression.type)
            else f"&({expression.code})"
        )
        if all(item.name in {"int", "float"} for item in variants(expression.type)):
            if expected.name == "float":
                return Expr(
                    f"if let Some(__value) = ({source}).downcast_ref::<f64>() {{ *__value }} "
                    f"else if let Some(__value) = ({source}).downcast_ref::<i64>() {{ *__value as f64 }} "
                    'else { return Err("numeric union mismatch".into()); }',
                    expected,
                )
            if all(item.name == "int" for item in variants(expression.type)):
                return Expr(
                    f'(*({source}).downcast_ref::<i64>().ok_or("union type mismatch")?).clone()',
                    expected,
                )
    if expression.type.name == "union" and expected in variants(expression.type):
        source = (
            f'({expression.code}).as_ref().ok_or("expected a union value")?'
            if nullable(expression.type)
            else f"&({expression.code})"
        )
        return Expr(
            f'(*({source}).downcast_ref::<{expected.rust()}>().ok_or("union type mismatch")?).clone()',
            expected,
        )
    return None


def class_name(compiler: ServiceCompiler, expression: Expr, node: ast.AST) -> Expr:
    if expression.type.name in compiler.records:
        return Expr(f"{expression.type.name.rsplit('__', 1)[-1]!r}.to_owned()", Type("str"))
    if expression.type.name != "union":
        compiler.error("type name requires a record or record union", node)
    source = (
        '__class_value.as_ref().ok_or("expected a union value")?' if nullable(expression.type) else "&__class_value"
    )
    output = 'return Err("value is not a supported record".into())'
    for item in reversed(variants(expression.type)):
        if item.name not in compiler.records:
            compiler.error("type name requires a record union", node)
        label = item.name.rsplit("__", 1)[-1]
        output = f"if ({source}).is::<{item.rust()}>() {{ {quote(label)}.to_owned() }} else {{ {output} }}"
    return Expr(f"{{ let __class_value = {expression.code}; {output} }}", Type("str"))


def identity(compiler: ServiceCompiler, expression: Expr, operation: ast.cmpop) -> Expr | None:
    if expression.type.name == "union" and nullable(expression.type):
        method = "is_none" if isinstance(operation, ast.Is) else "is_some"
        return Expr(f"({expression.code}).{method}()", Type("bool"))
    return None


def field(compiler: ServiceCompiler, expression: Expr, name: str, node: ast.AST) -> Expr | None:
    if expression.type.name != "union":
        return None
    source = (
        f'({expression.code}).as_ref().ok_or("expected a union value")?'
        if nullable(expression.type)
        else f"&({expression.code})"
    )
    selected = []
    result = None
    for item in variants(expression.type):
        if item.name not in compiler.records or name not in compiler.records[item.name]:
            continue
        field_type = compiler.records[item.name][name][0]
        if result is not None and result != field_type:
            compiler.error("union field has incompatible member types", node)
        result = field_type
        selected.append(item)
    if result is None or not selected:
        compiler.error("union members do not share this record field", node)
    suffix = "" if result.name in {"int", "float", "bool"} else ".clone()"
    output = 'Err("union has no matching record field")'
    for item in reversed(selected):
        output = (
            f"if let Some(__value) = ({source}).downcast_ref::<{item.rust()}>() {{ "
            f"Ok(__value.{name}{suffix}) }} else {{ {output} }}"
        )
    return Expr(f"({output})?", result)
