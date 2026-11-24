from py2rust.stdlib import (
    HttpResponse,
    Json,
    https_request_ca,
    json_dumps,
    json_loads,
    json_string,
    pretty,
)


def request() -> None:
    payload: Json = {"name": "世界"}
    response: HttpResponse = https_request_ca(
        "POST",
        "https://localhost:8443/hello",
        json_dumps(payload),
        3000,
        65536,
        "build/tls/ca.crt",
    )
    assert response.status == 200
    result: Json = json_loads(response.body)
    assert json_string(result["message"]) == "Hello, 世界"
    print(pretty(result))


if __name__ == "__main__":
    request()
