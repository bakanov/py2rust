"""Typed items, finite box inventories and exact integer capacity rules."""

# ruff: noqa: PLR1711 - explicit subset returns

from dataclasses import dataclass

from py2rust.stdlib import Json, json_array, json_bool, json_int, json_keys, json_string


@dataclass
class Item:
    name: str
    destination: str
    weight: int
    volume: int
    separate: bool


@dataclass
class Box:
    name: str
    weight_limit: int
    volume_limit: int
    item_limit: int
    tare: int
    cost: int
    stock: int


@dataclass
class Problem:
    items: list[Item]
    boxes: list[Box]
    package_limit: int


def exact(value: Json, fields: list[str]) -> None:
    assert json_keys(value) == sorted(fields), "unexpected object fields"
    return


def number(value: Json, minimum: int, maximum: int) -> int:
    result: int = json_int(value)
    assert minimum <= result <= maximum, "integer outside supported bounds"
    return result


def name(value: Json) -> str:
    result: str = json_string(value)
    assert 1 <= len(result) <= 128 and len(result.encode()) <= 512 and "\x00" not in result, "invalid name"
    return result


def item_name(item: Item) -> str:
    return item.name


def box_name(carton: Box) -> str:
    return carton.name


def load(value: Json) -> Problem:
    exact(value, ["version", "items", "boxes", "max_packages"])
    assert json_int(value["version"]) == 1, "unsupported packing version"
    items: list[Item] = []
    seen: set[str] = set()
    rows: list[Json] = json_array(value["items"])
    assert len(rows) <= 512, "item count exceeds 512"
    for row in rows:
        exact(row, ["id", "destination", "weight_g", "volume_cm3", "separate"])
        identifier: str = name(row["id"])
        assert identifier not in seen, "duplicate item"
        seen.add(identifier)
        items.append(
            Item(
                identifier,
                name(row["destination"]),
                number(row["weight_g"], 1, 1000000000),
                number(row["volume_cm3"], 1, 1000000000),
                json_bool(row["separate"]),
            )
        )
    boxes: list[Box] = []
    seen = set()
    rows = json_array(value["boxes"])
    assert len(rows) <= 16, "box type count exceeds 16"
    for row in rows:
        exact(row, ["id", "weight_limit_g", "volume_limit_cm3", "item_limit", "tare_g", "cost_cents", "stock"])
        identifier: str = name(row["id"])
        assert identifier not in seen, "duplicate box type"
        seen.add(identifier)
        weight: int = number(row["weight_limit_g"], 1, 1000000000)
        tare: int = number(row["tare_g"], 0, 1000000000)
        assert tare < weight, "tare must be below gross weight limit"
        boxes.append(
            Box(
                identifier,
                weight,
                number(row["volume_limit_cm3"], 1, 1000000000),
                number(row["item_limit"], 1, 512),
                tare,
                number(row["cost_cents"], 0, 1000000000),
                number(row["stock"], 0, 512),
            )
        )
    return Problem(sorted(items, key=item_name), sorted(boxes, key=box_name), number(value["max_packages"], 0, 512))


def item_document(item: Item) -> Json:
    return {
        "id": item.name,
        "destination": item.destination,
        "weight_g": item.weight,
        "volume_cm3": item.volume,
        "separate": item.separate,
    }


def box_document(carton: Box) -> Json:
    return {
        "id": carton.name,
        "weight_limit_g": carton.weight_limit,
        "volume_limit_cm3": carton.volume_limit,
        "item_limit": carton.item_limit,
        "tare_g": carton.tare,
        "cost_cents": carton.cost,
        "stock": carton.stock,
    }


def document(problem: Problem) -> Json:
    items: list[Json] = []
    boxes: list[Json] = []
    for item in problem.items:
        items.append(item_document(item))
    for carton in problem.boxes:
        boxes.append(box_document(carton))
    return {"version": 1, "items": items, "boxes": boxes, "max_packages": problem.package_limit}
