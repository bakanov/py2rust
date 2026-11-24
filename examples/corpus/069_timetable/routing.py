"""Earliest station labels, scheduled boarding constraints and complete journey reconstruction."""

# ruff: noqa: C414 - sorting uses an explicit typed list

import heapq

from model import Connection, Timetable, connection_record

from py2rust.stdlib import (
    Json,
    datetime_add_seconds,
    datetime_iso,
    datetime_parse,
    json_string,
)


def ready(arrival: str, transfer_seconds: int) -> str:
    return datetime_iso(datetime_add_seconds(datetime_parse(arrival), transfer_seconds))


def plan(timetable: Timetable, request: Json) -> Json:
    origin: str = json_string(request["from"])
    destination: str = json_string(request["to"])
    beginning: str = json_string(request["depart_after"])
    earliest: dict[str, str] = {origin: beginning}
    previous: dict[str, int] = {}
    heap: list[tuple[str, str]] = [(beginning, origin)]
    settled: set[str] = set()
    pushed: int = 1
    popped: int = 0
    stale: int = 0
    considered: int = 0
    missed: int = 0
    while len(heap) > 0:
        ticket: tuple[str, str] = heapq.heappop(heap)
        station: str = ticket[1]
        if station in settled or ticket[0] != earliest[station]:
            stale = stale + 1
            popped = popped + 1
            continue
        popped = popped + 1
        settled.add(station)
        board_after: str = ready(ticket[0], 0 if station == origin else timetable.transfers[station])
        for position in timetable.outgoing[station]:
            connection: Connection = timetable.connections[position]
            considered = considered + 1
            if connection.departure < board_after:
                missed = missed + 1
                continue
            following: str = connection.destination
            if following not in earliest or connection.arrival < earliest[following]:
                earliest[following] = connection.arrival
                previous[following] = position
                heapq.heappush(heap, (connection.arrival, following))
                pushed = pushed + 1
    reachable: list[Json] = []
    for station in sorted(list(earliest)):
        reachable.append({"station": station, "arrival": earliest[station]})
    legs: list[Json] = []
    arrival: Json = None
    if destination in earliest:
        arrival = earliest[destination]
        reverse: list[int] = []
        current: str = destination
        while current != origin:
            assert current in previous and len(reverse) < len(timetable.transfers), "invalid journey predecessor chain"
            position: int = previous[current]
            reverse.append(position)
            current = timetable.connections[position].origin
        reverse.reverse()
        for position in reverse:
            connection: Connection = timetable.connections[position]
            transfer: int = 0 if len(legs) == 0 else timetable.transfers[connection.origin]
            leg: Json = connection_record(connection)
            leg["transfer_seconds"] = transfer
            leg["ready_at"] = ready(earliest[connection.origin], transfer)
            legs.append(leg)
    return {
        "id": request["id"],
        "from": origin,
        "to": destination,
        "depart_after": beginning,
        "status": "found" if destination in earliest else "unreachable",
        "arrival": arrival,
        "legs": legs,
        "transfers": max(0, len(legs) - 1),
        "reachable": reachable,
        "stats": {
            "settled": len(settled),
            "pushed": pushed,
            "popped": popped,
            "stale": stale,
            "connections_considered": considered,
            "missed_connections": missed,
        },
    }
