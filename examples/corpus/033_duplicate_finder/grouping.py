"""Size buckets, digest buckets and byte-confirmed equivalence classes."""

from content import checkpoint, current, hash_file, same_bytes

from py2rust.stdlib import Json, json_array, json_int, json_string


def analyze(walk: Json, config: Json) -> Json:
    sizes: dict[int, list[Json]] = {}
    for row in json_array(walk["files"]):
        size: int = json_int(row["stamp"]["size"])
        if size not in sizes:
            sizes[size] = []
        sizes[size].append(row)
    buckets: dict[str, list[Json]] = {}
    errors: list[Json] = json_array(walk["errors"])
    omissions: list[Json] = json_array(walk["omissions"])
    hash_reserved: int = 0
    hashed_files: int = 0
    for size in sorted(list(sizes)):  # noqa: C414 - typed key snapshot
        if len(sizes[size]) < 2:
            continue
        for row in sizes[size]:
            name: str = json_string(row["paths"][0])
            if size > json_int(config["max_hash_bytes"]) - hash_reserved:
                omissions.append({"path": name, "reason": "hash_budget"})
                continue
            hash_reserved = hash_reserved + size
            hashed: bool = False
            try:
                row["sha256"] = hash_file(row, config)
                hashed = True
            except Exception:  # noqa: BLE001 - failed reads do not discard unrelated groups
                errors.append({"path": name, "operation": "hash"})
            if hashed:
                hashed_files = hashed_files + 1
                key: str = str(size) + ":" + json_string(row["sha256"])[: json_int(config["digest_chars"])]
                if key not in buckets:
                    buckets[key] = []
                buckets[key].append(row)
    checkpoint("hashed")
    groups: list[list[Json]] = []
    compare_reserved: int = 0
    comparisons: int = 0
    for key in sorted(list(buckets)):  # noqa: C414 - typed key snapshot
        candidates: list[Json] = buckets[key]
        if len(candidates) < 2:
            continue
        classes: list[list[Json]] = []
        failed: bool = False
        for row in candidates:
            matched: bool = False
            size: int = json_int(row["stamp"]["size"])
            for index in range(len(classes)):
                if (
                    comparisons >= json_int(config["max_comparisons"])
                    or size > (json_int(config["max_compare_bytes"]) - compare_reserved) // 2
                ):
                    omissions.append({"path": json_string(row["paths"][0]), "reason": "comparison_budget"})
                    failed = True
                    break
                comparisons = comparisons + 1
                compare_reserved = compare_reserved + 2 * size
                try:
                    matched = same_bytes(classes[index][0], row, config)
                except Exception:  # noqa: BLE001 - discard this bucket when comparison cannot be trusted
                    errors.append({"path": json_string(row["paths"][0]), "operation": "compare"})
                    failed = True
                if failed:
                    break
                if matched:
                    classes[index].append(row)
                    break
            if failed:
                break
            if not matched:
                classes.append([row])
        if not failed:
            for group in classes:
                if len(group) > 1:
                    groups.append(group)
    checkpoint("compared")
    observed: list[Json] = json_array(walk["files"])
    observed.extend(json_array(walk["directories"]))
    for row in observed:
        try:
            current(row, json_string(config["root"]))
        except Exception:  # noqa: BLE001 - changed observations make the plan non-actionable
            errors.append({"path": json_string(row["paths"][0]), "operation": "revalidate"})
    return {
        "groups": groups,
        "errors": errors,
        "omissions": omissions,
        "hashed_files": hashed_files,
        "hash_bytes_reserved": hash_reserved,
        "compare_bytes_reserved": compare_reserved,
        "comparisons": comparisons,
    }
