"""Collision-free readable identifiers for native compiler output."""


def symbol(name: str) -> str:
    parts: list[str] = ["py_"]
    for char in name:
        if char in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789":
            parts.append(char)
        elif char == "_":
            parts.append("_u")
        elif char == ".":
            parts.append("_d")
        else:
            parts.append("_x" + str(ord(char)) + "_")
    return "".join(parts)
