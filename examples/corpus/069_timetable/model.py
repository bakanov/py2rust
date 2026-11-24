"""Validated finite timetables with normalized UTC timestamps and station transfer times."""

# ruff: noqa: PLR1711, C414 - explicit returns and typed list sorting

from dataclasses import dataclass

from py2rust.stdlib import (
    Json,
    datetime_iso,
    datetime_parse,
    json_array,
    json_int,
    json_keys,
    json_string,
)


@dataclass
class Connection:
    identifier: str
    origin: str
    destination: str
    departure: str
    arrival: str


@dataclass
class Timetable:
    transfers: dict[str, int]
    connections: list[Connection]
    outgoing: dict[str, list[int]]


def exact(value: Json, fields: list[str]) -> None:
    assert json_keys(value) == sorted(fields), "unexpected object fields"
    return


def name(value: Json) -> str:
    result: str = json_string(value)
    assert 1 <= len(result) <= 128 and len(result.encode()) <= 512 and "\x00" not in result, "invalid name"
    return result


def when(value: Json) -> str:
    result: str = datetime_iso(datetime_parse(json_string(value)))
    assert "2000-01-01T00:00:00.000000+00:00" <= result < "2100-01-01T00:00:00.000000+00:00", "time outside 2000..2099"
    return result


def order(connection: Connection) -> tuple[str, str, str]:
    return (connection.departure, connection.arrival, connection.identifier)


def load(value: Json) -> Timetable:
    exact(value, ["version", "stations", "connections"])
    assert json_int(value["version"]) == 1, "unsupported timetable version"
    stations: list[Json] = json_array(value["stations"])
    rows: list[Json] = json_array(value["connections"])
    assert len(stations) <= 256 and len(rows) <= 4096, "timetable capacity exceeded"
    transfers: dict[str, int] = {}
    outgoing: dict[str, list[int]] = {}
    for station in stations:
        exact(station, ["id", "transfer_seconds"])
        identifier: str = name(station["id"])
        assert identifier not in transfers, "duplicate station id"
        delay: int = json_int(station["transfer_seconds"])
        assert 0 <= delay <= 86400, "transfer seconds outside bounds"
        transfers[identifier] = delay
        outgoing[identifier] = []
    seen: set[str] = set()
    connections: list[Connection] = []
    for row in rows:
        exact(row, ["id", "from", "to", "departure", "arrival"])
        identifier: str = name(row["id"])
        assert identifier not in seen, "duplicate connection id"
        seen.add(identifier)
        origin: str = name(row["from"])
        destination: str = name(row["to"])
        assert origin in transfers and destination in transfers, "unknown connection station"
        departure: str = when(row["departure"])
        arrival: str = when(row["arrival"])
        assert departure < arrival, "arrival must follow departure"
        connections.append(Connection(identifier, origin, destination, departure, arrival))
    connections = sorted(connections, key=order)
    for position in range(len(connections)):
        outgoing[connections[position].origin].append(position)
    return Timetable(transfers, connections, outgoing)


def connection_record(connection: Connection) -> Json:
    return {
        "id": connection.identifier,
        "from": connection.origin,
        "to": connection.destination,
        "departure": connection.departure,
        "arrival": connection.arrival,
    }


def document(timetable: Timetable) -> Json:
    stations: list[Json] = []
    connections: list[Json] = []
    for identifier in sorted(list(timetable.transfers)):
        stations.append({"id": identifier, "transfer_seconds": timetable.transfers[identifier]})
    for connection in timetable.connections:
        connections.append(connection_record(connection))
    return {"version": 1, "stations": stations, "connections": connections}


def requests(timetable: Timetable, value: Json) -> list[Json]:
    rows: list[Json] = json_array(value)
    assert len(rows) <= 64, "request count exceeds 64"
    seen: set[str] = set()
    result: list[Json] = []
    for row in rows:
        exact(row, ["id", "from", "to", "depart_after"])
        identifier: str = name(row["id"])
        assert identifier not in seen, "duplicate request id"
        seen.add(identifier)
        origin: str = name(row["from"])
        destination: str = name(row["to"])
        assert origin in timetable.transfers and destination in timetable.transfers, "unknown request station"
        result.append({"id": identifier, "from": origin, "to": destination, "depart_after": when(row["depart_after"])})
    return result
