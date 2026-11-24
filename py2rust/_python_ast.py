"""Bounded CPython reference for the flat statement-tree projection."""

# ruff: noqa: PLR1711 - explicit repository return
import ast
import io
import re
import token
import tokenize
import unicodedata
import warnings
from typing import Any


def python_statement_tree(source: str) -> Any:
    if unicodedata.unidata_version != "15.1.0":
        raise ValueError("Python statement parsing requires the Unicode 15.1 reference (Python 3.13)")
    try:
        length = len(source.encode())
    except UnicodeError as error:
        raise ValueError("invalid Python source bytes") from error
    if length > 131072 or "\0" in source:
        raise ValueError("invalid Python source bytes")
    source = source.removeprefix("\ufeff").replace("\r\n", "\n").replace("\r", "\n")
    lines = source.splitlines(keepends=True)
    rows = []
    count = brackets = indent = 0
    raw_fstrings: list[bool] = []
    try:
        for item in tokenize.generate_tokens(io.StringIO(source).readline):
            if item.type == token.FSTRING_START:
                raw_fstrings.append("r" in item.string.lower())
            elif item.type == token.FSTRING_END:
                raw_fstrings.pop()
            literal = item.type == token.STRING and not re.match("(?i)[rub]*[rb]", item.string)
            literal |= item.type == token.FSTRING_MIDDLE and not raw_fstrings[-1]
            if literal:
                for match in re.finditer(r"\\(?:N\{([^}]+)\}|.)", item.string, re.DOTALL):
                    if match[1] is not None:
                        try:
                            named = unicodedata.lookup(match[1])
                        except KeyError:
                            continue  # The grammar parser supplies the syntax diagnostic.
                        if len(named) != 1:
                            raise ValueError("python syntax error: named sequences are unsupported")
            if item.type in [token.ENDMARKER, token.ENCODING, token.NL, token.COMMENT]:
                continue
            count += 1
            if item.type == token.INDENT:
                indent += 1
            elif item.type == token.DEDENT:
                indent -= 1
            if item.type == token.OP:
                if item.string in ["(", "[", "{"]:
                    brackets += 1
                elif item.string in [")", "]", "}"]:
                    brackets -= 1
            if count > 16384 or brackets > 128 or indent > 64:
                raise ValueError("python token/nesting limit exceeded")
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", SyntaxWarning)
            warnings.simplefilter("ignore", DeprecationWarning)
            module = ast.parse(source, feature_version=(3, 12))
    except RecursionError as error:
        raise ValueError("python expression complexity limit exceeded") from error
    except (SyntaxError, tokenize.TokenError) as error:
        if isinstance(error, SyntaxError):
            line = error.lineno or 1
            char = max(0, (error.offset or 1) - 1)
        else:
            line, char = error.args[1]
        column = len(lines[line - 1][:char].encode()) if line <= len(lines) else 0
        raise ValueError(f"python syntax error at {line}:{column}") from error
    pending = [(module, 0, False)]
    while pending:
        node, depth, skip_expr = pending.pop()
        if isinstance(node, ast.expr) and not isinstance(node, ast.FormattedValue) and not skip_expr:
            depth += 1
        if depth > 128:
            raise ValueError("python expression complexity limit exceeded")
        if (
            isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and any(0xD800 <= ord(char) <= 0xDFFF for char in node.value)
        ):
            raise ValueError("python strings require Unicode scalar values")
        if isinstance(node, ast.arguments):
            names = [arg.arg for arg in [*node.posonlyargs, *node.args, *node.kwonlyargs]]
            names += [arg.arg for arg in [node.vararg, node.kwarg] if arg is not None]
            if len(names) != len(set(names)):
                raise ValueError("python syntax error: duplicate parameter")
        if isinstance(node, ast.Call):
            names = [kw.arg for kw in node.keywords if kw.arg is not None]
            if len(names) != len(set(names)):
                raise ValueError("python syntax error: duplicate keyword")
        for child in ast.iter_child_nodes(node):
            skip = isinstance(node, ast.JoinedStr) and isinstance(child, ast.Constant)
            skip |= isinstance(node, ast.FormattedValue) and child is node.format_spec
            pending.append((child, depth, skip))

    def location(node: ast.AST) -> dict:
        return {
            "line": node.lineno,
            "column": node.col_offset,
            "end_line": node.end_lineno,
            "end_column": node.end_col_offset,
        }

    def suite(statements: list[ast.stmt], parent: int, block: str, depth: int) -> None:
        for statement in statements:
            if depth > 64 or len(rows) >= 4096:
                raise ValueError("python statement limit exceeded")
            row = {
                **location(statement),
                "kind": type(statement).__name__,
                "parent": parent,
                "block": block,
                "name": "",
                "decorators": [],
                "names": [],
                "module": "",
                "level": 0,
                "string": None,
            }
            index = len(rows)
            rows.append(row)
            if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                row["name"] = statement.name
                row["decorators"] = [
                    {**location(value), "text": ast.get_source_segment(source, value)}
                    for value in statement.decorator_list
                ]
            if isinstance(statement, ast.TypeAlias):
                row["name"] = statement.name.id
            if isinstance(statement, (ast.Import, ast.ImportFrom)):
                row["names"] = [{"name": value.name, "asname": value.asname or ""} for value in statement.names]
            if isinstance(statement, ast.ImportFrom):
                row["module"] = statement.module or ""
                row["level"] = statement.level
            if isinstance(statement, (ast.Global, ast.Nonlocal)):
                row["names"] = [{"name": value, "asname": ""} for value in statement.names]
            if (
                isinstance(statement, ast.Expr)
                and isinstance(statement.value, ast.Constant)
                and isinstance(statement.value.value, str)
            ):
                row["string"] = statement.value.value
            suite(getattr(statement, "body", []), index, "body", depth + 1)
            for i, handler in enumerate(getattr(statement, "handlers", [])):
                suite(handler.body, index, "handlers." + str(i), depth + 1)
            for i, case in enumerate(getattr(statement, "cases", [])):
                suite(case.body, index, "cases." + str(i), depth + 1)
            suite(getattr(statement, "orelse", []), index, "orelse", depth + 1)
            suite(getattr(statement, "finalbody", []), index, "finalbody", depth + 1)
        return

    suite(module.body, -1, "body", 1)
    return {"version": 1, "nodes": rows}
