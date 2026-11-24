"""Deterministic counts, UTC hour buckets and request-path rankings over selected records."""

# ruff: noqa: C414 - sorting uses explicit typed list conversion

from py2rust.stdlib import Json, json_bool, json_int, json_string


def summarize(records: list[Json], top: int) -> Json:
    statuses: dict[int, int] = {}
    methods: dict[str, int] = {}
    hours: dict[str, int] = {}
    paths: dict[str, Json] = {}
    hosts: set[str] = set()
    count: int = 0
    total_bytes: int = 0
    client_errors: int = 0
    server_errors: int = 0
    first: str = ""
    last: str = ""
    for record in records:
        if not json_bool(record["selected"]):
            continue
        count = count + 1
        size: int = json_int(record["bytes"])
        assert total_bytes <= 9223372036854775807 - size, "selected byte total exceeds signed integer range"
        total_bytes = total_bytes + size
        status: int = json_int(record["status"])
        method: str = json_string(record["method"])
        timestamp: str = json_string(record["timestamp"])
        hour: str = timestamp[:13] + ":00:00.000000+00:00"
        statuses[status] = statuses.get(status, 0) + 1
        methods[method] = methods.get(method, 0) + 1
        hours[hour] = hours.get(hour, 0) + 1
        hosts.add(json_string(record["host"]))
        if first == "" or timestamp < first:
            first = timestamp
        if last == "" or timestamp > last:
            last = timestamp
        client_errors = client_errors + (1 if 400 <= status < 500 else 0)
        server_errors = server_errors + (1 if status >= 500 else 0)
        path: str = json_string(record["path"])
        row: Json = paths.get(path, {"path": path, "requests": 0, "bytes": 0, "errors": 0})
        row["requests"] = json_int(row["requests"]) + 1
        row["bytes"] = json_int(row["bytes"]) + size
        row["errors"] = json_int(row["errors"]) + (1 if status >= 400 else 0)
        paths[path] = row
    ranks: list[tuple[int, str]] = []
    for path in paths:
        ranks.append((-json_int(paths[path]["requests"]), path))
    ranked: list[Json] = []
    for rank in sorted(ranks)[:top]:
        ranked.append(paths[rank[1]])
    status_rows: list[Json] = []
    for status in sorted(list(statuses)):
        status_rows.append({"status": status, "requests": statuses[status]})
    method_rows: list[Json] = []
    for method in sorted(list(methods)):
        method_rows.append({"method": method, "requests": methods[method]})
    hour_rows: list[Json] = []
    for hour in sorted(list(hours)):
        hour_rows.append({"hour": hour, "requests": hours[hour]})
    return {
        "requests": count,
        "bytes": total_bytes,
        "client_errors": client_errors,
        "server_errors": server_errors,
        "unique_hosts": len(hosts),
        "first": first if count > 0 else None,
        "last": last if count > 0 else None,
        "statuses": status_rows,
        "methods": method_rows,
        "hours": hour_rows,
        "path_count": len(paths),
        "top_paths": ranked,
    }
