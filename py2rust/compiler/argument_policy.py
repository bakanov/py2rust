"""Runtime argument ownership contracts, independent of ASTs and Rust rendering.

Shared ABI parameters may still perform I/O or mutate resource state. These
contracts never establish purity or permit evaluation reordering.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass


@dataclass(frozen=True)
class RuntimeParameter:
    """Rust ABI ownership, independent of purity or shared-resource effects.

    Shared parameters cannot retain the caller's reference in an owned result.
    Resource state may still change; this metadata never permits call reordering.
    """

    type_name: str
    passing: str

    @classmethod
    def from_type(cls, type_name: str) -> RuntimeParameter:
        return cls(type_name, "value" if type_name in {"int", "float", "bool"} else "shared")


@dataclass(frozen=True)
class ArgumentUse:
    """A borrow is allowed only while subsequent evaluation cannot mutate its place."""

    mode: str
    reason: str
    line: int


def runtime_argument_decision(
    parameter: RuntimeParameter, stable_evaluations: Iterable[bool], line: int
) -> ArgumentUse:
    """Choose passing using this argument and all later argument evaluations.

    The caller supplies independently proved stability, in source order. Failure
    and allocation can be stable; unknown mutation or retention cannot. Scalar
    values are copied by their ABI regardless of surrounding effects.
    """
    if parameter.passing == "value":
        return ArgumentUse("value", "scalar_runtime_parameter", line)
    if not all(stable_evaluations):
        return ArgumentUse("copy", "argument_evaluation_effects_unknown", line)
    return ArgumentUse("borrow", "runtime_shared_parameter_stable_arguments", line)
