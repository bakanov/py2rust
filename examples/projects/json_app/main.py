"""One-command mixed Python/Rust JSON application."""

from app import build_response

from py2rust.stdlib import Json, json_dumps, json_loads, pretty


def main() -> None:
    request: Json = json_loads('{"name":"  世界  ","path":"/hello?lang=zh"}')
    response: Json = build_response(request)
    assert json_loads(json_dumps(response)) == response
    print(pretty(response))


if __name__ == "__main__":
    main()
