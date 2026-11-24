"""Crawl limits, protected report paths and bounded HTTP/HTML responses."""

from py2rust.stdlib import (
    Json,
    WebResponse,
    env_get,
    html_links,
    json_get,
    json_int,
    json_keys,
    json_loads,
    json_string,
    path_exists,
    path_is_symlink,
    path_join,
    path_name,
    path_parent,
    path_resolve,
    path_same,
    read_text,
    url_origin,
    url_resolve,
    web_request,
)


def configuration() -> Json:
    config: str = env_get("AUDIT_CONFIG", "audit.json")
    text: str = read_text(config)
    assert len(text.encode()) <= 65536, "configuration exceeds 64 KiB"
    value: Json = json_loads(text)
    for key in json_keys(value):
        assert key in [
            "start",
            "max_depth",
            "max_pages",
            "max_links",
            "max_edges",
            "max_body",
            "timeout_ms",
        ], "unknown setting"
    start: str = url_resolve(json_string(value["start"]), "")
    depth: int = json_int(json_get(value, "max_depth", 3))
    pages: int = json_int(json_get(value, "max_pages", 100))
    links: int = json_int(json_get(value, "max_links", 1000))
    edges: int = json_int(json_get(value, "max_edges", 5000))
    body: int = json_int(json_get(value, "max_body", 262144))
    timeout: int = json_int(json_get(value, "timeout_ms", 2000))
    assert depth >= 0 and depth <= 20 and pages >= 1 and pages <= 500, "invalid crawl budget"
    assert links >= 1 and links <= 2000 and edges >= 1 and edges <= 50000, "invalid link budget"
    assert body >= 1 and body <= 1048576 and timeout >= 1 and timeout <= 30000, "invalid HTTP bounds"
    report: str = env_get("AUDIT_REPORT", "audit-report.json")
    report = path_join(path_resolve(path_parent(report)), path_name(report))
    assert not path_is_symlink(report), "report must not be a symlink"
    assert path_resolve(config) != report, "report overlaps configuration"
    if path_exists(report):
        assert not path_same(config, report), "report aliases configuration"
    return {
        "start": start,
        "origin": url_origin(start),
        "max_depth": depth,
        "max_pages": pages,
        "max_links": links,
        "max_edges": edges,
        "max_body": body,
        "timeout_ms": timeout,
        "report": report,
    }


def fetch(url: str, policy: Json) -> Json:
    result: Json = {"url": url, "status": 0, "kind": "transport", "base": None, "links": [], "location": ""}
    headers: dict[str, str] = {"Accept-Encoding": "identity"}
    try:
        response: WebResponse = web_request(
            "GET", url, b"", headers, json_int(policy["timeout_ms"]), json_int(policy["max_body"])
        )
        result["status"] = response.status
        if response.status in [301, 302, 303, 307, 308]:
            result["location"] = response.headers.get("location", "").strip()
            result["kind"] = "redirect"
        elif response.status < 200 or response.status >= 300:
            result["kind"] = "http_error"
        else:
            result["kind"] = "asset"
            content_type: str = response.headers.get("content-type", "").split(";")[0].strip().lower()
            if content_type == "text/html":
                result["kind"] = "parse_error"
                encoding: str = response.headers.get("content-encoding", "identity").lower()
                assert encoding == "identity", "encoded HTML is not supported"
                # This UTF-8 profile does not guess a charset from the document.
                for parameter in response.headers.get("content-type", "").lower().split(";"):
                    fields: list[str] = parameter.strip().split("=")
                    if fields[0].strip() == "charset":
                        assert len(fields) == 2, "invalid charset parameter"
                        assert fields[1].strip() in ["utf-8", '"utf-8"'], "HTML must be UTF-8"
                parsed: Json = html_links(response.body.decode(), json_int(policy["max_links"]))
                result["base"] = parsed["base"]
                result["links"] = parsed["links"]
                result["kind"] = "html"
    except Exception:  # noqa: BLE001 - continue the audit after a failed page
        return result
    return result
