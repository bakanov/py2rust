"""Rust string literals for validated Unicode scalar text.

This production renderer is also compiler input during native bootstrap. Keep it
independent of Python formatting, AST objects and the host JSON implementation.
"""


def quote_scalar_text(text: str) -> str:
    parts: list[str] = ['"']
    digits: str = "0123456789abcdef"
    for char in text:
        number: int = ord(char)
        assert number < 55296 or number > 57343, "surrogate code points are unsupported"
        escaped: str = char
        if char == '"':
            escaped = '\\"'
        elif char == "\\":
            escaped = "\\\\"
        elif char == "\n":
            escaped = "\\n"
        elif char == "\r":
            escaped = "\\r"
        elif char == "\t":
            escaped = "\\t"
        elif number < 32:
            hexadecimal: str = digits[number % 16]
            if number >= 16:
                hexadecimal = digits[number // 16] + hexadecimal
            escaped = "\\u{" + hexadecimal + "}"
        parts.append(escaped)
    parts.append('"')
    return "".join(parts)
