"""Independent Counter-based accounting model and canonical audit oracle for application 102."""

from __future__ import annotations

import copy
import hashlib
import json
import re
from collections import Counter
from typing import Any


def canonical(value: Any) -> bytes:
    def encode(item: Any) -> str:
        if type(item) is float:
            mantissa, exponent = format(item, ".16e").split("e")
            return mantissa.rstrip("0").rstrip(".") + "e" + str(int(exponent))
        if isinstance(item, dict):
            return "{" + ",".join(json.dumps(k, ensure_ascii=False) + ":" + encode(item[k]) for k in sorted(item)) + "}"
        if isinstance(item, list):
            return "[" + ",".join(encode(child) for child in item) + "]"
        return json.dumps(item, ensure_ascii=False, allow_nan=False, separators=(",", ":"))

    return (encode(value) + "\n").encode()


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def event(name: str, kind: str, items: dict | None = None, order: str | None = None) -> dict:
    result = {"id": name, "op": kind}
    if kind != "cancel":
        result["items"] = {} if items is None else items
    if order is not None:
        result["order"] = order
    return result


def new_ledger(items: list[str]) -> dict:
    items = sorted(items)
    return {
        "version": 1,
        "items": items,
        "revision": 0,
        "head": digest(canonical({"version": 1, "items": items})),
        "events": [],
        "state": {"stock": dict.fromkeys(items, 0), "orders": {}},
    }


def balances(state: dict) -> dict:
    totals: Counter = Counter()
    for row in state["orders"].values():
        assert row["status"] in {"active", "released", "cancelled"}
        assert bool(row["items"]) == (row["status"] == "active")
        assert all(type(q) is int and q > 0 for q in row["items"].values())
        totals.update(row["items"])
    assert set(totals) <= set(state["stock"])
    result = {}
    for sku, count in sorted(state["stock"].items()):
        assert type(count) is int and 0 <= totals[sku] <= count <= 10**9
        result[sku] = {"on_hand": count, "reserved": totals[sku], "available": count - totals[sku]}
    return result


def shape(row: Any, items: list[str]) -> str:
    def identifier(value: Any) -> bool:
        return isinstance(value, str) and re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{0,31}", value) is not None

    if not isinstance(row, dict):
        return "expected transaction object"
    if not {"id", "op"} <= row.keys():
        return "transaction fields missing"
    if not identifier(row["id"]):
        return "invalid identifier"
    if not isinstance(row["op"], str):
        return "invalid transaction kind"
    kind = row["op"]
    if kind not in {"receive", "reserve", "release", "cancel", "reconcile"}:
        return "unknown transaction"
    keys = {"id", "op"} | ({"order"} if kind in {"reserve", "release", "cancel"} else set())
    keys |= {"items"} if kind != "cancel" else set()
    if row.keys() != keys:
        return "unexpected fields"
    if "order" in keys and not identifier(row["order"]):
        return "invalid identifier"
    if kind != "cancel":
        if not isinstance(row["items"], dict):
            return "expected transaction items"
        if not 1 <= len(row["items"]) <= 32:
            return "transaction item limit"
        for sku, quantity in row["items"].items():
            if sku not in items:
                return "unknown item"
            if type(quantity) is not int or not (0 if kind == "reconcile" else 1) <= quantity <= 10**9:
                return "invalid quantity"
    return ""


def movement(state: dict, row: dict) -> tuple[dict, str]:
    """Check a complete vector before applying it; allocations are independent Counters."""
    stock = Counter(state["stock"])
    orders = copy.deepcopy(state["orders"])
    held = Counter()
    for allocation in orders.values():
        held.update(allocation["items"])
    kind, quantities = row["op"], Counter(row.get("items", {}))
    if kind in {"receive", "reconcile"}:
        proposed = {sku: stock[sku] + q if kind == "receive" else q for sku, q in quantities.items()}
        for sku in sorted(proposed):
            if proposed[sku] > 10**9:
                return state, "stock quantity limit"
            if proposed[sku] < held[sku]:
                return state, "count below existing reservations"
        stock.update({sku: value - stock[sku] for sku, value in proposed.items()})
    elif kind == "reserve":
        if row["order"] in orders:
            return state, "order identifier already used"
        if len(orders) == 128:
            return state, "order count limit"
        if any(q > stock[sku] - held[sku] for sku, q in quantities.items()):
            return state, "insufficient available stock"
        orders[row["order"]] = {"status": "active", "items": dict(quantities)}
    else:
        name = row["order"]
        if name not in orders:
            return state, "unknown order"
        if orders[name]["status"] != "active":
            return state, "order is already closed"
        allocated = Counter(orders[name]["items"])
        if kind == "release":
            if any(q > allocated[sku] for sku, q in quantities.items()):
                return state, "release exceeds reservation"
            remaining = dict(allocated - quantities)
            orders[name] = {"status": "active" if remaining else "released", "items": remaining}
        else:
            orders[name] = {"status": "cancelled", "items": {}}
    following = {"stock": dict(stock), "orders": orders}
    balances(following)
    return following, ""


def record(sequence: int, head: str, row: dict, state: dict) -> dict:
    result = {"sequence": sequence, "previous": head, "event": row, "state_sha256": digest(canonical(state))}
    result["hash"] = digest(canonical(result))
    return result


def apply_model(ledger: dict, operations: list) -> tuple[dict, list[dict]]:
    current = copy.deepcopy(ledger)
    seen = {row["event"]["id"]: row["event"] for row in current["events"]}
    outcomes = []
    for index, row in enumerate(operations):
        reason, status = shape(row, current["items"]), "accepted"
        if not reason:
            if row["id"] in seen:
                if canonical(row) == canonical(seen[row["id"]]):
                    status = "duplicate"
                else:
                    reason = "transaction identifier conflicts"
            elif len(seen) == 512:
                reason = "ledger event limit"
            else:
                following, reason = movement(current["state"], row)
                if not reason:
                    current["state"] = following
                    current["revision"] += 1
                    audit = record(current["revision"], current["head"], copy.deepcopy(row), following)
                    current["events"].append(audit)
                    current["head"] = audit["hash"]
                    seen[row["id"]] = row
        if reason:
            outcomes.append({"index": index, "status": "rejected", "event": row, "reason": reason})
        else:
            outcomes.append({"index": index, "status": status, "id": row["id"]})
        balances(current["state"])
    return current, outcomes


def sequence() -> list[dict]:
    return [
        event("receipt", "receive", {"bolt": 20, "nut": 12, "washer": 10}),
        event("a", "reserve", {"bolt": 12, "nut": 6}, "orderA"),
        event("atomic_reserve", "reserve", {"bolt": 2, "nut": 7}, "orderB"),
        event("atomic_release", "release", {"bolt": 1, "nut": 7}, "orderA"),
        event("atomic_count", "reconcile", {"bolt": 15, "nut": 5}),
        event("partial", "release", {"bolt": 2}, "orderA"),
        event("atomic_reserve", "reserve", {"bolt": 10, "washer": 10}, "orderB"),
        event("count", "reconcile", {"bolt": 20, "nut": 6}),
        event("release", "release", {"bolt": 10, "nut": 6}, "orderA"),
        event("cancel", "cancel", order="orderB"),
        event("closed", "cancel", order="orderB"),
        event("reuse", "reserve", {"bolt": 1}, "orderA"),
        event("a", "reserve", {"bolt": 12, "nut": 6}, "orderA"),
        event("a", "reserve", {"bolt": 13, "nut": 6}, "orderA"),
        event("a", "reserve", {"bolt": 12.0, "nut": 6}, "orderA"),
        event("zero", "reconcile", {"bolt": 0, "nut": 0, "washer": 0}),
    ]
