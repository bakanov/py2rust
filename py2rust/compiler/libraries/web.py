"""Web callback and record contracts used by frontend typing and lowering."""

from ..rules.records import runtime_field_type

FIELDS = {
    record: {
        field: runtime_field_type(record, field)
        for field in ("method", "path", "target", "status", "body", "headers", "query")
        if runtime_field_type(record, field)
    }
    for record in ("HttpReader", "HttpResponse", "WebRequest", "WebResponse")
}

CALLBACKS = {
    "http_serve_json": ("HttpServer", "Callable[[str, str, Json], Json]", "int", "int"),
    "http_serve_json_timeout": ("HttpServer", "Callable[[str, str, Json], Json]", "int", "int", "int", "int"),
    "web_serve": ("str", "int", "Callable[[WebRequest], WebResponse]"),
    "web_serve_stream": ("str", "int", "Callable[[WebRequest], WebResponse]", "Callable[[Json], StreamChunk]"),
}
