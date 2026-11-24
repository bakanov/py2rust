"""Deterministic reports and review-only plans; no input file is ever deleted."""

from py2rust.stdlib import (
    Json,
    json_array,
    json_bool,
    json_dumps,
    json_int,
    json_keys,
    json_string,
    sha256_digest,
    sha256_new,
    sha256_update,
)


def report(walk: Json, analysis: Json, config: Json) -> Json:
    ordered: dict[str, Json] = {}
    actions: list[Json] = []
    potential: int = 0
    for value in json_array(analysis["groups"]):
        copies: list[Json] = json_array(value)
        keeper: Json = copies[0]
        reclaim: int = 0
        removals: list[Json] = []
        for row in copies[1:]:
            aliases: list[Json] = json_array(row["paths"])
            removals.extend(aliases)
            if len(aliases) == json_int(row["stamp"]["links"]):
                reclaim = reclaim + json_int(row["stamp"]["size"])
            actions.append(
                {
                    "keep": keeper["paths"][0],
                    "remove": aliases,
                    "keep_stamp": keeper["stamp"],
                    "remove_stamp": row["stamp"],
                    "sha256": keeper["sha256"],
                }
            )
        name: str = json_string(keeper["paths"][0])
        ordered[name] = {
            "keep": name,
            "size": keeper["stamp"]["size"],
            "sha256": keeper["sha256"],
            "copies": copies,
            "redundant_paths": removals,
            "reclaimable_logical_bytes": reclaim,
        }
        potential = potential + reclaim
    groups: list[Json] = []
    for name in sorted(list(ordered)):  # noqa: C414 - typed key snapshot
        groups.append(ordered[name])
    aliases: list[Json] = []
    for row in json_array(walk["files"]):
        if len(json_array(row["paths"])) > 1:
            aliases.append({"paths": row["paths"], "links": row["stamp"]["links"], "size": row["stamp"]["size"]})
    complete: bool = len(json_array(analysis["errors"])) == 0 and len(json_array(analysis["omissions"])) == 0
    policy: Json = {}
    for key in json_keys(config):
        if key not in ["report", "plan"]:
            policy[key] = config[key]
    result: Json = {
        "version": 1,
        "root": config["root"],
        "complete": complete,
        "policy": policy,
        "groups": groups,
        "hard_links": aliases,
        "unique_files": len(json_array(walk["files"])),
        "visited_entries": walk["visited"],
        "excluded": walk["excluded"],
        "ignored": walk["ignored"],
        "errors": analysis["errors"],
        "omissions": analysis["omissions"],
        "hashed_files": analysis["hashed_files"],
        "hash_bytes_reserved": analysis["hash_bytes_reserved"],
        "compare_bytes_reserved": analysis["compare_bytes_reserved"],
        "comparisons": analysis["comparisons"],
        "reclaimable_logical_bytes": potential,
        "actions": actions if complete else [],
    }
    result["id"] = sha256_digest(sha256_update(sha256_new(), json_dumps(result).encode()))
    return result


def plan(result: Json) -> Json:
    return {
        "version": 1,
        "report_id": result["id"],
        "root": result["root"],
        "ready": json_bool(result["complete"]),
        "requires_revalidation": True,
        "actions": result["actions"],
    }
