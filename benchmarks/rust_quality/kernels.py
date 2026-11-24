"""Small application kernels chosen to expose ownership and growth costs."""

# ruff: noqa: EXE002 - exFAT exposes every source file as executable
from py2rust.stdlib import Json, json_string


def payload_size(data: bytes) -> int:
    return len(data)


def read_payload(data: bytes, rounds: int) -> int:
    total: int = 0
    for iteration in range(rounds):
        total = total + payload_size(data)
    return total


def sum_values(values: list[int], rounds: int) -> int:
    total: int = 0
    for iteration in range(rounds):
        for value in values:
            total = total + value
    return total


def route(document: Json, rounds: int) -> int:
    total: int = 0
    for iteration in range(rounds):
        name: str = json_string(document["route"])
        total = total + len(name)
    return total


def build_text(count: int) -> str:
    result: str = ""
    for index in range(count):
        result = result + "message "
    return result


def arithmetic(count: int) -> int:
    result: int = 0
    for index in range(count):
        result = result + index
    return result


if __name__ == "__main__":
    print(arithmetic(10))
