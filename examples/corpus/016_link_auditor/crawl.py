"""Breadth-first static-link traversal; no external origin is requested."""

from model import fetch

from py2rust.stdlib import (
    Json,
    json_array,
    json_bool,
    json_int,
    json_is_null,
    json_string,
    url_origin,
    url_resolve,
)


def resolve(base: str, reference: str) -> Json:
    value: str = reference.strip()
    lower: str = value.lower()
    for scheme in ["mailto:", "tel:", "javascript:", "data:", "blob:", "about:"]:
        if lower.startswith(scheme):
            return {"target": "", "outcome": "ignored_scheme"}
    try:
        return {"target": url_resolve(base, value), "outcome": "resolved"}
    except Exception:  # noqa: BLE001 - malformed links belong in the report
        return {"target": "", "outcome": "invalid"}


def consider(edge: Json, depth: int, policy: Json, queue: list[str], seen: dict[str, int]) -> Json:
    target: str = json_string(edge["target"])
    if json_string(edge["outcome"]) != "resolved":
        return edge
    if url_origin(target) != json_string(policy["origin"]):
        edge["outcome"] = "external"
    elif target in seen:
        edge["outcome"] = "duplicate"
        if depth < seen[target]:
            edge["outcome"] = "shorter"
    elif depth > json_int(policy["max_depth"]):
        edge["outcome"] = "depth_limit"
    elif len(queue) >= json_int(policy["max_pages"]):
        edge["outcome"] = "page_limit"
    else:
        edge["outcome"] = "queued"
    return edge


def crawl(policy: Json) -> Json:
    start: str = json_string(policy["start"])
    queue: list[str] = [start]
    seen: dict[str, int] = {start: 0}
    processed: set[str] = set()
    pages: list[Json] = []
    edges: list[Json] = []
    truncated: bool = False
    while len(processed) < len(queue):
        # Redirects cost zero depth, so select the smallest pending distance.
        current: str = ""
        depth: int = 21
        for candidate in queue:
            if candidate not in processed and seen[candidate] < depth:
                current = candidate
                depth = seen[candidate]
        processed.add(current)
        page: Json = fetch(current, policy)
        page["depth"] = depth
        page["target"] = ""
        outgoing: list[Json] = json_array(page["links"])
        base: str = current
        next_depth: int = depth + 1
        if json_string(page["kind"]) == "redirect":
            next_depth = depth
            if json_string(page["location"]) == "":
                page["kind"] = "redirect_error"
            else:
                outgoing = [{"tag": "http", "attribute": "location", "value": page["location"]}]
        elif not json_is_null(page["base"]):
            resolved: Json = resolve(current, json_string(page["base"]))
            if json_string(resolved["outcome"]) == "resolved":
                base = json_string(resolved["target"])
            else:
                page["kind"] = "base_error"
                outgoing = []
        for item in outgoing:
            if len(edges) >= json_int(policy["max_edges"]):
                truncated = True
                break
            edge: Json = resolve(base, json_string(item["value"]))
            edge["source"] = current
            edge["reference"] = item["value"]
            edge["tag"] = item["tag"]
            edge["attribute"] = item["attribute"]
            edge = consider(edge, next_depth, policy, queue, seen)
            outcome: str = json_string(edge["outcome"])
            if outcome == "queued":
                seen[json_string(edge["target"])] = next_depth
                queue.append(json_string(edge["target"]))
            elif outcome == "shorter":
                seen[json_string(edge["target"])] = next_depth
            if json_string(page["kind"]) == "redirect":
                page["target"] = edge["target"]
                if outcome == "invalid" or outcome == "ignored_scheme":
                    page["kind"] = "redirect_error"
            edges.append(edge)
        page["links"] = []
        pages.append(page)
    return {"pages": pages, "edges": edges, "truncated": truncated}


def terminal(url: str, pages: dict[str, Json]) -> Json:
    visited: set[str] = set()
    current: str = url
    while current in pages:
        if current in visited:
            return {"url": current, "outcome": "redirect_loop", "status": 0}
        visited.add(current)
        page: Json = pages[current]
        kind: str = json_string(page["kind"])
        if kind != "redirect":
            return {"url": current, "outcome": kind, "status": page["status"]}
        current = json_string(page["target"])
        if current == "":
            return {"url": current, "outcome": "not_checked", "status": 0}
    return {"url": current, "outcome": "not_checked", "status": 0}


def report(policy: Json, data: Json) -> Json:
    pages: list[Json] = json_array(data["pages"])
    lookup: dict[str, Json] = {}
    for page in pages:
        lookup[json_string(page["url"])] = page
    failures: list[str] = ["http_error", "transport", "parse_error", "redirect_error", "redirect_loop", "base_error"]
    broken_pages: list[Json] = []
    for page in pages:
        destination: Json = terminal(json_string(page["url"]), lookup)
        if json_string(destination["outcome"]) in failures:
            broken_pages.append({"url": page["url"], "terminal": destination})
    broken_links: list[Json] = []
    counts: dict[str, int] = {}
    complete: bool = not json_bool(data["truncated"])
    for edge in json_array(data["edges"]):
        outcome: str = json_string(edge["outcome"])
        counts[outcome] = counts.get(outcome, 0) + 1
        if outcome in ["depth_limit", "page_limit"] and json_string(edge["target"]) not in lookup:
            complete = False
        if outcome == "invalid":
            broken_links.append(
                {"source": edge["source"], "reference": edge["reference"], "target": "", "reason": "invalid"}
            )
        elif json_string(edge["target"]) in lookup:
            destination: Json = terminal(json_string(edge["target"]), lookup)
            if json_string(destination["outcome"]) in failures:
                broken_links.append(
                    {
                        "source": edge["source"],
                        "reference": edge["reference"],
                        "target": edge["target"],
                        "reason": destination["outcome"],
                    }
                )
    return {
        "start": policy["start"],
        "origin": policy["origin"],
        "complete": complete,
        "pages": pages,
        "edges": data["edges"],
        "broken_pages": broken_pages,
        "broken_links": broken_links,
        "summary": {
            "pages": len(pages),
            "links": len(json_array(data["edges"])),
            "broken_pages": len(broken_pages),
            "broken_links": len(broken_links),
            "complete": complete,
            "outcomes": counts,
        },
    }
