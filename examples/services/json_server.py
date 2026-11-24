import logging

from py2rust.stdlib import (
    HttpServer,
    Json,
    http_listen,
    http_port,
    http_serve_json,
    json_string,
    log_configure,
)


def handle(method: str, path: str, body: Json) -> Json:
    logging.info(method + " " + path)  # noqa: LOG015
    name: str = json_string(body["name"]).strip()
    response: Json = {"message": "Hello, " + name, "ok": True}
    return response


def serve() -> None:
    log_configure(20)
    server: HttpServer = http_listen("127.0.0.1", 8080)
    print(http_port(server))
    http_serve_json(server, handle, 1, 65536)


if __name__ == "__main__":
    serve()
