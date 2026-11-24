"""Fraction-based allocation oracle, refunds, replay and settlement conservation."""

import json
import random
from fractions import Fraction
from pathlib import Path

from .common import Application


def reference(event: dict) -> dict[str, int]:
    denominator = sum(item["weight"] for item in event["shares"])
    exact = {item["person"]: Fraction(event["cents"] * item["weight"], denominator) for item in event["shares"]}
    result = {name: amount.numerator // amount.denominator for name, amount in exact.items()}
    ranked = sorted(exact, key=lambda name: (-(exact[name] - result[name]), name))
    for name in ranked[: event["cents"] - sum(result.values())]:
        result[name] += 1
    return result


def check(app: Application, directory: Path) -> dict:
    people = ["Alice", "Bob", "世界"]
    rng = random.Random(101001)
    events = []
    for index, cents in enumerate(
        [1, 2, -1, -2, 0, 1000000000000, -1000000000000] + [rng.randint(-900, 900) for _ in range(35)]
    ):
        weights = [1, 1, 1] if index < 5 else [rng.randint(1, 1000000) for _ in people]
        events.append(
            {
                "op": "expense",
                "id": f"expense-{index}",
                "payer": people[index % 3],
                "cents": cents,
                "shares": [{"person": name, "weight": weight} for name, weight in zip(people, weights)],
            }
        )
    source = directory / "expenses.json"
    state = directory / "state.json"
    target = directory / "report.json"
    settings = {"EXPENSE_INPUT": str(source), "EXPENSE_STATE": str(state), "EXPENSE_REPORT": str(target)}

    def run(operations: list, code: int = 0) -> dict:
        source.write_text(json.dumps({"people": list(reversed(people)), "operations": operations}))
        result = app.run(directory, settings)
        assert result.returncode == code, result.stderr + result.stdout
        report = json.loads(target.read_text())
        assert json.loads(result.stdout) == report
        assert sum(report["balances"].values()) == 0
        return report

    # Split import across fresh processes to exercise persistence and replay.
    run(events[:20])
    report = run(events[20:])
    expected = dict.fromkeys(people, 0)
    for event, row in zip(events, report["audit"], strict=True):
        allocation = reference(event)
        assert row["allocation"] == allocation
        assert sum(allocation.values()) == event["cents"]
        expected[event["payer"]] += event["cents"]
        for name, amount in allocation.items():
            expected[name] -= amount
    assert report["balances"] == expected
    assert report["totals"] == {
        "expense_count": len(events),
        "purchases": sum(max(event["cents"], 0) for event in events),
        "refunds": sum(max(-event["cents"], 0) for event in events),
        "net_expenses": sum(event["cents"] for event in events),
        "settled": 0,
        "outstanding": sum(max(value, 0) for value in expected.values()),
    }
    before = state.read_bytes()
    duplicate = run(events)
    assert all(item["status"] == "duplicate" for item in duplicate["outcomes"])
    assert state.read_bytes() == before
    bad = [
        dict(events[0], cents=1.0),
        dict(events[0], cents=99),
        dict(events[0], id="bad-payer", payer="unknown"),
        dict(events[0], id="zero-weight", shares=[{"person": "Bob", "weight": 0}]),
        dict(events[0], id="duplicate-shares", shares=[{"person": "Bob", "weight": 1}, {"person": "Bob", "weight": 1}]),
        dict(events[0], id="fractional-cents", cents=1.5),
        {"op": "settle", "id": "overpay", "from": "Alice", "to": "Bob", "cents": 9000000000000000},
    ]
    rejected = run(bad, 1)
    assert rejected["rejected"] == len(bad)
    assert state.read_bytes() == before
    assert rejected["balances"] == expected
    payments = [
        dict(item, op="settle", id=f"payment-{index}") for index, item in enumerate(report["suggested_settlements"])
    ]
    settled = run(payments)
    assert all(amount == 0 for amount in settled["balances"].values())
    assert settled["suggested_settlements"] == []
    assert settled["totals"]["outstanding"] == 0
    assert settled["totals"]["settled"] == sum(payment["cents"] for payment in payments)
    assert len(settled["audit"]) == len(events) + len(payments)
    repeated = run(payments)
    assert all(item["status"] == "duplicate" for item in repeated["outcomes"])
    assert repeated["balances"] == dict.fromkeys(people, 0)
    # A ledger with invalid historical allocations/transactions is refused.
    corrupted = json.loads(state.read_text())
    corrupted["events"][0]["shares"][0]["weight"] = 0
    state.write_text(json.dumps(corrupted))
    previous_report = target.read_bytes()
    source.write_text(json.dumps({"people": people, "operations": []}))
    result = app.run(directory, settings)
    assert result.returncode != 0
    assert target.read_bytes() == previous_report
    invalid_parent = directory / "not-a-directory"
    invalid_parent.write_text("unchanged")
    source.write_text(json.dumps({"people": people, "operations": events[:2]}))
    failure = app.run(directory, dict(settings, EXPENSE_STATE=str(invalid_parent / "state.json")))
    assert failure.returncode != 0 and failure.stdout == ""
    assert target.read_bytes() == previous_report and invalid_parent.read_text() == "unchanged"
    return {
        "fraction_oracle_expenses": len(events),
        "balances_before_settlement": expected,
        "settlements": payments,
        "final_balances": dict.fromkeys(people, 0),
        "idempotent_import": True,
        "invalid_operations_rejected": len(bad),
        "corrupt_ledger_rejected": True,
        "storage_failure_stops_import": True,
    }
