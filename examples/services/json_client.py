import json

from py2rust.stdlib import HttpResponse, Json, http_request, json_string, pretty


def run() -> None:
    request: Json = {"name": " 世界 "}
    response: HttpResponse = http_request(
        "POST", "http://127.0.0.1:8080/hello", json.dumps(request), 2000, 65536
    )
    assert response.status == 200
    data: Json = json.loads(response.body)
    assert json_string(data["message"]) == "Hello, 世界"
    print(pretty(data))


if __name__ == "__main__":
    run()
