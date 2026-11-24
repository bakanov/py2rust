"""A numeric five-field cron grammar with explicit sets and source-located diagnostics."""

from dataclasses import dataclass

from py2rust.stdlib import Json, regex_fullmatch


@dataclass
class Field:
    name: str
    values: set[int]
    starred: bool


@dataclass
class Expression:
    fields: list[Field]
    error: str
    field: int
    column: int


def number(text: str, low: int, high: int) -> int:
    assert regex_fullmatch("[0-9]{1,2}", text), "expected one or two ASCII digits"
    value: int = int(text)
    assert low <= value <= high, "value must be in " + str(low) + ".." + str(high)
    return value


def component(text: str, low: int, high: int) -> set[int]:
    pieces: list[str] = text.split("/")
    assert 1 <= len(pieces) <= 2, "expected at most one step separator"
    body: str = pieces[0]
    step: int = 1
    if len(pieces) == 2:
        step = number(pieces[1], 1, high - low + 1)
        assert body == "*" or "-" in body, "steps require a wildcard or range"
    first: int = low
    last: int = high
    if body != "*":
        bounds: list[str] = body.split("-")
        assert 1 <= len(bounds) <= 2, "expected a value or ascending range"
        first = number(bounds[0], low, high)
        last = first if len(bounds) == 1 else number(bounds[1], low, high)
        assert first <= last, "range is descending"
    values: set[int] = set()
    value: int = first
    while value <= last:
        values.add(value)
        value = value + step
    return values


def parse(source: str) -> Expression:
    tokens: list[str] = []
    columns: list[int] = []
    token: str = ""
    start: int = 1
    column: int = 1
    for character in source:
        if character in [" ", "\t"]:
            if token != "":
                tokens.append(token)
                columns.append(start)
                token = ""
        else:
            if token == "":
                start = column
            token = token + character
        column = column + 1
    if token != "":
        tokens.append(token)
        columns.append(start)
    if len(tokens) != 5:
        position: int = columns[5] if len(tokens) > 5 else len(source) + 1
        return Expression([], "expected five fields; found " + str(len(tokens)), min(len(tokens) + 1, 6), position)
    names: list[str] = ["minute", "hour", "day_of_month", "month", "day_of_week"]
    lows: list[int] = [0, 0, 1, 1, 0]
    highs: list[int] = [59, 23, 31, 12, 7]
    fields: list[Field] = []
    for index in range(5):
        text: str = tokens[index]
        parts: list[str] = text.split(",")
        if len(parts) > 1 and "*" in text:
            return Expression([], "wildcards cannot be combined with a list", index + 1, columns[index])
        values: set[int] = set()
        offset: int = columns[index]
        for part in parts:
            try:
                values = values | component(part, lows[index], highs[index])
            except Exception as error:  # noqa: BLE001 - source-located recoverable grammar errors
                return Expression([], names[index] + ": " + str(error), index + 1, offset)
            offset = offset + len(part) + 1
        if index == 4 and 7 in values:
            values = values - {7}
            values.add(0)
        fields.append(Field(names[index], values, text.startswith("*")))
    return Expression(fields, "", 0, 0)


def ordered(values: set[int]) -> list[int]:
    return sorted(list(values))  # noqa: C414 - subset sorting requires a typed sequence


def describe(expression: Expression) -> Json:
    fields: list[Json] = []
    for field in expression.fields:
        fields.append({"name": field.name, "values": ordered(field.values), "starred": field.starred})
    day_rule: str = ""
    if expression.error == "":
        day_rule = "and" if expression.fields[2].starred or expression.fields[4].starred else "or"
    return {
        "fields": fields,
        "day_rule": day_rule,
        "error": expression.error,
        "error_field": expression.field,
        "error_column": expression.column,
    }
