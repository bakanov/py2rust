"""A native batch client; reconnect at the server's per-connection frame budget."""

import sys

from config import distinct_paths, state_path
from protocol import receive, send

from py2rust.stdlib import (
    Json,
    env_get,
    json_array,
    json_bool,
    json_dumps,
    json_int,
    json_loads,
    path_is_symlink,
    pretty,
    read_text,
    tcp_connect,
    write_text_atomic,
)


def exchange(policy: Json, port: int) -> None:
    source: str = env_get("BROKER_REQUESTS", "requests.json")
    output: str = env_get("BROKER_REPORT", "responses.json")
    paths: list[str] = [source, output, state_path(), env_get("BROKER_CONFIG", "broker.json")]
    marker: str = env_get("BROKER_SHUTDOWN", "")
    if marker != "":
        paths.append(marker)
    distinct_paths(paths)
    assert not path_is_symlink(output), "client report must not be a symlink"
    text: str = read_text(source)
    assert len(text.encode()) <= 1048576, "request batch exceeds 1 MiB"
    commands: list[Json] = json_array(json_loads(text))
    assert len(commands) >= 1 and len(commands) <= 100, "expected 1–100 commands"
    limit: int = json_int(policy["max_frame"])
    timeout: int = json_int(policy["frame_timeout_ms"])
    for command in commands:
        assert len(json_dumps(command).encode()) <= limit, "request exceeds frame limit"
    replies: list[Json] = []
    report: Json = {"phase": "running", "requested": len(commands), "responses": replies}
    write_text_atomic(output, pretty(report))
    index: int = 0
    errors: int = 0
    while index < len(commands):
        with tcp_connect(env_get("BROKER_HOST", "127.0.0.1"), port, timeout) as stream:
            count: int = min(json_int(policy["connection_frames"]), len(commands) - index)
            for offset in range(count):
                send(stream, commands[index], limit, timeout)
                body: bytes = receive(stream, limit, timeout)
                reply: Json = json_loads(body.decode())
                if not json_bool(reply["ok"]):
                    errors = errors + 1
                replies.append(reply)
                index = index + 1
                report["responses"] = replies
                write_text_atomic(output, pretty(report))
    report["phase"] = "finished"
    report["errors"] = errors
    write_text_atomic(output, pretty(report))
    print(json_dumps({"responses": index, "errors": errors}))
    if errors > 0:
        sys.exit(1)
    return  # noqa: PLR1711 - explicit return required by repository guidelines
