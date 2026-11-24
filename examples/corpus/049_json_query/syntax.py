"""Bounded UTF-8 query tokens and escaped field paths, with byte/line/column diagnostics."""

from dataclasses import dataclass

from py2rust.stdlib import Json, json_kind, json_loads, json_string, regex_fullmatch


@dataclass
class Token:
    text: str
    value: Json
    literal: bool
    position: int


def fail(query: str, position: int, message: str) -> None:
    prefix: str = query.encode()[:position].decode()
    lines: list[str] = prefix.split("\n")
    assert False, (
        "byte " + str(position) + ", line " + str(len(lines)) + ", column " + str(len(lines[-1]) + 1) + ": " + message
    )
    return  # noqa: PLR1711 - explicit returns follow repository guidelines


def lex(query: str) -> list[Token]:
    data: bytes = query.encode()
    assert len(data) <= 8192, "query exceeds 8192 UTF-8 bytes"
    tokens: list[Token] = []
    position: int = 0
    while position < len(data):
        char: bytes = data[position : position + 1]
        if b" \t\r\n".find(char) >= 0:
            position = position + 1
            continue
        start: int = position
        literal: bool = b'"[{0123456789-'.find(char) >= 0
        if b'"[{'.find(char) >= 0:
            depth: int = 0
            quoted: bool = False
            escaped: bool = False
            while position < len(data):
                char = data[position : position + 1]
                position = position + 1
                if quoted:
                    if escaped:
                        escaped = False
                    elif char == b"\\":
                        escaped = True
                    elif char == b'"':
                        quoted = False
                        if depth == 0:
                            break
                elif char == b'"':
                    quoted = True
                elif char in [b"[", b"{"]:
                    depth = depth + 1
                    if depth > 16:
                        fail(query, start, "literal nesting exceeds 16")
                elif char in [b"]", b"}"]:
                    depth = depth - 1
                    if depth == 0:
                        break
            if quoted or depth != 0:
                fail(query, start, "unterminated JSON literal")
        elif b",|()<>!=".find(char) >= 0:
            position = position + 1
            if b"<>!=".find(char) >= 0 and data[position : position + 1] == b"=":
                position = position + 1
        else:
            while position < len(data) and b" \t\r\n,|()<>!=".find(data[position : position + 1]) < 0:
                position = position + 1
        text: str = data[start:position].decode()
        literal = literal or text in ["true", "false", "null"]
        value: Json = None
        if literal:
            try:
                value = json_loads(text)
            except Exception:  # noqa: BLE001 - invalid literals need query source positions
                fail(query, start, "invalid JSON literal")
        tokens.append(Token(text, value, literal, start))
        if len(tokens) > 512:
            fail(query, start, "query exceeds 512 tokens")
    tokens.append(Token("", None, False, len(data)))
    return tokens


def field(query: str, token: Token) -> Json:
    if not token.literal or json_kind(token.value) != "string":
        fail(query, token.position, "expected a quoted field path")
    path: str = json_string(token.value)
    if (
        len(path.encode()) > 1024
        or (path != "" and not path.startswith("/"))
        or not regex_fullmatch("([^~]|~[01])*", path)
    ):
        fail(query, token.position, "invalid field path")
    parts: list[str] = []
    if path != "":
        for part in path[1:].split("/"):
            parts.append(part.replace("~1", "/").replace("~0", "~"))
    if len(parts) > 16:
        fail(query, token.position, "field path exceeds 16 levels")
    return {"path": path, "parts": parts, "position": token.position}
