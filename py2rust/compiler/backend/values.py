"""Transitional emitter values; independent of the AST-based service coordinator."""

from dataclasses import dataclass

from ..ir import ValueType
from ..rules.types import render_owned_type


@dataclass(frozen=True)
class Type:
    name: str
    args: tuple = ()

    def value_type(self) -> ValueType:
        return ValueType(self.name, tuple(argument.value_type() for argument in self.args))

    def rust(self) -> str:
        if self.name == "$json_ref":
            return "&rt::Json"
        return render_owned_type(self.name, [argument.rust() for argument in self.args])


@dataclass(frozen=True)
class Expr:
    code: str
    type: Type
    borrowed: bool = False
    result_call: str | None = None
