"""Tokenize decimal arithmetic and ASCII variable names with one-based source columns."""

from dataclasses import dataclass


@dataclass
class Token:
    kind: str
    text: str
    column: int


def location(column: int) -> str:
    return "column " + str(column) + ": "


def identifier(name: str) -> bool:
    letters: str = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ_"
    if name == "" or len(name) > 64 or name[0] not in letters:
        return False
    for character in name:
        if character not in letters + "0123456789":
            return False
    return True


def tokenize(text: str) -> list[Token]:
    assert len(text.encode()) <= 4096, "expression exceeds 4096 bytes"
    tokens: list[Token] = []
    position: int = 0
    while position < len(text):
        character: str = text[position]
        start: int = position
        if character in " \t\r":
            position = position + 1
            continue
        if character == "#":
            break
        if character in "0123456789.":
            position = position + 1
            while position < len(text):
                current: str = text[position]
                if current in "0123456789.eE" or (current in "+-" and text[position - 1] in "eE"):
                    position = position + 1
                else:
                    break
            tokens.append(Token("number", text[start:position], start + 1))
        elif character in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ_":
            position = position + 1
            while (
                position < len(text)
                and text[position] in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ_0123456789"
            ):
                position = position + 1
            name: str = text[start:position]
            assert identifier(name), location(start + 1) + "invalid variable name"
            tokens.append(Token("name", name, start + 1))
        else:
            assert character in "+-*/%()=", location(start + 1) + "unexpected character"
            position = position + 1
            if character == "/" and position < len(text) and text[position] == "/":
                character = "//"
                position = position + 1
            tokens.append(Token("operator", character, start + 1))
        assert len(tokens) <= 512, "expression exceeds 512 tokens"
    tokens.append(Token("end", "", len(text) + 1))
    return tokens
