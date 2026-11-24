"""Exact stock accounting, atomic order transitions and explicit reservation invariants."""

# ruff: noqa: PLR1711, BLE001 - explicit validation boundary
from py2rust.stdlib import (
    Json,
    json_array,
    json_canonical,
    json_int,
    json_keys,
    json_kind,
    json_loads_unique,
    json_string,
    regex_fullmatch,
)


def exact(value: Json, fields: list[str]) -> None:
    assert sorted(json_keys(value)) == sorted(fields), "unexpected fields"
    return


def integer(value: Json, low: int, high: int) -> int:
    try:
        result: int = json_int(value)
        assert low <= result <= high, "invalid quantity"
        return result
    except Exception:
        assert False, "invalid quantity"
    return 0


def identifier(value: Json) -> str:
    assert json_kind(value) == "string", "invalid identifier"
    result: str = json_string(value)
    assert regex_fullmatch("[A-Za-z][A-Za-z0-9_-]{0,31}", result), "invalid identifier"
    return result


def catalog(value: Json) -> list[str]:
    items: list[str] = []
    for entry in json_array(value):
        name: str = identifier(entry)
        assert name not in items, "duplicate item"
        items.append(name)
    assert 1 <= len(items) <= 32, "item count limit"
    return sorted(items)


def validate(event: Json, items: list[str]) -> str:
    assert json_kind(event) == "object", "expected transaction object"
    assert "id" in json_keys(event) and "op" in json_keys(event), "transaction fields missing"
    identifier(event["id"])
    assert json_kind(event["op"]) == "string", "invalid transaction kind"
    kind: str = json_string(event["op"])
    assert kind in ["receive", "reserve", "release", "cancel", "reconcile"], "unknown transaction"
    keys: list[str] = ["id", "op"]
    if kind in ["reserve", "release", "cancel"]:
        keys.append("order")
    if kind != "cancel":
        keys.append("items")
    exact(event, keys)
    if kind in ["reserve", "release", "cancel"]:
        identifier(event["order"])
    if kind != "cancel":
        quantities: Json = event["items"]
        assert json_kind(quantities) == "object", "expected transaction items"
        assert 1 <= len(json_keys(quantities)) <= 32, "transaction item limit"
        for item in json_keys(quantities):
            assert item in items, "unknown item"
            integer(quantities[item], 0 if kind == "reconcile" else 1, 1000000000)
    return kind


def empty(items: list[str]) -> Json:
    stock: Json = {}
    for item in items:
        stock[item] = 0
    return {"stock": stock, "orders": {}}


def balances(state: Json) -> Json:
    stock: Json = state["stock"]
    orders: Json = state["orders"]
    reserved: dict[str, int] = {}
    for item in json_keys(stock):
        reserved[item] = 0
    assert len(json_keys(orders)) <= 128, "order count limit"
    for name in json_keys(orders):
        order: Json = orders[name]
        exact(order, ["status", "items"])
        status: str = json_string(order["status"])
        assert status in ["active", "released", "cancelled"], "invalid order status"
        quantities: Json = order["items"]
        assert (len(json_keys(quantities)) > 0) == (status == "active"), "inconsistent order status"
        for item in json_keys(quantities):
            assert item in json_keys(stock), "unknown reserved item"
            reserved[item] = reserved[item] + integer(quantities[item], 1, 1000000000)
    result: Json = {}
    for item in sorted(json_keys(stock)):
        on_hand: int = integer(stock[item], 0, 1000000000)
        assert reserved[item] <= on_hand, "insufficient available stock"
        result[item] = {"on_hand": on_hand, "reserved": reserved[item], "available": on_hand - reserved[item]}
    return result


def transition(state: Json, event: Json, kind: str) -> Json:
    # Copy before mutation: a rejected multi-item transaction cannot alter its caller.
    copied: Json = json_loads_unique(json_canonical(state))
    stock: Json = copied["stock"]
    orders: Json = copied["orders"]
    available: Json = balances(state)
    if kind in ["receive", "reconcile"]:
        for item in sorted(json_keys(event["items"])):
            quantity: int = json_int(event["items"][item])
            count: int = json_int(stock[item]) + quantity if kind == "receive" else quantity
            assert count <= 1000000000, "stock quantity limit"
            assert count >= json_int(available[item]["reserved"]), "count below existing reservations"
            stock[item] = count
    else:
        name: str = json_string(event["order"])
        if kind == "reserve":
            assert name not in json_keys(orders), "order identifier already used"
            assert len(json_keys(orders)) < 128, "order count limit"
            for item in json_keys(event["items"]):
                assert json_int(event["items"][item]) <= json_int(
                    available[item]["available"]
                ), "insufficient available stock"
            orders[name] = {"status": "active", "items": event["items"]}
        else:
            assert name in json_keys(orders), "unknown order"
            assert json_string(orders[name]["status"]) == "active", "order is already closed"
            quantities: Json = orders[name]["items"]
            if kind == "cancel":
                orders[name] = {"status": "cancelled", "items": {}}
            else:
                for item in sorted(json_keys(event["items"])):
                    amount: int = json_int(event["items"][item])
                    assert item in json_keys(quantities) and amount <= json_int(
                        quantities[item]
                    ), "release exceeds reservation"
                    remaining: int = json_int(quantities[item]) - amount
                    if remaining == 0:
                        del quantities[item]
                    else:
                        quantities[item] = remaining
                orders[name] = {
                    "status": "released" if len(json_keys(quantities)) == 0 else "active",
                    "items": quantities,
                }
    following: Json = {"stock": stock, "orders": orders}
    balances(following)
    return following
