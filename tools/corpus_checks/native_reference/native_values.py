"""Models the wrapper's recursive output validation, not just the adapter body."""

from py2rust.stdlib import Json


def special(mode: str) -> float:
    if mode != "finite":
        raise ValueError("non-finite floating point result")
    return 1.25


def nested(mode: str) -> tuple[list[float], tuple[float, str]]:
    return [special(mode), -0.0], (2.5, "ok")


def document(mode: str) -> Json:
    if mode == "wide":
        raise ValueError("JSON integers must fit signed 64 bits")
    return {"items": [1, True, None, {"text": "世界"}]}


def roundtrip(value: Json) -> Json:
    return value
