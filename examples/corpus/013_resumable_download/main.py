"""Stream validated byte ranges into a durable prefix, then publish verified bytes."""

import sys

from model import configuration, response_range, setting
from storage import load, prepare, publish, restore, save, stop, target, validate_paths

from py2rust.stdlib import (
    Json,
    Sha256,
    env_get,
    file_open,
    file_seek,
    file_size,
    file_sync,
    file_write,
    json_dumps,
    json_int,
    json_string,
    pretty,
    sha256_digest,
    sha256_update,
    web_open,
    web_read,
    write_text_atomic,
)


def transfer(state: Json, digest: Sha256) -> tuple[Json, Sha256]:
    policy: Json = state["policy"]
    offset: int = json_int(state["offset"])
    end: int = offset + json_int(policy["chunk_size"]) - 1
    if json_int(state["total"]) >= 0:
        end = min(end, json_int(state["total"]) - 1)
    headers: dict[str, str] = {"Range": "bytes=" + str(offset) + "-" + str(end), "Accept-Encoding": "identity"}
    if json_string(state["etag"]) != "":
        headers["If-Range"] = json_string(state["etag"])
    with web_open(
        json_string(policy["url"]), headers, json_int(policy["timeout_ms"]), json_int(policy["chunk_size"])
    ) as response:
        metadata: tuple[int, int, str] = response_range(response, state, end)
        received: int = 0
        with file_open(target(state) + ".part", "r+b") as output:
            assert file_size(output) == offset, "partial size changed"
            file_seek(output, offset, 0)
            if metadata[0] > 0:
                while True:
                    data: bytes = web_read(response, 65536)
                    if len(data) == 0:
                        break
                    assert received + len(data) <= metadata[1], "body exceeds declared range"
                    file_write(output, data)
                    digest = sha256_update(digest, data)
                    received = received + len(data)
                    stop("mid_body")
            assert received == metadata[1], "body is shorter than declared range"
            file_sync(output)
        stop("after_write")
        updated: Json = {
            "version": 1,
            "policy": policy,
            "offset": offset + received,
            "total": metadata[0],
            "etag": metadata[2],
            "prefix": sha256_digest(digest),
            "phase": "downloading",
        }
        save(updated)
        stop("after_checkpoint")
        return (updated, digest)


def download(state: Json, steps: int) -> Json:
    if json_string(state["phase"]) == "downloading":
        digest: Sha256 = restore(state)
        for index in range(steps):
            if json_int(state["offset"]) == json_int(state["total"]):
                break
            result: tuple[Json, Sha256] = transfer(state, digest)
            state = result[0]
            digest = result[1]
    if json_int(state["offset"]) == json_int(state["total"]):
        state = publish(state)
    return state


def main() -> None:
    steps: int = setting("DOWNLOAD_STEPS", 8)
    assert steps >= 1 and steps <= 1000, "invalid range budget"
    assert env_get("DOWNLOAD_STOP", "") in [
        "",
        "mid_body",
        "after_write",
        "after_checkpoint",
        "before_publish",
        "after_publish",
    ], "invalid interruption point"
    policy: Json = configuration()
    state: Json = prepare(policy)
    error: str = ""
    try:
        state = download(state, steps)
    except Exception as failure:  # noqa: BLE001 - the compiled profile uses recoverable Exception
        error = str(failure)
        state = load(policy)
    result: Json = {
        "phase": state["phase"],
        "offset": state["offset"],
        "total": state["total"],
        "etag": state["etag"],
        "sha256": state["prefix"],
        "error": error,
    }
    validate_paths(policy)
    write_text_atomic(target(state) + ".report.json", pretty(result))
    print(json_dumps({"phase": state["phase"], "offset": state["offset"], "total": state["total"]}))
    if error != "":
        sys.exit(1)
    return  # noqa: PLR1711 - explicit return required by repository guidelines


if __name__ == "__main__":
    main()
