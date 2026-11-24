"""Native collection construction after typed-IR operand validation."""


def render_collection_literal(kind: str, representation: str, values: list[str]) -> str:
    if kind == "list":
        return "{ let __items: " + representation + " = vec![" + ", ".join(values) + "]; __items }"
    if kind == "tuple":
        if len(values) == 0:
            return "()"
        return "(" + ", ".join(values) + ",)"
    if kind == "dict":
        assert len(values) % 2 == 0, "dictionary needs key/value pairs"
        statements: list[str] = ["let mut __mapping: " + representation + " = indexmap::IndexMap::new();"]
        for index in range(0, len(values), 2):
            statements.append("__mapping.insert(" + values[index] + ", " + values[index + 1] + ");")
        return "{ " + " ".join(statements) + " __mapping }"
    if kind == "set":
        return "{ let __set: " + representation + " = [" + ", ".join(values) + "].into_iter().collect(); __set }"
    assert False, "unsupported collection literal"
    return ""
