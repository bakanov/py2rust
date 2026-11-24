"""Count ordered matches and bound expansion before constructing replacements."""


from py2rust.stdlib import Json, json_int, json_string, regex_findall, regex_replace


def apply(text: str, rules: list[Json], counters: list[Json]) -> tuple[str, list[Json], int]:
    total: int = 0
    assert len(text.encode()) <= 65536, "selected field too large"
    for index in range(len(rules)):
        rule: Json = rules[index]
        pattern: str = json_string(rule["pattern"])
        replacement: str = json_string(rule["replacement"])
        count: int = 0
        removed: int = 0
        literal: bool = json_string(rule["kind"]) == "literal"
        parts: list[str] = []
        if literal:
            parts = text.split(pattern)
            count = len(parts) - 1
            removed = count * len(pattern.encode())
        else:
            matches: list[str] = regex_findall(pattern, text)
            count = len(matches)
            for matched_text in matches:
                removed = removed + len(matched_text.encode())
        assert len(text.encode()) - removed + count * len(replacement.encode()) <= 65536, "field expansion limit"
        updated: str = replacement.join(parts) if literal else regex_replace(pattern, replacement, text)
        counter: Json = counters[index]
        counter["matches"] = json_int(counter["matches"]) + count
        counter["matched_fields"] = json_int(counter["matched_fields"]) + (1 if count > 0 else 0)
        counter["changed_fields"] = json_int(counter["changed_fields"]) + (1 if updated != text else 0)
        counters[index] = counter
        total = total + count
        text = updated
    return (text, counters, total)
