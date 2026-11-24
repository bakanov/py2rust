"""Exact cent allocations using weighted largest remainders and stable name ties."""

from py2rust.stdlib import Json, json_array, json_int, json_string


def identifier(event: Json) -> str:
    value: str = json_string(event["id"])
    assert len(value) > 0 and len(value) <= 128, "invalid transaction ID"
    return value


def validate_people(values: list[Json]) -> list[str]:
    assert len(values) > 0 and len(values) <= 100, "expected 1–100 people"
    people: list[str] = []
    for value in values:
        name: str = json_string(value)
        assert len(name) > 0 and len(name) <= 100, "invalid person name"
        assert name not in people, "duplicate person"
        people.append(name)
    people.sort()
    return people


def shares(event: Json, people: list[str]) -> dict[str, int]:
    weights: dict[str, int] = {}
    supplied: list[Json] = json_array(event["shares"])
    assert len(supplied) > 0 and len(supplied) <= len(people), "invalid share count"
    for item in supplied:
        name: str = json_string(item["person"])
        weight: int = json_int(item["weight"])
        assert name in people and name not in weights, "unknown or duplicate share recipient"
        assert weight > 0 and weight <= 1000000, "weight must be 1–1000000"
        weights[name] = weight
    return weights


def allocate(event: Json, people: list[str]) -> dict[str, int]:
    assert json_string(event["payer"]) in people, "unknown payer"
    amount: int = json_int(event["cents"])
    assert amount >= -1000000000000 and amount <= 1000000000000, "expense outside cent bounds"
    weights: dict[str, int] = shares(event, people)
    total_weight: int = 0
    for name in people:
        total_weight = total_weight + weights.get(name, 0)
    allocation: dict[str, int] = {}
    ranked: list[tuple[int, str]] = []
    allocated: int = 0
    for name in people:
        if name in weights:
            numerator: int = amount * weights[name]
            base: int = numerator // total_weight
            remainder: int = numerator % total_weight
            allocation[name] = base
            allocated = allocated + base
            # Ascending negative remainder selects the greatest remainder first;
            # Unicode name order makes ties independent of import order.
            ranked.append((-remainder, name))
    ranked.sort()
    extra: int = amount - allocated
    assert extra >= 0 and extra < len(ranked), "invalid remainder budget"
    for index in range(extra):
        name: str = ranked[index][1]
        allocation[name] = allocation[name] + 1
    total: int = 0
    for name in people:
        total = total + allocation.get(name, 0)
    assert total == amount, "allocation lost cents"
    return allocation


def expense_balance(event: Json, people: list[str], current: dict[str, int]) -> dict[str, int]:
    following: dict[str, int] = current.copy()
    allocation: dict[str, int] = allocate(event, people)
    payer: str = json_string(event["payer"])
    following[payer] = following[payer] + json_int(event["cents"])
    for name in people:
        following[name] = following[name] - allocation.get(name, 0)
    return following


def settlement_balance(event: Json, people: list[str], current: dict[str, int]) -> dict[str, int]:
    sender: str = json_string(event["from"])
    recipient: str = json_string(event["to"])
    amount: int = json_int(event["cents"])
    assert sender in people and recipient in people and sender != recipient, "invalid settlement parties"
    assert amount > 0, "settlement must be positive"
    assert current[sender] < 0 and current[recipient] > 0, "settlement must run from debtor to creditor"
    assert amount <= -current[sender] and amount <= current[recipient], "settlement exceeds outstanding balance"
    following: dict[str, int] = current.copy()
    following[sender] = following[sender] + amount
    following[recipient] = following[recipient] - amount
    return following
