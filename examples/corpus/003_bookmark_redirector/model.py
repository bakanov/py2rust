"""Named HTTP links with explicit URL, tag and timestamp constraints."""

from py2rust.stdlib import (
    Json,
    env_get,
    json_array,
    json_float,
    json_int,
    json_keys,
    json_parse,
    json_string,
    regex_fullmatch,
    regex_search,
    unix_time,
)


def setting(name: str, default: int) -> int:
    return json_int(json_parse(env_get(name, str(default)), None))


def clock() -> float:
    value: str = env_get("BOOKMARK_NOW", "")
    if value != "":
        return json_float(json_parse(value, None))
    return unix_time()


def valid_name(name: str) -> bool:
    return regex_fullmatch("[a-z][a-z0-9_-]{0,47}", name)


def validate_url(url: str) -> None:
    assert len(url) <= 4096, "destination is too long"
    assert url.startswith("http://") or url.startswith("https://"), "expected http or https"  # noqa: PIE810 - tuple-prefix overload is outside this profile
    assert regex_fullmatch("[A-Za-z0-9._~:/?#@!$&'()*+,;=%-]+", url), "URL must use escaped ASCII characters"
    assert not regex_search("%([^0-9A-Fa-f]|[0-9A-Fa-f][^0-9A-Fa-f]|$)|%[0-9A-Fa-f]$", url), "invalid percent escape"
    rest: str = url[url.find("://") + 3 :]
    authority: str = rest.split("/")[0].split("?")[0].split("#")[0]
    assert "@" not in authority and len(authority) > 0, "credentials or empty host are not allowed"
    parts: list[str] = authority.split(":")
    assert len(parts) <= 2, "expected a DNS or IPv4 host"
    host: str = parts[0]
    assert len(host) <= 253, "host is too long"
    for label in host.split("."):
        assert regex_fullmatch("[A-Za-z0-9]([A-Za-z0-9-]{0,61}[A-Za-z0-9])?", label), "invalid host label"
    if regex_fullmatch("[0-9.]+", host):
        octets: list[str] = host.split(".")
        assert len(octets) == 4, "IPv4 address must have four octets"
        for octet in octets:
            number: int = json_int(json_parse(octet, None))
            assert number >= 0 and number <= 255, "invalid IPv4 octet"
    if len(parts) == 2:
        port: int = json_int(json_parse(parts[1], None))
        assert port >= 1 and port <= 65535, "invalid port"
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def normalize(value: Json) -> Json:
    assert json_keys(value) == ["name", "tags", "title", "url"], "unexpected bookmark fields"
    name: str = json_string(value["name"])
    title: str = json_string(value["title"]).strip()
    url: str = json_string(value["url"])
    assert valid_name(name), "invalid bookmark name"
    assert len(title) > 0 and len(title) <= 200, "invalid title length"
    assert not regex_search("[\\x00-\\x1f\\x7f]", title), "title contains control characters"
    validate_url(url)
    tags: list[str] = []
    for raw in json_array(value["tags"]):
        tag: str = json_string(raw).lower()
        assert regex_fullmatch("[a-z0-9][a-z0-9_-]{0,29}", tag), "invalid tag"
        if tag not in tags:
            tags.append(tag)
    assert len(tags) <= 10, "too many tags"
    tags.sort()
    return {"name": name, "title": title, "url": url, "tags": tags}


def validate_record(value: Json) -> Json:
    assert json_keys(value) == ["created", "name", "tags", "title", "updated", "url", "visits"], "invalid record fields"
    record: Json = normalize(
        {"name": value["name"], "title": value["title"], "url": value["url"], "tags": value["tags"]}
    )
    visits: int = json_int(value["visits"])
    created: float = json_float(value["created"])
    updated: float = json_float(value["updated"])
    assert visits >= 0 and visits <= 1000000000000, "invalid visit counter"
    assert created >= 0.0 and updated >= created, "invalid record timestamps"
    record["visits"] = visits
    record["created"] = created
    record["updated"] = updated
    return record


def configure() -> None:
    assert setting("BOOKMARK_LIMIT", 1000) >= 1 and setting("BOOKMARK_LIMIT", 1000) <= 1000, "invalid bookmark limit"
    assert setting("BOOKMARK_PORT", 8769) >= 0 and setting("BOOKMARK_PORT", 8769) <= 65535, "invalid port"
    assert clock() >= 0.0, "clock must be nonnegative"
    return  # noqa: PLR1711 - explicit return required by repository guidelines
