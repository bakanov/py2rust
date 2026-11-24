"""Exclusive resource bookings with adjacent intervals, cancellation and agendas."""

from model import (
    clock,
    configure,
    conflict,
    definition,
    find,
    normalize_booking,
    normalize_resource,
    ordered,
    setting,
)
from storage import initialize, load, save

from py2rust.stdlib import (
    DateTime,
    Json,
    WebRequest,
    WebResponse,
    datetime_iso,
    datetime_parse,
    json_array,
    json_bool,
    json_dumps,
    json_equal,
    json_float,
    json_kind,
    json_loads,
    json_parse,
    json_string,
    web_response,
    web_serve,
)


def reply(status: int, value: Json) -> WebResponse:
    headers: dict[str, str] = {"Content-Type": "application/json"}
    return web_response(status, json_dumps(value).encode(), headers)


def create_resource(request: WebRequest) -> WebResponse:
    resource: Json = None
    try:
        resource = normalize_resource(json_loads(request.body.decode()))
    except Exception:  # noqa: BLE001 - the compiled profile uses recoverable Exception
        return reply(400, {"error": "invalid resource"})
    state: Json = load()
    resources: list[Json] = json_array(state["resources"])
    previous: Json = find(resources, json_string(resource["id"]))
    if json_kind(previous) != "null":
        if json_equal(previous, resource):
            return reply(200, previous)
        return reply(409, {"error": "resource ID already exists"})
    if len(resources) >= setting("RESERVE_RESOURCES", 100):
        return reply(507, {"error": "resource storage is full"})
    resources.append(resource)
    state["resources"] = resources
    save(state)
    return reply(201, resource)


def book(request: WebRequest) -> WebResponse:
    booking: Json = None
    try:
        booking = normalize_booking(json_loads(request.body.decode()))
    except Exception:  # noqa: BLE001 - the compiled profile uses recoverable Exception
        return reply(400, {"error": "invalid booking or interval"})
    state: Json = load()
    if json_kind(find(json_array(state["resources"]), json_string(booking["resource"]))) == "null":
        return reply(404, {"error": "unknown resource"})
    bookings: list[Json] = json_array(state["bookings"])
    previous: Json = find(bookings, json_string(booking["id"]))
    if json_kind(previous) != "null":
        if json_equal(definition(previous), booking):
            return reply(200, previous)
        return reply(409, {"error": "booking ID already has different content"})
    overlapping: str = conflict(bookings, booking)
    if overlapping != "":
        return reply(409, {"error": "resource is already booked", "conflict": overlapping})
    if len(bookings) >= setting("RESERVE_BOOKINGS", 1000):
        return reply(507, {"error": "booking history is full"})
    booking["status"] = "active"
    booking["created_at"] = clock()
    booking["cancelled_at"] = 0.0
    bookings.append(booking)
    state["bookings"] = bookings
    save(state)
    return reply(201, booking)


def cancel(identifier: str) -> WebResponse:
    state: Json = load()
    bookings: list[Json] = json_array(state["bookings"])
    for index in range(len(bookings)):
        record: Json = bookings[index]
        if json_string(record["id"]) == identifier:
            if json_string(record["status"]) == "cancelled":
                return reply(200, record)
            record["status"] = "cancelled"
            record["cancelled_at"] = max(clock(), json_float(record["created_at"]))
            bookings[index] = record
            state["bookings"] = bookings
            save(state)
            return reply(200, record)
    return reply(404, {"error": "unknown booking"})


def agenda(request: WebRequest) -> WebResponse:
    start: DateTime = datetime_parse("0001-01-01T00:00:00Z")
    end: DateTime = datetime_parse("9999-12-31T23:59:59.999999Z")
    include_cancelled: bool = False
    try:
        start = datetime_parse(request.query.get("from", "0001-01-01T00:00:00Z"))
        end = datetime_parse(request.query.get("to", "9999-12-31T23:59:59.999999Z"))
        include_cancelled = json_bool(json_parse(request.query.get("include_cancelled", "false"), None))
        assert start < end, "invalid agenda range"
    except Exception:  # noqa: BLE001 - the compiled profile uses recoverable Exception
        return reply(400, {"error": "invalid agenda range or cancellation filter"})
    state: Json = load()
    resource: str = request.query.get("resource", "")
    if resource != "" and json_kind(find(json_array(state["resources"]), resource)) == "null":
        return reply(404, {"error": "unknown resource"})
    results: list[Json] = []
    for record in json_array(state["bookings"]):
        if (
            (resource == "" or json_string(record["resource"]) == resource)
            and (include_cancelled or json_string(record["status"]) == "active")
            and request.query.get("owner", "") in ["", json_string(record["owner"])]
        ):
            previous_start: DateTime = datetime_parse(json_string(record["start"]))
            previous_end: DateTime = datetime_parse(json_string(record["end"]))
            if start < previous_end and previous_start < end:
                results.append(record)
    return reply(
        200, {"from": datetime_iso(start), "to": datetime_iso(end), "bookings": ordered(results), "count": len(results)}
    )


def dispatch(request: WebRequest) -> WebResponse:
    if len(request.body) > 65536:
        return reply(413, {"error": "request exceeds byte limit"})
    if request.path == "/resources":
        if request.method == "POST":
            return create_resource(request)
        if request.method == "GET":
            return reply(200, {"resources": load()["resources"]})
        return reply(405, {"error": "use GET or POST"})
    if request.path.startswith("/resources/") and request.method == "DELETE":
        identifier: str = request.path[11:]
        state: Json = load()
        resources: list[Json] = json_array(state["resources"])
        if json_kind(find(resources, identifier)) == "null":
            return reply(404, {"error": "unknown resource"})
        for record in json_array(state["bookings"]):
            if json_string(record["resource"]) == identifier:
                return reply(409, {"error": "resource is referenced by booking history"})
        kept: list[Json] = []
        for resource in resources:
            if json_string(resource["id"]) != identifier:
                kept.append(resource)
        state["resources"] = kept
        save(state)
        return reply(200, {"deleted": identifier})
    if request.path == "/bookings" and request.method == "POST":
        return book(request)
    if request.path.startswith("/bookings/"):
        identifier: str = request.path[10:]
        if request.method == "DELETE":
            return cancel(identifier)
        if request.method == "GET":
            record: Json = find(json_array(load()["bookings"]), identifier)
            if json_kind(record) == "null":
                return reply(404, {"error": "unknown booking"})
            return reply(200, record)
        return reply(405, {"error": "use GET or DELETE"})
    if request.path == "/agenda" and request.method == "GET":
        return agenda(request)
    return reply(404, {"error": "unknown route"})


def handle(request: WebRequest) -> WebResponse:
    try:
        return dispatch(request)
    except Exception:  # noqa: BLE001 - the compiled profile uses recoverable Exception
        return reply(500, {"error": "reservation storage operation failed"})


def main() -> None:
    configure()
    initialize()
    web_serve("127.0.0.1", setting("RESERVE_PORT", 8773), handle)
    return  # noqa: PLR1711 - explicit return required by repository guidelines


if __name__ == "__main__":
    main()
