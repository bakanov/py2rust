"""Reference for the compiler syntax exchange; parsing never executes input."""

import ast
from typing import Any

from ._python_ast import python_statement_tree


def python_syntax_tree(source: str) -> Any:
    # Share Unicode, syntax and complexity limits with the established parser API.
    python_statement_tree(source)
    source = source.removeprefix("\ufeff").replace("\r\n", "\n").replace("\r", "\n")
    module = ast.parse(source, feature_version=(3, 12))
    fields = {
        "Name": ("id",),
        "BinOp": ("op", "left", "right"),
        "UnaryOp": ("op", "operand"),
        "BoolOp": ("op", "values"),
        "Compare": ("left", "ops", "comparators"),
        "IfExp": ("test", "body", "orelse"),
        "JoinedStr": ("values",),
        "FormattedValue": ("value", "format_spec", "conversion"),
        "Call": ("func", "args", "keywords"),
        "Attribute": ("value", "attr"),
        "Subscript": ("value", "slice"),
        "Slice": ("lower", "upper", "step"),
        "List": ("elts",),
        "Tuple": ("elts",),
        "Set": ("elts",),
        "Dict": ("keys", "values"),
        "Assign": ("targets", "value"),
        "AnnAssign": ("target", "annotation", "value"),
        "AugAssign": ("target", "op", "value"),
        "Return": ("value",),
        "Expr": ("value",),
        "Assert": ("test", "msg"),
        "Delete": ("targets",),
        "For": ("target", "iter", "body", "orelse"),
        "While": ("test", "body", "orelse"),
        "If": ("test", "body", "orelse"),
        "Import": ("names",),
        "ImportFrom": ("module", "level", "names"),
        "Pass": (),
        "Break": (),
        "Continue": (),
    }

    def convert(node: Any) -> Any:
        if node is None or isinstance(node, (str, int)):
            return node
        if isinstance(node, list):
            return [convert(item) for item in node]
        if isinstance(node, (ast.operator, ast.unaryop, ast.boolop, ast.cmpop)):
            return type(node).__name__
        if isinstance(node, ast.alias):
            return {"name": node.name, "asname": node.asname or ""}
        if isinstance(node, ast.keyword):
            return {"arg": node.arg, "value": convert(node.value)}
        kind = type(node).__name__
        result = {"kind": kind, "line": node.lineno, "column": node.col_offset}
        if isinstance(node, ast.Constant):
            value = node.value
            if value is None:
                tag, text = "none", ""
            elif isinstance(value, bool):
                tag, text = "bool", str(value)
            elif isinstance(value, str):
                tag, text = "str", value
            elif isinstance(value, bytes):
                tag, text = "bytes", value.hex()
            elif isinstance(value, (int, float, complex)):
                tag, text = "number", ast.get_source_segment(source, node)
            else:
                raise ValueError(f"unsupported compiler syntax at {node.lineno}:{node.col_offset}")
            result.update(tag=tag, text=text)
        elif isinstance(node, ast.FunctionDef) and not node.type_params:
            args = node.args
            if args.posonlyargs or args.kwonlyargs or args.vararg or args.kwarg:
                raise ValueError(f"unsupported compiler syntax at {node.lineno}:{node.col_offset}")
            defaults = [None] * (len(args.args) - len(args.defaults)) + args.defaults
            result.update(
                name=node.name,
                parameters=[
                    {"name": arg.arg, "annotation": convert(arg.annotation), "default": convert(default)}
                    for arg, default in zip(args.args, defaults)
                ],
                returns=convert(node.returns),
                decorators=convert(node.decorator_list),
                body=convert(node.body),
            )
        elif isinstance(node, ast.ClassDef) and not node.type_params:
            result.update(
                name=node.name,
                bases=convert(node.bases),
                keywords=convert(node.keywords),
                decorators=convert(node.decorator_list),
                body=convert(node.body),
            )
        elif kind in fields:
            result.update({name: convert(getattr(node, name)) for name in fields[kind]})
            if kind == "ImportFrom":
                result["module"] = node.module or ""
        else:
            raise ValueError(f"unsupported compiler syntax at {node.lineno}:{node.col_offset}")
        return result

    return {"version": 1, "body": convert(module.body)}
