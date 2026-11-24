"""Sync message bytes before atomically publishing their receipt in the index."""

import sys

from envelope import greeting_valid, mailbox

from py2rust.stdlib import (
    Json,
    datetime_iso,
    datetime_parse,
    env_get,
    file_open,
    file_read,
    file_size,
    file_sync,
    file_write,
    json_array,
    json_int,
    json_keys,
    json_loads,
    json_string,
    list_dir,
    mkdir_all,
    path_exists,
    path_is_symlink,
    path_join,
    path_resolve,
    pretty,
    random_token,
    read_text,
    regex_fullmatch,
    remove_file,
    sha256_digest,
    sha256_new,
    sha256_update,
    sync_directory,
    utc_now,
    write_text_atomic,
)


def root() -> str:
    return env_get("SMTP_DATA", "smtp-capture")


def digest(data: bytes) -> str:
    return sha256_digest(sha256_update(sha256_new(), data))


def fault(boundary: str) -> None:
    if env_get("SMTP_FAULT", "") == boundary:
        sys.exit(75)
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def load(policy: Json, recover: bool) -> list[Json]:
    assert not path_is_symlink(root()), "capture directory must not be a symlink"
    mkdir_all(root())
    directory: str = path_resolve(root())
    assert not path_resolve(env_get("SMTP_CONFIG", "smtp.json")).startswith(directory + "/"), "config inside data"
    path: str = path_join(root(), "index.json")
    assert not path_is_symlink(path), "index must not be a symlink"
    records: list[Json] = []
    if path_exists(path):
        with file_open(path, "rb") as handle:
            assert file_size(handle) <= 8388608, "index exceeds 8 MiB"
        state: Json = json_loads(read_text(path))
        assert json_keys(state) == ["format", "messages"] and json_int(state["format"]) == 1, "invalid index"
        records = json_array(state["messages"])
    assert len(records) <= json_int(policy["max_messages"]), "retained capacity exceeded"
    ids: set[str] = set()
    for record in records:
        assert json_keys(record) == [
            "body",
            "from",
            "greeting",
            "id",
            "received",
            "recipients",
            "sha256",
            "size",
        ], "bad receipt"
        name: str = json_string(record["id"])
        assert regex_fullmatch("[0-9a-f]{64}", name) and name not in ids, "invalid or repeated ID"
        ids.add(name)
        assert mailbox(json_string(record["from"]), True), "invalid retained sender"
        recipients: list[Json] = json_array(record["recipients"])
        assert len(recipients) >= 1 and len(recipients) <= json_int(policy["max_recipients"]), "recipient count"
        for recipient in recipients:
            assert mailbox(json_string(recipient), False), "invalid retained recipient"
        assert json_string(record["body"]) in ["7BIT", "8BITMIME"], "invalid retained body mode"
        assert greeting_valid(json_string(record["greeting"])), "bad greeting"
        datetime_parse(json_string(record["received"]))
        path = path_join(root(), name + ".eml")
        assert not path_is_symlink(path), "message must not be a symlink"
        content: bytes = b""
        with file_open(path, "rb") as handle:
            size: int = file_size(handle)
            assert size == json_int(record["size"]) and size <= json_int(policy["max_bytes"]), "message size mismatch"
            content = file_read(handle, size + 1)
        assert digest(content) == json_string(record["sha256"]), "message checksum mismatch"
    if recover:
        for name in list_dir(root()):
            if name != "index.json":
                assert regex_fullmatch("[0-9a-f]{64}[.]eml", name), "unexpected file in capture directory"
                assert not path_is_symlink(path_join(root(), name)), "message must not be a symlink"
                if name[:64] not in ids:
                    remove_file(path_join(root(), name))
        sync_directory(root())
    return records


def capture(sender: str, recipients: list[str], greeting: str, body: str, content: bytes, policy: Json) -> str:
    records: list[Json] = load(policy, True)
    assert len(records) < json_int(policy["max_messages"]), "capture directory full"
    name: str = random_token()
    records.append(
        {
            "id": name,
            "from": sender,
            "recipients": recipients,
            "greeting": greeting,
            "body": body,
            "size": len(content),
            "sha256": digest(content),
            "received": datetime_iso(utc_now()),
        }
    )
    text: str = pretty({"format": 1, "messages": records})
    assert len(text.encode()) <= 8388608, "index exceeds 8 MiB"
    fault("before_message")
    with file_open(path_join(root(), name + ".eml"), "x+b") as handle:
        file_write(handle, content)
        file_sync(handle)
    sync_directory(root())
    fault("after_message")
    write_text_atomic(path_join(root(), "index.json"), text)
    fault("after_index")
    return name
