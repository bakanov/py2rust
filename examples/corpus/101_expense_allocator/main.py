"""Import expense and settlement records, preserve rejected inputs, and report exact cents."""

import sys

from allocation import validate_people
from ledger import audit, balances, initialize, propose, save, settlement_plan, totals

from py2rust.stdlib import (
    Json,
    env_get,
    json_array,
    json_loads,
    json_string,
    pretty,
    read_text,
    write_text_atomic,
)


def main() -> None:
    document: Json = json_loads(read_text(env_get("EXPENSE_INPUT", "expenses.json")))
    people: list[str] = validate_people(json_array(document["people"]))
    events: list[Json] = json_array(document["operations"])
    assert len(events) <= 1000, "import exceeds 1000 transactions"
    state: Json = initialize(people)
    outcomes: list[Json] = []
    errors: int = 0
    index: int = 0
    for event in events:
        needs_save: bool = False
        try:
            result: Json = propose(state, event)
            state = result["state"]
            outcomes.append({"index": index, "id": event["id"], "status": result["status"]})
            needs_save = json_string(result["status"]) == "accepted"
        except Exception:  # noqa: BLE001 - recoverable domain validation uses the profile Exception boundary
            outcomes.append({"index": index, "event": event, "status": "rejected"})
            errors = errors + 1
        else:
            # Persistence failures stop the import; they must never be reported
            # as a rejected domain operation followed by further writes.
            if needs_save:
                save(state)
        index = index + 1
    report: Json = {
        "outcomes": outcomes,
        "rejected": errors,
        "balances": balances(state),
        "audit": audit(state),
        "suggested_settlements": settlement_plan(state),
        "totals": totals(state),
    }
    write_text_atomic(env_get("EXPENSE_REPORT", "expense-report.json"), pretty(report))
    print(pretty(report))
    if errors > 0:
        sys.exit(1)
    return  # noqa: PLR1711 - explicit return required by repository guidelines


if __name__ == "__main__":
    main()
