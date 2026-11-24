"""Validate a bounded queue of JSON webhook deliveries."""

from py2rust.stdlib import (
    Json,
    env_get,
    json_dumps,
    json_float,
    json_get,
    json_int,
    json_keys,
    json_kind,
    json_parse,
    json_string,
    regex_fullmatch,
    unix_time,
)


def setting(name: str, default: int) -> int:
    return json_int(json_parse(env_get(name, str(default)), None))


def clock() -> float:
    value: str = env_get("OUTBOX_NOW", "")
    if value != "":
        return json_float(json_parse(value, None))
    return unix_time()


def validate_configuration() -> None:
    assert env_get("OUTBOX_MODE", "run") in ["run", "inspect"], "invalid mode"
    assert setting("OUTBOX_ATTEMPTS", 4) >= 1 and setting("OUTBOX_ATTEMPTS", 4) <= 20, "invalid attempt limit"
    assert setting("OUTBOX_DELAY", 2) >= 1 and setting("OUTBOX_DELAY", 2) <= 3600, "invalid retry delay"
    assert setting("OUTBOX_TIMEOUT", 2000) >= 1 and setting("OUTBOX_TIMEOUT", 2000) <= 60000, "invalid timeout"
    assert clock() >= 0.0, "clock must be nonnegative"
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def normalize_job(value: Json) -> Json:
    keys: list[str] = json_keys(value)
    assert keys == ["id", "payload", "url"] or keys == ["headers", "id", "payload", "url"], "unexpected job fields"
    identifier: str = json_string(value["id"])
    assert regex_fullmatch("[A-Za-z0-9_-]{1,100}", identifier), "invalid delivery ID"
    url: str = json_string(value["url"])
    assert len(url) <= 2048, "URL too long"
    assert regex_fullmatch("https?://[A-Za-z0-9.-]+(:[1-9][0-9]{0,4})?(/[^\\s#@]*)?", url), "invalid delivery URL"
    authority: str = url.split("//")[1].split("/")[0]
    if ":" in authority:
        port: int = json_int(json_parse(authority.split(":")[1], None))
        assert port <= 65535, "invalid URL port"
    assert regex_fullmatch("[\\x21-\\x7e]+", url), "URL must be percent-encoded ASCII"
    assert json_kind(value["payload"]) == "object", "payload must be an object"
    assert len(json_dumps(value["payload"]).encode()) <= 65536, "payload too large"
    supplied: Json = json_get(value, "headers", {})
    assert len(json_keys(supplied)) <= 20, "too many headers"
    normalized: Json = {}
    for name in json_keys(supplied):
        assert regex_fullmatch("[!#$%&'*+.^_`|~0-9a-zA-Z-]+", name), "invalid header name"
        header: str = name.lower()
        assert header not in [
            "host",
            "content-length",
            "transfer-encoding",
            "connection",
            "idempotency-key",
            "content-type",
        ], "managed header"
        assert header not in normalized, "duplicate header"
        content: str = json_string(supplied[name])
        assert len(content) <= 1024 and regex_fullmatch("[\\x20-\\x7e]*", content), "invalid header value"
        normalized[header] = content
    return {"id": identifier, "url": url, "payload": value["payload"], "headers": normalized}


def new_entry(job: Json) -> Json:
    return {
        "job": job,
        "state": "pending",
        "attempts": 0,
        "next_attempt": 0.0,
        "last_status": 0,
        "last_error": "",
        "last_attempt": 0.0,
    }


def headers_for(job: Json) -> dict[str, str]:
    headers: dict[str, str] = {"Content-Type": "application/json", "Idempotency-Key": json_string(job["id"])}
    for name in json_keys(job["headers"]):
        headers[name] = json_string(job["headers"][name])
    return headers
