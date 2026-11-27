"""Compiler-owned typed IR. No mypy objects or Rust source belong in these nodes."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Source:
    path: str
    line: int
    column: int


@dataclass(frozen=True)
class ValueType:
    name: str
    arguments: tuple[ValueType, ...] = ()


@dataclass(frozen=True)
class Expression:
    operation: str
    type: ValueType
    source: Source
    operands: tuple[Expression, ...] = ()
    value: str | bytes | int | float | bool | None = None
    operators: tuple[str, ...] = ()


@dataclass(frozen=True)
class Handler:
    exception: str
    binding: str | None
    body: tuple[Statement, ...]
    source: Source


@dataclass(frozen=True)
class Statement:
    operation: str
    source: Source
    expressions: tuple[Expression, ...] = ()
    blocks: tuple[tuple[Statement, ...], ...] = ()
    target: str | None = None
    target_type: ValueType | None = None
    handlers: tuple[Handler, ...] = ()
    declaration: bool = False


@dataclass(frozen=True)
class Parameter:
    name: str
    type: ValueType


@dataclass(frozen=True)
class Function:
    name: str
    parameters: tuple[Parameter, ...]
    result: ValueType
    body: tuple[Statement, ...]
    source: Source
    defaults: tuple[Expression, ...] = ()


@dataclass(frozen=True)
class Field:
    name: str
    type: ValueType
    source: Source
    default: Expression | None = None


@dataclass(frozen=True)
class Record:
    name: str
    fields: tuple[Field, ...]
    source: Source


@dataclass(frozen=True)
class Enum:
    name: str
    members: tuple[tuple[str, Expression], ...]
    source: Source


@dataclass(frozen=True)
class Module:
    name: str
    functions: tuple[Function, ...]
    body: tuple[Statement, ...] = ()
    records: tuple[Record, ...] = ()
    enums: tuple[Enum, ...] = ()
