"""Compiler-owned control-flow proofs for exception and cleanup lowering.

These decisions use typed IR only. Rust rendering must preserve pending returns
and errors through cleanup, and reject jumps that would cross a protected closure.
"""

from dataclasses import dataclass

from . import ir

# Context scopes close these shared handles on normal and exceptional exits.
RESOURCE_TYPES = frozenset(
    {
        "FileHandle",
        "GzipReader",
        "GzipWriter",
        "LineReader",
        "HttpReader",
        "TcpListener",
        "TcpStream",
        "UdpSocket",
        "UnixListener",
        "UnixStream",
        "ProcessPool",
    }
)


class ExceptionPolicyError(ValueError):
    def __init__(self, message: str, source: ir.Source) -> None:
        self.filename = source.path
        self.lineno = source.line
        super().__init__(f"{source.path}:{source.line}: {message}")


@dataclass(frozen=True)
class TryCompletion:
    body_terminates: bool
    cleanup_terminates: bool
    statement_terminates: bool


@dataclass(frozen=True)
class StatementFlow:
    terminates: bool
    protected: TryCompletion | None = None


@dataclass(frozen=True)
class ExceptionPlan:
    statements: tuple[tuple[ir.Statement, StatementFlow], ...]

    def facts(self) -> dict[ir.Statement, StatementFlow]:
        return dict(self.statements)


def invalid_jump(statements: tuple[ir.Statement, ...], loops: int = 0) -> ir.Statement | None:
    """Find a jump escaping this closure, accounting for nested protected regions."""
    for statement in statements:
        if statement.operation == "try":
            # A nested protected body (and finally region) has its own closure.
            # A handler/else without finally executes in the enclosing region.
            if not statement.blocks[2]:
                for block in (statement.blocks[1], *(handler.body for handler in statement.handlers)):
                    invalid = invalid_jump(block, loops)
                    if invalid is not None:
                        return invalid
            continue
        if statement.operation in {"break", "continue"} and loops == 0:
            return statement
        for index, block in enumerate(statement.blocks):
            nested_loop = statement.operation in {"for", "while"} and index == 0
            invalid = invalid_jump(block, loops + nested_loop)
            if invalid is not None:
                return invalid
    return None


def analyze(modules: tuple[ir.Module, ...]) -> ExceptionPlan:
    """Plan all source regions before emission; loops conservatively may complete."""
    facts: dict[ir.Statement, StatementFlow] = {}

    def block_terminates(statements: tuple[ir.Statement, ...]) -> bool:
        # Visit all statements, even after a return, to validate protected jumps.
        outcomes = [statement_flow(statement).terminates for statement in statements]
        return any(outcomes)

    def statement_flow(statement: ir.Statement) -> StatementFlow:
        if statement in facts:
            return facts[statement]
        blocks = tuple(block_terminates(block) for block in statement.blocks)
        handlers = tuple(block_terminates(handler.body) for handler in statement.handlers)
        terminates = statement.operation in {"return", "reraise"}
        protected = None
        if statement.operation == "resource_scope":
            terminates = blocks[0]
        elif statement.operation == "if":
            terminates = all(blocks)
        elif statement.operation == "try":
            if len(handlers) > 1 or (not handlers and not statement.blocks[2]):
                raise ExceptionPolicyError(
                    "try requires at most one except Exception handler and/or finally", statement.source
                )
            regions = (statement.blocks[0],)
            if statement.blocks[2]:
                regions = (*statement.blocks, *(handler.body for handler in statement.handlers))
            for region in regions:
                invalid = invalid_jump(region)
                if invalid is not None:
                    raise ExceptionPolicyError("break/continue across a try boundary is unsupported", invalid.source)
            body_terminates = (blocks[0] or blocks[1]) and all(handlers) if handlers else blocks[0]
            terminates = blocks[2] or body_terminates
            protected = TryCompletion(body_terminates, blocks[2], terminates)
        result = StatementFlow(terminates, protected)
        facts[statement] = result
        return result

    for module in modules:
        block_terminates(module.body)
        for function in module.functions:
            block_terminates(function.body)
    return ExceptionPlan(tuple(facts.items()))
