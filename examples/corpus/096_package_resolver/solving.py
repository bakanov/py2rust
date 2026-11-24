"""Deterministic finite-domain search, explicit branch conflicts and independent lock closure checks."""

# ruff: noqa: I001, C414 - compact imports and explicit typed lists for sorted
from versions import accepts, version
from py2rust.stdlib import (
    Json, json_array, json_keys, json_string,
)


def constraints(packages: Json, roots: Json, choices: dict[str, str]) -> dict[str, list[Json]]:
    # Rebuild incoming requirements so sibling search branches never share mutable constraints.
    requests: list[Json] = [{"from": "root", "dependencies": roots}]
    for name in sorted(list(choices)):
        requests.append({"from": name + "@" + choices[name], "dependencies": packages[name]["releases"][choices[name]]})
    result: dict[str, list[Json]] = {}
    for request in requests:
        for name in sorted(json_keys(request["dependencies"])):
            if name not in result:
                result[name] = []
            parsed: Json = request["dependencies"][name]
            result[name].append({"from": request["from"], "range": parsed["text"], "clauses": parsed["clauses"]})
    return result


def domain(packages: Json, name: str, required: list[Json]) -> list[str]:
    matches: list[str] = []
    if name in json_keys(packages):
        for item in json_array(packages[name]["order"]):
            text: str = json_string(item)
            candidate: tuple[int, int, int] = version(text)
            allowed: bool = True
            for constraint in required:
                allowed = allowed and accepts(candidate, constraint)
            if allowed:
                matches.append(text)
    return matches


def conflict(packages: Json, name: str, required: list[Json], choices: dict[str, str], allowed: list[str]) -> Json:
    rejected: list[Json] = []
    sources: list[Json] = []
    for constraint in required:
        sources.append({"from": constraint["from"], "range": constraint["range"]})
    if name in json_keys(packages):
        for item in json_array(packages[name]["order"]):
            text: str = json_string(item)
            failed: list[int] = []
            for index in range(len(required)):
                if not accepts(version(text), required[index]):
                    failed.append(index)
            if len(failed) > 0:
                rejected.append({"version": text, "requirements": failed})
    reason: str = "selected_version" if name in choices else "no_version"
    if name not in json_keys(packages):
        reason = "missing_package"
    return {
        "package": name,
        "reason": reason,
        "choices": choices,
        "requirements": sources,
        "admissible": allowed,
        "rejected": rejected,
    }


def solve(packages: Json, roots: Json, limit: int, retained: int) -> Json:
    pending: list[dict[str, str]] = [{}]
    visited: int = 0
    failed: int = 0
    trace: list[Json] = []
    solution: dict[str, str] = {}
    status: str = "unsatisfiable"
    while len(pending) > 0:
        if visited == limit:
            status = "budget_exhausted"
            break
        choices: dict[str, str] = pending.pop()
        visited = visited + 1
        required: dict[str, list[Json]] = constraints(packages, roots, choices)
        selected: str = ""
        options: list[str] = []
        broken: bool = False
        for name in sorted(list(required)):
            allowed: list[str] = domain(packages, name, required[name])
            if len(allowed) == 0 or (name in choices and choices[name] not in allowed):
                failed = failed + 1
                if len(trace) < retained:
                    trace.append(conflict(packages, name, required[name], choices, allowed))
                broken = True
                break
            # The smallest domain wins; the sorted traversal breaks ties by package name.
            if name not in choices and (selected == "" or len(allowed) < len(options)):
                selected = name
                options = allowed
        if broken:
            continue
        if selected == "":
            status = "resolved"
            solution = choices
            break
        # Ascending pushes put the greatest numeric version at the top of the DFS stack.
        for candidate in options:
            branch: dict[str, str] = choices.copy()
            branch[selected] = candidate
            pending.append(branch)
    next_state: Json = None
    if status == "budget_exhausted":
        next_state = pending[-1]
    return {
        "status": status,
        "selected": solution,
        "statistics": {
            "states": visited,
            "conflicts": failed,
            "recorded_conflicts": len(trace),
            "pending_states": len(pending),
        },
        "conflicts": trace,
        "next_state": next_state,
    }


def verify(packages: Json, roots: Json, choices: dict[str, str]) -> list[Json]:
    errors: list[Json] = []
    for name in sorted(list(choices)):
        if name not in json_keys(packages) or choices[name] not in json_keys(packages[name]["releases"]):
            errors.append({"kind": "unknown_release", "package": name, "version": choices[name]})
    if len(errors) > 0:
        return errors
    required: dict[str, list[Json]] = constraints(packages, roots, choices)
    for name in sorted(list(required)):
        if name not in choices:
            errors.append({"kind": "missing_package", "package": name})
        elif choices[name] not in domain(packages, name, required[name]):
            errors.append({"kind": "constraint", "package": name})
    reachable: set[str] = set()
    pending: list[str] = sorted(json_keys(roots))
    while len(pending) > 0:
        name: str = pending.pop()
        if name in reachable:
            continue
        reachable.add(name)
        if name in choices:
            pending.extend(json_keys(packages[name]["releases"][choices[name]]))
    for name in sorted(list(choices)):
        if name not in reachable:
            errors.append({"kind": "unreachable_package", "package": name})
    return errors
