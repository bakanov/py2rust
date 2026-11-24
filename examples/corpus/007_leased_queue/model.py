"""Job identities, bounded leases and public receipt views."""

import hmac

from py2rust.stdlib import (
    Json,
    env_get,
    json_dumps,
    json_float,
    json_get,
    json_int,
    json_keys,
    json_parse,
    json_string,
    regex_fullmatch,
    unix_time,
)


def setting(name: str, default: int) -> int:
    return json_int(json_parse(env_get(name, str(default)), None))


def clock() -> float:
    value: str = env_get("QUEUE_NOW", "")
    if value != "":
        return json_float(json_parse(value, None))
    return unix_time()


def valid_name(value: str) -> bool:
    return regex_fullmatch("[A-Za-z0-9_-]{1,64}", value)


def valid_token(value: str) -> bool:
    return regex_fullmatch("[0-9a-f]{64}", value)


def matches(record: Json, worker: str, token: str) -> bool:
    return (
        json_string(record["worker"]) == worker
        and valid_token(token)
        and hmac.compare_digest(json_string(record["token"]).encode(), token.encode())
    )


def normalize_job(value: Json) -> Json:
    for key in json_keys(value):
        assert key in ["id", "payload", "queue", "priority", "delay"], "unexpected job field"
    identifier: str = json_string(value["id"])
    queue: str = json_string(json_get(value, "queue", "main"))
    priority: int = json_int(json_get(value, "priority", 0))
    delay: int = json_int(json_get(value, "delay", 0))
    assert valid_name(identifier) and valid_name(queue), "invalid job ID or queue"
    assert priority >= 0 and priority <= 9, "invalid priority"
    assert delay >= 0 and delay <= 86400, "invalid delay"
    assert len(json_dumps(value["payload"]).encode()) <= 16384, "payload exceeds byte limit"
    return {"id": identifier, "queue": queue, "payload": value["payload"], "priority": priority, "delay": delay}


def copy_record(record: Json) -> Json:
    copied: Json = {}
    for key in json_keys(record):
        copied[key] = record[key]
    return copied


def clear_lease(record: Json, available: float) -> Json:
    changed: Json = copy_record(record)
    changed["state"] = "pending"
    changed["worker"] = ""
    changed["token"] = ""
    changed["lease_until"] = 0.0
    changed["available_at"] = available
    return changed


def public(record: Json) -> Json:
    job: Json = record["job"]
    return {
        "id": job["id"],
        "queue": job["queue"],
        "payload": job["payload"],
        "priority": job["priority"],
        "state": record["state"],
        "attempts": record["attempts"],
        "worker": record["worker"],
        "created": record["created"],
        "available_at": record["available_at"],
        "lease_until": record["lease_until"],
        "completed_at": record["completed_at"],
    }


def configure() -> None:
    assert setting("QUEUE_PORT", 8772) >= 0 and setting("QUEUE_PORT", 8772) <= 65535, "invalid port"
    assert setting("QUEUE_LIMIT", 1000) >= 1 and setting("QUEUE_LIMIT", 1000) <= 1000, "invalid job limit"
    assert setting("QUEUE_LEASE", 30) >= 1 and setting("QUEUE_LEASE", 30) <= 3600, "invalid default lease"
    assert clock() >= 0.0 and clock() <= 253402214400.0, "invalid clock"
    return  # noqa: PLR1711 - explicit return required by repository guidelines
