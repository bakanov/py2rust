"""Tokenize the automation language with one-based Unicode source coordinates."""

from dataclasses import dataclass


@dataclass
class Token:
    kind: str
    text: str
    location: str


def tokenize(source: str) -> list[Token]:
    assert len(source.encode()) <= 32768 and "\x00" not in source, "invalid program size or NUL"
    source = source.replace("\r\n", "\n").replace("\r", "\n")
    tokens: list[Token] = []
    letters: str = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ_"
    index: int = 0
    line: int = 1
    column: int = 1
    while index < len(source):
        char: str = source[index]
        location: str = str(line) + ":" + str(column) + ": "
        if char in " \t":
            index = index + 1
            column = column + 1
            continue
        if char == "#":
            while index < len(source) and source[index] != "\n":
                index = index + 1
                column = column + 1
            continue
        start: int = index
        kind: str = "symbol"
        if char in letters or char in "0123456789":
            kind = "name" if char in letters else "number"
            allowed: str = letters + "0123456789" if kind == "name" else "0123456789"
            while index < len(source) and source[index] in allowed:
                index = index + 1
            assert index - start <= (64 if kind == "name" else 19), location + "token too long"
        else:
            assert char in "\n;{}()+-*/%=!<>", location + "unexpected character"
            index = index + 1
            if source[start : index + 1] in ["//", "==", "!=", "<=", ">="]:
                index = index + 1
            assert source[start:index] not in ["/", "!"], location + "unsupported operator"
        tokens.append(Token(kind, source[start:index], location))
        if char == "\n":
            line = line + 1
            column = 1
        else:
            column = column + index - start
        assert len(tokens) <= 4096, location + "program exceeds 4096 tokens"
    tokens.append(Token("end", "", str(line) + ":" + str(column) + ": "))
    return tokens
