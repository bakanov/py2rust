"""Partition normalized source into typed tokens, retaining malformed text as diagnostics."""

from dataclasses import dataclass
from enum import Enum

from py2rust.stdlib import Json, regex_fullmatch


class Kind(Enum):
    SPACE = "space"
    IDENTIFIER = "identifier"
    KEYWORD = "keyword"
    NUMBER = "number"
    STRING = "string"
    COMMENT = "comment"
    PUNCTUATION = "punctuation"
    ERROR = "error"


@dataclass
class Token:
    kind: Kind
    text: str
    start: int
    end: int
    line: int
    column: int
    end_line: int
    end_column: int


@dataclass
class Highlight:
    text: str
    tokens: list[Token]
    diagnostics: list[Json]


def scan(source: str) -> Highlight:
    text: str = source.replace("\r\n", "\n").replace("\r", "\n")
    assert "\x00" not in text, "source contains NUL"
    characters: list[str] = []
    for character in text:
        characters.append(character)  # noqa: PERF402 - explicit character iteration in the typed subset
    tokens: list[Token] = []
    diagnostics: list[Json] = []
    letters: str = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ_"
    position: int = 0
    line: int = 1
    column: int = 1
    while position < len(characters):
        start: int = position
        character: str = characters[position]
        following: str = characters[position + 1] if position + 1 < len(characters) else ""
        kind: Kind = Kind.PUNCTUATION
        error: str = ""
        if character in " \t\n\f\v":
            kind = Kind.SPACE
            while position < len(characters) and characters[position] in " \t\n\f\v":
                position = position + 1
        elif character == "#":
            kind = Kind.COMMENT
            while position < len(characters) and characters[position] != "\n":
                position = position + 1
        elif character == "/" and following == "*":
            kind = Kind.COMMENT
            depth: int = 1
            position = position + 2
            while position < len(characters) and depth > 0:
                pair: str = characters[position]
                if position + 1 < len(characters):
                    pair = pair + characters[position + 1]
                if pair == "/*":
                    depth = depth + 1
                    assert depth <= 8, "comment nesting exceeds 8"
                    position = position + 2
                elif pair == "*/":
                    depth = depth - 1
                    position = position + 2
                else:
                    position = position + 1
            if depth != 0:
                error = "unterminated block comment"
        elif character in ["'", '"']:
            kind = Kind.STRING
            triple: bool = (
                following == character and position + 2 < len(characters) and characters[position + 2] == character
            )
            position = position + (3 if triple else 1)
            closed: bool = False
            while position < len(characters):
                current: str = characters[position]
                if current == "\n" and not triple:
                    break
                if current == "\\":
                    position = position + 1
                    if position < len(characters) and (triple or characters[position] != "\n"):
                        position = position + 1
                elif current == character:
                    if not triple:
                        position = position + 1
                        closed = True
                        break
                    if (
                        position + 2 < len(characters)
                        and characters[position + 1] == character
                        and characters[position + 2] == character
                    ):
                        position = position + 3
                        closed = True
                        break
                    position = position + 1
                else:
                    position = position + 1
            if not closed:
                error = "unterminated string"
        elif character in letters:
            kind = Kind.IDENTIFIER
            while position < len(characters) and characters[position] in letters + "0123456789":
                position = position + 1
        elif character in "0123456789":
            kind = Kind.NUMBER
            position = position + 1
            while position < len(characters):
                current: str = characters[position]
                if current in "0123456789.eE" or (current in "+-" and characters[position - 1] in "eE"):
                    position = position + 1
                else:
                    break
        else:
            position = position + 1
            if character not in "{}[]():=,;.+-*/":
                error = "unexpected character"
        value: str = "".join(characters[start:position])
        if kind == Kind.IDENTIFIER and value in ["true", "false", "null"]:
            kind = Kind.KEYWORD
        if kind == Kind.NUMBER and not regex_fullmatch(r"[0-9]+(\.[0-9]+)?([eE][+-]?[0-9]+)?", value):
            error = "invalid number"
        if error != "":
            kind = Kind.ERROR
            diagnostics.append({"token": len(tokens), "line": line, "column": column, "message": error})
        end_line: int = line
        end_column: int = column
        for character in value:
            if character == "\n":
                end_line = end_line + 1
                end_column = 1
            else:
                end_column = end_column + 1
        tokens.append(Token(kind, value, start, position, line, column, end_line, end_column))
        assert len(tokens) <= 8192, "source exceeds 8192 tokens"
        line = end_line
        column = end_column
    return Highlight(text, tokens, diagnostics)


def describe(highlight: Highlight) -> Json:
    tokens: list[Json] = []
    for token in highlight.tokens:
        tokens.append(
            {
                "kind": token.kind.value,
                "text": token.text,
                "start": token.start,
                "end": token.end,
                "line": token.line,
                "column": token.column,
                "end_line": token.end_line,
                "end_column": token.end_column,
            }
        )
    return {"tokens": tokens, "diagnostics": highlight.diagnostics, "lines": len(highlight.text.split("\n"))}
