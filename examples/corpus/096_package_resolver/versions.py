"""A bounded stable-version grammar: numeric triples, comparisons, caret/tilde, AND and OR."""

# ruff: noqa: I001 - compact imports
from py2rust.stdlib import (
    Json, json_array, json_int, json_string, regex_fullmatch,
)


def version(text: str) -> tuple[int, int, int]:
    assert regex_fullmatch(r"(0|[1-9][0-9]{0,9})\.(0|[1-9][0-9]{0,9})\.(0|[1-9][0-9]{0,9})", text), "invalid version"
    parts: list[str] = text.split(".")
    values: list[int] = []
    for part in parts:
        number: int = int(part)
        assert number <= 2147483647, "version component exceeds 31 bits"
        values.append(number)
    return (values[0], values[1], values[2])


def requirement(text: str) -> Json:
    assert 1 <= len(text) <= 256 and regex_fullmatch(r"[0-9 .<>=^~|*]+", text), "invalid requirement"
    alternatives: list[str] = text.split("||")
    assert len(alternatives) <= 4, "too many alternatives"
    clauses: list[Json] = []
    for alternative in alternatives:
        terms: list[str] = []
        for token in alternative.strip().split(" "):
            if token != "":
                terms.append(token)
        assert 1 <= len(terms) <= 4, "expected one to four terms"
        atoms: list[Json] = []
        for term in terms:
            if term == "*":
                continue
            operator: str = "="
            core: str = term
            for candidate in [">=", "<=", ">", "<", "=", "^", "~"]:
                if term.startswith(candidate):
                    operator = candidate
                    core = term[len(candidate) :]
                    break
            lower: tuple[int, int, int] = version(core)
            if operator in ["^", "~"]:
                upper: tuple[int, int, int] = (lower[0], lower[1] + 1, 0)
                if operator == "^":
                    if lower[0] > 0:
                        upper = (lower[0] + 1, 0, 0)
                    elif lower[1] == 0:
                        upper = (0, 0, lower[2] + 1)
                atoms.append({"op": ">=", "value": [lower[0], lower[1], lower[2]]})
                atoms.append({"op": "<", "value": [upper[0], upper[1], upper[2]]})
            else:
                atoms.append({"op": operator, "value": [lower[0], lower[1], lower[2]]})
        clauses.append(atoms)
    return {"text": text, "clauses": clauses}


def accepts(candidate: tuple[int, int, int], parsed: Json) -> bool:
    for clause in json_array(parsed["clauses"]):
        matched: bool = True
        for atom in json_array(clause):
            numbers: list[Json] = json_array(atom["value"])
            bound: tuple[int, int, int] = (json_int(numbers[0]), json_int(numbers[1]), json_int(numbers[2]))
            operator: str = json_string(atom["op"])
            valid: bool = candidate == bound
            if operator == ">":
                valid = candidate > bound
            elif operator == ">=":
                valid = candidate >= bound
            elif operator == "<":
                valid = candidate < bound
            elif operator == "<=":
                valid = candidate <= bound
            matched = matched and valid
        if matched:
            return True
    return False
