"""The page protocol is {items: [objects with string IDs], next: absolute URL or null}."""

from py2rust.stdlib import (
    Json,
    env_get,
    json_array,
    json_dumps,
    json_equal,
    json_get,
    json_int,
    json_is_null,
    json_keys,
    json_loads,
    json_string,
    read_text,
    regex_fullmatch,
    regex_search,
)


def setting(name: str, default: int) -> int:
    return json_int(json_loads(env_get(name, str(default))))


def normalize_url(value: str) -> str:
    assert len(value) <= 2048, "URL exceeds 2048 characters"
    assert regex_fullmatch(
        "https?://[A-Za-z0-9.-]+(:[1-9][0-9]{0,4})?/[A-Za-z0-9._~!$&'()*+,;=:@/?%-]*", value
    ), "invalid URL"
    scheme: str = value.split(":")[0]
    authority: str = value.split("/")[2].lower()
    host: str = authority.split(":")[0]
    assert len(host) <= 253, "hostname too long"
    for label in host.split("."):
        assert len(label) <= 63 and regex_fullmatch("[A-Za-z0-9]([A-Za-z0-9-]*[A-Za-z0-9])?", label), "invalid hostname"
    if regex_fullmatch("[0-9.]+", host):
        assert len(host.split(".")) == 4, "IPv4 needs four octets"
        for octet in host.split("."):
            assert regex_fullmatch("0|[1-9][0-9]{0,2}", octet), "invalid IPv4 octet"
            assert json_int(json_loads(octet)) <= 255, "invalid IPv4 octet"
    if ":" in authority:
        port: int = json_int(json_loads(authority.split(":")[1]))
        assert port <= 65535, "invalid port"
        if (scheme == "http" and port == 80) or (scheme == "https" and port == 443):
            authority = host
    pieces: list[str] = value.split("%")
    for index in range(1, len(pieces)):
        assert len(pieces[index]) >= 2 and regex_fullmatch(
            "[0-9A-Fa-f]{2}", pieces[index][:2]
        ), "invalid percent escape"
    return scheme + "://" + authority + value[len(scheme) + 3 + len(value.split("/")[2]) :]


def origin(url: str) -> str:
    parts: list[str] = url.split("/")
    return parts[0] + "//" + parts[2]


def configuration() -> Json:
    text: str = read_text(env_get("HARVEST_CONFIG", "harvest.json"))
    assert len(text.encode()) <= 65536, "configuration exceeds 64 KiB"
    value: Json = json_loads(text)
    for key in json_keys(value):
        assert key in ["start", "max_pages", "max_records", "page_size", "max_body", "timeout_ms"], "unknown setting"
    start: str = normalize_url(json_string(value["start"]))
    pages: int = json_int(json_get(value, "max_pages", 100))
    records: int = json_int(json_get(value, "max_records", 10000))
    page_size: int = json_int(json_get(value, "page_size", 1000))
    maximum: int = json_int(json_get(value, "max_body", 1048576))
    timeout: int = json_int(json_get(value, "timeout_ms", 2000))
    assert pages >= 1 and pages <= 1000 and records >= 1 and records <= 10000, "invalid import limits"
    assert page_size >= 1 and page_size <= 1000, "invalid page size limit"
    assert maximum >= 1 and maximum <= 1048576 and timeout >= 1 and timeout <= 30000, "invalid HTTP bounds"
    return {
        "start": start,
        "max_pages": pages,
        "max_records": records,
        "page_size": page_size,
        "max_body": maximum,
        "timeout_ms": timeout,
    }


def record_id(value: Json) -> str:
    assert "id" in json_keys(value), "record requires an ID"
    identifier: str = json_string(value["id"])
    assert len(identifier) >= 1 and len(identifier) <= 128, "invalid record ID length"
    assert not regex_search("[\\x00-\\x1f\\x7f]", identifier), "record ID has control characters"
    assert len(json_dumps(value).encode()) <= 16384, "record exceeds 16 KiB"
    return identifier


def checked_next(value: Json, policy: Json, seen: set[str]) -> Json:
    if json_is_null(value):
        return None
    url: str = normalize_url(json_string(value))
    assert origin(url) == origin(json_string(policy["start"])), "next page has a different origin"
    assert url not in seen, "repeated next-page URL"
    return url


def accept_page(state: Json, page: Json) -> Json:
    assert json_keys(page) == ["items", "next"], "expected items and next"
    policy: Json = state["policy"]
    pages: list[Json] = json_array(state["pages"])
    current: str = json_string(state["next"])
    seen: set[str] = {current}
    for receipt in pages:
        seen.add(json_string(receipt["url"]))
    next_url: Json = checked_next(page["next"], policy, seen)
    items: list[Json] = json_array(page["items"])
    assert len(items) <= json_int(policy["page_size"]), "page exceeds record limit"
    records: list[Json] = json_array(state["records"])
    indexed: dict[str, Json] = {}
    for record in records:
        indexed[record_id(record)] = record
    added: int = 0
    for record in items:
        identifier: str = record_id(record)
        if identifier in indexed:
            assert json_equal(indexed[identifier], record), "record ID has conflicting content"
        else:
            records.append(record)
            indexed[identifier] = record
            added = added + 1
    assert len(records) <= json_int(policy["max_records"]), "import record limit reached"
    pages.append({"url": current, "next": next_url, "received": len(items), "added": added})
    assert len(pages) <= json_int(policy["max_pages"]), "page budget reached"
    return {"version": 1, "policy": policy, "records": records, "pages": pages, "next": next_url}
