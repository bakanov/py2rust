"""Runtime ABI rendering. Shared parameters do not imply pure operations."""

from .runtime_contracts import RuntimeContract


def render_runtime_call(contract: RuntimeContract, values: list[str], types: list[str]) -> str:
    assert len(values) == len(contract.parameters), "native runtime argument count mismatch"
    statements: list[str] = []
    arguments: list[str] = []
    for index in range(len(values)):
        value: str = values[index]
        if contract.parameters[index] == "float" and types[index] == "int":
            value = "(" + value + " as f64)"
        name: str = "__runtime_argument_" + str(index)
        statements.append("let " + name + " = " + value + ";")
        arguments.append("&" + name if contract.shared[index] else name)
    call: str = "rt::" + contract.name + "(" + ", ".join(arguments) + ")"
    if contract.fallible:
        call = call + "?"
    return "{ " + " ".join(statements) + " " + call + " }"
