"""Connect roads and airports, then inspect shared resource stocks."""

from model import City, city_with_id
from network import build_network, connected, exportable


def main() -> None:
    cities: list[City] = [
        City(10, "Rome", 0, 0, ["wheat", "wheat"], True, True),
        City(11, "Ostia", 2, 0, ["fish"]),
        City(12, "Neapolis", 6, 0, ["iron"], True),
        City(20, "Antium", 8, 0, ["gems", "gems"]),
    ]
    roads: list[tuple[tuple[int, int], tuple[int, int]]] = [
        ((0, 0), (1, 0)),
        ((1, 0), (2, 0)),
        ((6, 0), (7, 0)),
    ]
    segments = build_network(cities, roads)
    for city in cities:
        segment = segments[city.identifier]
        print(
            city.name
            + ": network="
            + str(segment.network_id)
            + " cities="
            + str(len(segment.cities))
            + " tiles="
            + str(len(segment.tiles))
        )
    print("Rome connected to Ostia: " + ("True" if connected(segments, 10, 11) else "False"))
    print("Rome connected by air to Neapolis: " + ("True" if connected(segments, 10, 12) else "False"))
    print("Rome connected to Antium: " + ("True" if connected(segments, 10, 20) else "False"))
    for name in sorted(segments[10].resources):
        print("Capital stock " + name + ": " + str(segments[10].resources[name]))
    print("Capital exports: " + ", ".join(exportable(segments, 10)))
    capital: City | None = next((city for city in cities if city.capital), None)
    assert capital is not None
    selected: City | None = city_with_id(cities, capital.identifier)
    assert selected is not None
    print(
        "Capital: "
        + selected.name
        + "; separate networks: "
        + str(len({segment.network_id for segment in segments.values()}))
    )
    return


if __name__ == "__main__":
    main()
