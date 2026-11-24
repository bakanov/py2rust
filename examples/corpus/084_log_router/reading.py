"""Drain complete lines from saved inodes before switching to replacement input files."""

# ruff: noqa: I001 - compact grouped runtime imports within 120 columns
from config import severity
from files import hashed, identity, prefix, present, regular

from py2rust.stdlib import (
    Json, Sha256, directory_names, json_array, json_int, json_keys, json_string, line_open, line_read, path_join,
    path_parent, path_stat, regex_search, sha256_digest, sha256_update
)


def locate(path: str, token: str) -> str:
    if present(path) and identity(path) == token:
        return path
    matches: list[str] = []
    for name in directory_names(path_parent(path), 256):
        candidate: str = path_join(path_parent(path), name)
        info: Json = path_stat(candidate, False)
        candidate_token: str = str(json_int(info["device"])) + ":" + str(json_int(info["inode"]))
        if json_string(info["kind"]) == "file" and candidate_token == token:
            regular(candidate)
            matches.append(candidate)
    assert len(matches) == 1, "previous input inode is missing or ambiguous"
    return matches[0]


def collect(config: Json, state: Json) -> tuple[Json, list[Json]]:
    cursors: Json = state["sources"]
    known: list[str] = []
    for key in json_keys(cursors):
        known.append(json_string(cursors[key]["identity"]))
        for token in json_array(cursors[key]["past"]):
            known.append(json_string(token))
    rows: list[Json] = []
    for source in json_array(config["sources"]):
        key: str = json_string(source["id"])
        cursor: Json = cursors[key]
        configured: str = json_string(source["path"])
        token: str = json_string(cursor["identity"])
        path: str = locate(configured, token)
        size: int = json_int(regular(path)["size"])
        offset: int = json_int(cursor["offset"])
        assert offset <= size <= 67108864, "input truncated or exceeds 64 MiB"
        digest: Sha256 = prefix(path, offset)
        assert sha256_digest(digest) == json_string(cursor["sha256"]), "committed input prefix changed"
        with line_open(path, offset) as reader:
            for attempt in range(json_int(config["batch_lines"])):
                if offset == size:
                    break
                part: tuple[bytes, bool] = line_read(reader, min(1025, size - offset))
                raw: bytes = part[0]
                assert len(raw) <= 1024, "input line exceeds 1024 bytes"
                if not raw.endswith(b"\n"):
                    break
                text: str = raw[:-1].decode()
                if text.endswith("\r"):  # noqa: FURB188 - subset has no str.removesuffix
                    text = text[:-1]
                fields: list[str] = text.split(" ")
                assert len(fields) >= 2 and not regex_search("[\\x00-\\x08\\x0b-\\x1f\\x7f]", text), "invalid log line"
                severity(fields[0])
                cursor["lines"] = json_int(cursor["lines"]) + 1
                rows.append(
                    {
                        "source": key,
                        "line": cursor["lines"],
                        "generation": len(json_array(cursor["past"])),
                        "offset": offset,
                        "level": fields[0],
                        "message": text[len(fields[0]) + 1 :],
                    }
                )
                offset = offset + len(raw)
                digest = sha256_update(digest, raw)
        observed_size: int = json_int(regular(path)["size"])
        assert identity(path) == token and observed_size >= size, "input changed during reading"
        cursor["offset"] = offset
        cursor["sha256"] = sha256_digest(digest)
        if path != configured and offset == observed_size and present(configured):
            next_token: str = identity(configured)
            assert next_token not in known, "input identity was already used"
            past: list[Json] = json_array(cursor["past"])
            assert len(past) < 32, "input rotation limit reached"
            past.append(token)
            cursor["past"] = past
            cursor["identity"] = next_token
            cursor["offset"] = 0
            cursor["sha256"] = hashed(b"")
            known.append(next_token)
        cursors[key] = cursor
    state["sources"] = cursors
    return (state, rows)
