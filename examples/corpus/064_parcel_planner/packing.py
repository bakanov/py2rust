"""Weight-first first-fit packing with explicit stock, package limits and item accounting."""

from dataclasses import dataclass

from model import Box, Item, Problem, item_document

from py2rust.stdlib import Json


@dataclass
class Parcel:
    kind: int
    destination: str
    items: list[Item]
    weight: int
    volume: int
    separate: bool


def item_rank(item: Item) -> tuple[int, int, str]:
    return (-item.weight, -item.volume, item.name)


def box_rank(carton: Box) -> tuple[int, int, int, int, str]:
    return (carton.cost, carton.weight_limit - carton.tare, carton.volume_limit, carton.item_limit, carton.name)


def fits_empty(carton: Box, item: Item) -> bool:
    return item.weight + carton.tare <= carton.weight_limit and item.volume <= carton.volume_limit


def fits(parcel: Parcel, carton: Box, item: Item) -> bool:
    return (
        not parcel.separate
        and not item.separate
        and parcel.destination == item.destination
        and len(parcel.items) < carton.item_limit
        and parcel.weight + item.weight + carton.tare <= carton.weight_limit
        and parcel.volume + item.volume <= carton.volume_limit
    )


def parcel_document(parcel: Parcel, carton: Box, number: int) -> Json:
    items: list[Json] = []
    for item in parcel.items:
        items.append(item_document(item))
    return {
        "id": "package-" + str(number),
        "box": carton.name,
        "destination": parcel.destination,
        "items": items,
        "item_weight_g": parcel.weight,
        "gross_weight_g": parcel.weight + carton.tare,
        "volume_cm3": parcel.volume,
        "cost_cents": carton.cost,
        "remaining_weight_g": carton.weight_limit - carton.tare - parcel.weight,
        "remaining_volume_cm3": carton.volume_limit - parcel.volume,
        "remaining_slots": carton.item_limit - len(items),
    }


def plan(problem: Problem) -> Json:
    remaining: list[int] = []
    for carton in problem.boxes:
        remaining.append(carton.stock)
    parcels: list[Parcel] = []
    rejected: list[Json] = []
    for item in sorted(problem.items, key=item_rank):
        selected: int = -1
        for index in range(len(parcels)):
            candidate: Parcel = parcels[index]
            if fits(candidate, problem.boxes[candidate.kind], item):
                selected = index
                break
        if selected < 0:
            eligible: list[str] = []
            available: list[str] = []
            choice: int = -1
            for index in range(len(problem.boxes)):
                carton: Box = problem.boxes[index]
                if fits_empty(carton, item):
                    eligible.append(carton.name)
                    if remaining[index] > 0:
                        available.append(carton.name)
                        if choice < 0 or box_rank(carton) < box_rank(problem.boxes[choice]):
                            choice = index
            reason: str = ""
            if len(eligible) == 0:
                reason = "no_box_fits"
            elif len(available) == 0:
                reason = "stock_exhausted"
            elif len(parcels) == problem.package_limit:
                reason = "package_limit"
            if reason != "":
                rejected.append(
                    {
                        "item": item_document(item),
                        "reason": reason,
                        "eligible_box_types": eligible,
                        "available_box_types": available,
                    }
                )
                continue
            remaining[choice] = remaining[choice] - 1
            selected = len(parcels)
            parcels.append(Parcel(choice, item.destination, [], 0, 0, item.separate))
        parcel: Parcel = parcels[selected]
        contents: list[Item] = parcel.items.copy()
        contents.append(item)
        parcel.items = contents
        parcel.weight = parcel.weight + item.weight
        parcel.volume = parcel.volume + item.volume
        parcels[selected] = parcel
    packages: list[Json] = []
    assigned: int = 0
    net_weight: int = 0
    gross_weight: int = 0
    volume: int = 0
    cost: int = 0
    for parcel in parcels:
        carton: Box = problem.boxes[parcel.kind]
        packages.append(parcel_document(parcel, carton, len(packages) + 1))
        assigned = assigned + len(parcel.items)
        net_weight = net_weight + parcel.weight
        gross_weight = gross_weight + parcel.weight + carton.tare
        volume = volume + parcel.volume
        cost = cost + carton.cost
    inventory: list[Json] = []
    for index in range(len(problem.boxes)):
        carton: Box = problem.boxes[index]
        inventory.append({"box": carton.name, "opened": carton.stock - remaining[index], "remaining": remaining[index]})
    total_weight: int = 0
    total_volume: int = 0
    for item in problem.items:
        total_weight = total_weight + item.weight
        total_volume = total_volume + item.volume
    assert assigned + len(rejected) == len(problem.items), "internal item accounting error"
    return {
        "version": 1,
        "heuristic": "weight-first-first-fit-v1",
        "status": "complete" if len(rejected) == 0 else "partial",
        "packages": packages,
        "rejected": rejected,
        "inventory": inventory,
        "totals": {
            "items": len(problem.items),
            "assigned": assigned,
            "rejected": len(rejected),
            "packages": len(parcels),
            "item_weight_g": net_weight,
            "gross_weight_g": gross_weight,
            "volume_cm3": volume,
            "cost_cents": cost,
            "rejected_weight_g": total_weight - net_weight,
            "rejected_volume_cm3": total_volume - volume,
        },
    }
