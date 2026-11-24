"""Three-way decisions, subtree conflicts, and deterministic operation ordering."""

from documents import under

from py2rust.stdlib import Json, json_equal, json_string


def plan(
    source: dict[str, Json], destination: dict[str, Json], baseline: dict[str, Json], protected: list[str]
) -> Json:
    paths: set[str] = set(list(source))  # noqa: C414 - explicit typed key snapshot
    for name in destination:
        paths.add(name)
    for name in baseline:
        paths.add(name)
    ordered: list[str] = []
    for name in paths:
        ordered.append(name)  # noqa: PERF402 - explicit set-to-list conversion
    ordered.sort()
    blocked: list[str] = []
    covered: list[str] = []
    removals: dict[str, Json] = {}
    additions: dict[str, Json] = {}
    modes: dict[str, Json] = {}
    conflicts: list[Json] = []
    for name in ordered:
        skip: bool = False
        for parent in blocked:
            if under(name, parent):
                skip = True
        if skip:
            continue
        desired: Json = source.get(name, None)
        current: Json = destination.get(name, None)
        previous: Json = baseline.get(name, None)
        if json_equal(desired, current):
            continue
        safe: bool = json_equal(current, previous)
        reason: str = "both_changed"
        if previous is None:
            reason = "untracked_difference" if desired is not None else "destination_only"
        elif json_equal(desired, previous):
            reason = "destination_changed"
        destroys: bool = current is not None and json_string(current["kind"]) == "directory"
        if desired is not None and json_string(desired["kind"]) == "directory":
            destroys = False
        if safe and destroys:
            for child in protected:
                if under(child, name):
                    safe = False
                    reason = "excluded_descendant"
            for child in ordered:
                if under(child, name) and not json_equal(destination.get(child, None), baseline.get(child, None)):
                    safe = False
                    reason = "destination_subtree_changed"
        if not safe:
            conflicts.append(
                {"path": name, "reason": reason, "source": desired, "destination": current, "baseline": previous}
            )
            blocked.append(name)
            continue
        removed_parent: bool = False
        for parent in covered:
            if under(name, parent):
                removed_parent = True
        if removed_parent:
            current = None
        if current is not None:
            if (
                desired is not None
                and json_string(current["kind"]) == "directory"
                and json_string(desired["kind"]) == "directory"
            ):
                modes[name] = {"op": "chmod", "path": name, "before": current, "after": desired}
                continue
            for child in ordered:
                if under(child, name) and child in destination:
                    removals[child] = {"op": "remove", "path": child, "before": destination[child], "after": None}
            covered.append(name)
        if desired is not None:
            kind: str = json_string(desired["kind"])
            after: Json = desired
            if kind == "directory":
                after = {"kind": "directory", "mode": 448}
                if not json_equal(after, desired):
                    modes[name] = {"op": "chmod", "path": name, "before": after, "after": desired}
            additions[name] = {
                "op": "mkdir" if kind == "directory" else "copy" if kind == "file" else "symlink",
                "path": name,
                "before": None,
                "after": after,
            }
    operations: list[Json] = []
    names: list[str] = sorted(list(removals))  # noqa: C414 - explicit typed key snapshot
    for index in range(len(names) - 1, -1, -1):
        operations.append(removals[names[index]])
    for name in sorted(list(additions)):  # noqa: C414 - explicit typed key snapshot
        operations.append(additions[name])
    names = sorted(list(modes))  # noqa: C414 - explicit typed key snapshot
    for index in range(len(names) - 1, -1, -1):
        operations.append(modes[names[index]])
    return {"operations": operations, "conflicts": conflicts}
