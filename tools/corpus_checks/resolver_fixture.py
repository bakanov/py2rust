"""Independent exhaustive assignment and interval oracles; never import the resolver application."""

from __future__ import annotations

import itertools
import random
import re
from collections import defaultdict

INDEX = {
    "version": 1,
    "packages": {
        "Client": [
            {"version": "2.0.0", "dependencies": {"Http": "^2.0.0"}},
            {"version": "1.0.0", "dependencies": {"Http": "^1.0.0"}},
        ],
        "Extension": [
            {"version": "2.0.0", "dependencies": {"Http": "<2.0.0"}},
            {"version": "1.0.0", "dependencies": {"Http": "<2.0.0"}},
        ],
        "Http": [{"version": "2.0.0", "dependencies": {}}, {"version": "1.5.0", "dependencies": {}}],
        "Unused": [{"version": "1.0.0", "dependencies": {"Missing": "*"}}],
    },
}
ROOTS = {"Client": "*", "Extension": "*"}
SELECTED = {"Client": "1.0.0", "Extension": "2.0.0", "Http": "1.5.0"}


def triple(text: str) -> tuple[int, ...]:
    assert re.fullmatch(r"(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)", text)
    return tuple(map(int, text.split(".")))


def matches(text: str, requirement: str) -> bool:
    candidate = triple(text)

    def term(value: str) -> bool:
        if value == "*":
            return True
        match = re.fullmatch(r"(>=|<=|>|<|=|\^|~)?([0-9]+\.[0-9]+\.[0-9]+)", value)
        assert match
        operator, raw = match.groups()
        bound = triple(raw)
        if operator == "^":
            # Equality of the compatibility prefix implements the interval independently.
            prefix = next((i + 1 for i, component in enumerate(bound) if component), 3)
            return candidate >= bound and candidate[:prefix] == bound[:prefix]
        if operator == "~":
            return candidate >= bound and candidate[:2] == bound[:2]
        return {
            None: candidate == bound,
            "=": candidate == bound,
            ">": candidate > bound,
            ">=": candidate >= bound,
            "<": candidate < bound,
            "<=": candidate <= bound,
        }[operator]

    return any(all(term(value) for value in clause.split()) for clause in requirement.split("||"))


def releases(index: dict) -> dict:
    return {
        name: {entry["version"]: entry["dependencies"] for entry in entries}
        for name, entries in index["packages"].items()
    }


def incoming(index: dict, roots: dict, choices: dict) -> dict:
    result = defaultdict(list)
    for name in sorted(roots):
        result[name].append({"from": "root", "range": roots[name]})
    packages = releases(index)
    for name, value in sorted(choices.items()):
        for dependency, requirement in sorted(packages[name][value].items()):
            result[dependency].append({"from": name + "@" + value, "range": requirement})
    return dict(result)


def valid(index: dict, roots: dict, choices: dict) -> bool:
    packages = releases(index)
    if any(value not in packages.get(name, {}) for name, value in choices.items()):
        return False
    reachable, pending = set(), list(roots)
    while pending:
        name = pending.pop()
        if name in reachable:
            continue
        reachable.add(name)
        if name not in choices:
            return False
        pending.extend(packages[name][choices[name]])
    if reachable != set(choices):
        return False
    for name, constraints in incoming(index, roots, choices).items():
        if name not in choices or not all(matches(choices[name], row["range"]) for row in constraints):
            return False
    return True


def solutions(index: dict, roots: dict) -> list[dict]:
    packages = releases(index)
    names = sorted(packages)
    result = []
    for values in itertools.product(*[[None, *packages[name]] for name in names]):
        choices = {name: value for name, value in zip(names, values, strict=True) if value is not None}
        if valid(index, roots, choices):
            result.append(choices)
    return result


def witness(index: dict, roots: dict, item: dict) -> None:
    packages, choices = releases(index), item["choices"]
    required = incoming(index, roots, choices)[item["package"]]
    name = item["package"]
    assert item["requirements"] == required
    allowed, rejected = [], []
    for value in sorted(packages.get(name, {}), key=triple):
        failed = [i for i, row in enumerate(required) if not matches(value, row["range"])]
        if failed:
            rejected.append({"version": value, "requirements": failed})
        else:
            allowed.append(value)
    assert not allowed or name in choices and choices[name] not in allowed
    assert item["admissible"] == allowed and item["rejected"] == rejected
    reason = "missing_package" if name not in packages else "selected_version" if name in choices else "no_version"
    assert item["reason"] == reason
    return  # noqa: PLR1711


def repositories() -> list[tuple[dict, dict]]:
    randomizer = random.Random(96024)
    requirements = ["*", "1.0.0", "2.0.0", "^1.0.0", "<2.0.0", ">=1.0.0 <3.0.0", "3.0.0 || 1.0.0"]
    result = []
    for _ in range(120):
        names = ["A", "B", "C", "D"][: randomizer.randint(1, 4)]
        packages = {}
        for name in names:
            entries = []
            for major in range(1, randomizer.randint(0, 3) + 1):
                dependencies = {
                    other: randomizer.choice(requirements) for other in [*names, "Missing"] if randomizer.random() < 0.2
                }
                entries.append({"version": f"{major}.0.0", "dependencies": dependencies})
            packages[name] = entries
        roots = {name: randomizer.choice(requirements) for name in names if randomizer.random() < 0.7}
        result.append(({"version": 1, "packages": packages}, roots))
    return result


def binary_tree(count: int) -> tuple[dict, dict]:
    packages = {f"P{i:02}": [{"version": f"{v}.0.0", "dependencies": {}} for v in [1, 2]] for i in range(count)}
    packages["ZZ"] = [{"version": f"{v}.0.0", "dependencies": {"Missing": "*"}} for v in [1, 2]]
    return {"version": 1, "packages": packages}, {name: "*" for name in packages}
