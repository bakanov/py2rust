from app import build_response

from py2rust.stdlib import (
    HttpServer,
    Json,
    http_listen,
    http_port,
    http_serve_json_timeout,
)


def handle(method: str, path: str, body: Json) -> Json:
    return build_response(body)


def main() -> None:
    server: HttpServer = http_listen("127.0.0.1", 8080)
    print(http_port(server))
    http_serve_json_timeout(server, handle, 1, 65536, 30000, 5000)


if __name__ == "__main__":
    main()
