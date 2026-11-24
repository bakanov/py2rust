"""A bounded durable event ledger with replay and idempotent import IDs."""

from allocation import (
    allocate,
    expense_balance,
    identifier,
    settlement_balance,
    validate_people,
)

from py2rust.stdlib import (
    Json,
    env_get,
    json_array,
    json_equal,
    json_int,
    json_loads,
    json_string,
    path_exists,
    pretty,
    read_text,
    write_text_atomic,
)


def state_path() -> str:
    return env_get("EXPENSE_STATE", "expense-state.json")


def balances(state: Json) -> dict[str, int]:
    people: list[str] = validate_people(json_array(state["people"]))
    current: dict[str, int] = {}
    for person in people:
        current[person] = 0
    seen: set[str] = set()
    events: list[Json] = json_array(state["events"])
    assert len(events) <= 1000, "ledger exceeds 1000 transactions"
    for event in events:
        name: str = identifier(event)
        assert name not in seen, "duplicate stored transaction ID"
        seen.add(name)
        kind: str = json_string(event["op"])
        if kind == "expense":
            current = expense_balance(event, people, current)
        else:
            assert kind == "settle", "unknown transaction kind"
            current = settlement_balance(event, people, current)
    total: int = 0
    for person in people:
        total = total + current[person]
    assert total == 0, "ledger balances do not sum to zero"
    return current


def initialize(people: list[str]) -> Json:
    if not path_exists(state_path()):
        return {"version": 1, "people": people, "events": []}
    state: Json = json_loads(read_text(state_path()))
    assert json_int(state["version"]) == 1, "unsupported ledger version"
    assert validate_people(json_array(state["people"])) == people, "people differ from the saved ledger"
    balances(state)
    return state


def propose(state: Json, event: Json) -> Json:
    name: str = identifier(event)
    # Idempotency may skip applying an event, but never its schema validation.
    people: list[str] = validate_people(json_array(state["people"]))
    kind: str = json_string(event["op"])
    if kind == "expense":
        allocate(event, people)
    else:
        assert kind == "settle", "unknown transaction kind"
        sender: str = json_string(event["from"])
        recipient: str = json_string(event["to"])
        assert sender in people and recipient in people and sender != recipient, "invalid settlement parties"
        assert json_int(event["cents"]) > 0, "settlement must use positive integer cents"
    events: list[Json] = json_array(state["events"])
    for previous in events:
        if identifier(previous) == name:
            assert json_equal(previous, event), "transaction ID conflicts with earlier content"
            return {"status": "duplicate", "state": state}
    events.append(event)
    following: Json = {"version": 1, "people": state["people"], "events": events}
    # Replaying the proposed ledger checks the new event against its actual
    # balance and cannot partially mutate the caller's state on failure.
    balances(following)
    return {"status": "accepted", "state": following}


def save(state: Json) -> None:
    write_text_atomic(state_path(), pretty(state))
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def audit(state: Json) -> list[Json]:
    people: list[str] = validate_people(json_array(state["people"]))
    rows: list[Json] = []
    for event in json_array(state["events"]):
        if json_string(event["op"]) == "expense":
            rows.append(
                {
                    "id": identifier(event),
                    "kind": "expense",
                    "cents": event["cents"],
                    "payer": event["payer"],
                    "allocation": allocate(event, people),
                }
            )
        else:
            rows.append(
                {
                    "id": identifier(event),
                    "kind": "settle",
                    "cents": event["cents"],
                    "from": event["from"],
                    "to": event["to"],
                }
            )
    return rows


def settlement_plan(state: Json) -> list[Json]:
    people: list[str] = validate_people(json_array(state["people"]))
    current: dict[str, int] = balances(state)
    plan: list[Json] = []
    for debtor in people:
        if current[debtor] < 0:
            for creditor in people:
                if current[creditor] > 0 and current[debtor] < 0:
                    amount: int = min(-current[debtor], current[creditor])
                    plan.append({"from": debtor, "to": creditor, "cents": amount})
                    current[debtor] = current[debtor] + amount
                    current[creditor] = current[creditor] - amount
    for person in people:
        assert current[person] == 0, "settlement plan leaves an outstanding balance"
    return plan


def totals(state: Json) -> Json:
    purchases: int = 0
    refunds: int = 0
    settled: int = 0
    expense_count: int = 0
    for event in json_array(state["events"]):
        amount: int = json_int(event["cents"])
        if json_string(event["op"]) == "expense":
            expense_count = expense_count + 1
            if amount >= 0:
                purchases = purchases + amount
            else:
                refunds = refunds - amount
        else:
            settled = settled + amount
    current: dict[str, int] = balances(state)
    outstanding: int = 0
    for name in validate_people(json_array(state["people"])):
        if current[name] > 0:
            outstanding = outstanding + current[name]
    return {
        "expense_count": expense_count,
        "purchases": purchases,
        "refunds": refunds,
        "net_expenses": purchases - refunds,
        "settled": settled,
        "outstanding": outstanding,
    }
