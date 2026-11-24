import native as rust

from py2rust.stdlib import Json, json_string

from .models import API_VERSION, Status


def build_response(request: Json) -> Json:
    name: str = json_string(request["name"]).strip()
    path: str = rust.route(json_string(request["path"]))
    status: Status = Status.OK
    result: Json = {
        "message": "Hello, " + name,
        "path": path,
        "bytes": rust.payload_size(name.encode()),
        "status": status.value,
        "version": API_VERSION,
    }
    return result
