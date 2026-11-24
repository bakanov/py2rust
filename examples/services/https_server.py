import logging

from py2rust.stdlib import (
    HttpServer,
    Json,
    http_port,
    http_serve_json_timeout,
    https_listen,
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
    server: HttpServer = https_listen(
        "127.0.0.1", 8443, "build/tls/server.crt", "build/tls/server.key"
    )
    print(http_port(server))
    http_serve_json_timeout(server, handle, 1, 65536, 30000, 5000)


if __name__ == "__main__":
    serve()
