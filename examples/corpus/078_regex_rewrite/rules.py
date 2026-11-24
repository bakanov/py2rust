"""Validate common ASCII regex syntax and apply ordered literal replacements."""

from dataclasses import dataclass

from py2rust.stdlib import (
    Json,
    json_array,
    json_keys,
    json_string,
    regex_findall,
    regex_fullmatch,
    regex_replace,
    sha256_digest,
    sha256_new,
    sha256_update,
)


@dataclass
class Rule:
    name: str
    pattern: str
    replacement: str


def digest(data: bytes) -> str:
    return sha256_digest(sha256_update(sha256_new(), data))


def validate_pattern(pattern: str) -> None:
    """Require a shared grammar; reject engine-specific escapes and class operations."""
    inside: bool = False
    first: bool = False
    negate: bool = False
    depth: int = 0
    index: int = 0
    while index < len(pattern):
        character: str = pattern[index]
        if character == "\\":
            index = index + 1
            assert index < len(pattern), "trailing regex escape"
            escaped: str = pattern[index]
            if escaped == "x":
                assert regex_fullmatch("[0-9A-Fa-f]{2}", pattern[index + 1 : index + 3]), "invalid hex escape"
                index = index + 2
            else:
                assert escaped in "AbBdDsSwWZfnrtv\\.^$*+?{}[]()|-", "unsupported regex escape"
            first = False
            negate = False
        elif inside:
            assert character != "[", "escape literal brackets inside character classes"
            assert pattern[index : index + 2] not in ["&&", "--", "~~", "||"], "class set operations are unsupported"
            if character == "]" and not first:
                inside = False
            if character != "^" or not negate:
                first = False
            negate = False
        elif character == "[":
            inside = True
            first = True
            negate = True
        elif character == "{":
            ending: int = index + 1
            while ending < len(pattern) and pattern[ending] != "}":
                ending = ending + 1
            assert ending < len(pattern), "escape literal braces"
            assert regex_fullmatch("[0-9]{1,4}(,[0-9]{0,4})?", pattern[index + 1 : ending]), "invalid repetition"
            index = ending
            assert pattern[index + 1 : index + 2] != "+", "possessive repetitions are unsupported"
        elif character == "}":
            assert False, "escape literal braces"
        elif character in "*+?":
            assert pattern[index + 1 : index + 2] not in ["+", "*"], "stacked repetitions are unsupported"
        elif character == "(":
            depth = depth + 1
            assert depth <= 32, "regex group nesting exceeds 32"
        elif character == ")":
            depth = depth - 1
            assert depth >= 0, "unbalanced regex group"
        index = index + 1
    assert depth == 0 and not inside, "unbalanced regex structure"
    return  # noqa: PLR1711 - explicit subset return


def load_rules(value: Json) -> list[Rule]:
    entries: list[Json] = json_array(value)
    assert 1 <= len(entries) <= 32, "expected 1..32 rules"
    result: list[Rule] = []
    names: set[str] = set()
    for entry in entries:
        assert sorted(json_keys(entry)) == ["name", "pattern", "replacement"], "invalid rule fields"
        name: str = json_string(entry["name"])
        assert regex_fullmatch("[A-Za-z][A-Za-z0-9_-]{0,63}", name) and name not in names, "invalid rule name"
        names.add(name)
        pattern: str = json_string(entry["pattern"])
        replacement: str = json_string(entry["replacement"])
        assert 1 <= len(pattern.encode()) <= 512 and "\x00" not in pattern, "invalid pattern size"
        for byte in pattern.encode():
            assert byte < 128, "rules require ASCII patterns"
        assert len(replacement.encode()) <= 4096 and "\x00" not in replacement, "invalid replacement"
        validate_pattern(pattern)
        # Compile and detect patterns that match an empty input before opening any output.
        regex_findall(pattern, "")
        result.append(Rule(name, pattern, replacement))
    return result


def transform(text: str, rules: list[Rule]) -> tuple[str, list[Json]]:
    events: list[Json] = []
    for rule in rules:
        matches: list[str] = regex_findall(rule.pattern, text)
        removed: int = 0
        for matched in matches:
            removed = removed + len(matched.encode())
        expected: int = len(text.encode()) - removed + len(matches) * len(rule.replacement.encode())
        assert expected <= 65536, "replacement exceeds per-file byte limit"
        changed: str = regex_replace(rule.pattern, rule.replacement, text)
        assert len(changed.encode()) == expected, "replacement byte accounting mismatch"
        events.append(
            {
                "rule": rule.name,
                "matches": len(matches),
                "bytes_before": len(text.encode()),
                "bytes_after": expected,
                "before_sha256": digest(text.encode()),
                "after_sha256": digest(changed.encode()),
                "changed": changed != text,
            }
        )
        text = changed
    return (text, events)
