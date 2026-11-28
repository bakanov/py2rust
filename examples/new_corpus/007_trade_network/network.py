"""Build stable trade components with indexed breadth-first traversal."""

from collections import Counter

from model import City, NetworkSegment, city_at


def road_neighbors(
    point: tuple[int, int], roads: list[tuple[tuple[int, int], tuple[int, int]]]
) -> list[tuple[int, int]]:
    result: list[tuple[int, int]] = []
    for road in roads:
        if road[0] == point:
            result.append(road[1])
        elif road[1] == point:
            result.append(road[0])
    return result


def build_network(
    cities: list[City], roads: list[tuple[tuple[int, int], tuple[int, int]]]
) -> dict[int, NetworkSegment]:
    airports: list[tuple[int, int]] = [city.point for city in cities if city.airport]
    assigned: dict[int, int] = {}
    components: list[tuple[int, list[int], set[tuple[int, int]]]] = []
    for origin in cities:
        if origin.identifier in assigned:
            continue
        network_id: int = origin.identifier
        members: list[int] = []
        tiles: set[tuple[int, int]] = set()
        pending: list[tuple[int, int]] = [origin.point]
        cursor: int = 0
        while cursor < len(pending):
            point: tuple[int, int] = pending[cursor]
            cursor += 1
            if point in tiles:
                continue
            tiles.add(point)
            city: City | None = city_at(cities, point)
            if city is not None:
                if city.identifier not in assigned:
                    members.append(city.identifier)
                    assigned[city.identifier] = network_id
                    network_id = min(network_id, city.identifier)
                if city.airport:
                    for destination in airports:
                        if destination not in tiles:
                            pending.append(destination)
            for neighbor in road_neighbors(point, roads):
                if neighbor not in tiles:
                    pending.append(neighbor)
        components.append((network_id, members, tiles))
    segments: dict[int, NetworkSegment] = {}
    for network_id, members, tiles in components:
        resources: Counter[str] = Counter()
        has_airport: bool = False
        for identifier in members:
            city: City | None = next((item for item in cities if item.identifier == identifier), None)
            assert city is not None
            for resource in city.resources:
                resources[resource] += 1
            has_airport = has_airport or city.airport
        segment: NetworkSegment = NetworkSegment(network_id, members, tiles, resources, has_airport)
        for identifier in members:
            segments[identifier] = segment
    return segments


def connected(segments: dict[int, NetworkSegment], first: int, second: int) -> bool:
    if first not in segments or second not in segments:
        return False
    return segments[first].network_id == segments[second].network_id


def exportable(segments: dict[int, NetworkSegment], city_id: int) -> list[str]:
    resources: Counter[str] = segments[city_id].resources
    return [name for name in sorted(resources) if resources[name] > 1]
