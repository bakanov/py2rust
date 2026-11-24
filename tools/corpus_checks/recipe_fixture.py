"""Independent exact quantities, Unicode grouping and weekly-plan oracle."""

from __future__ import annotations

import datetime as dt
import decimal
import hashlib
import json
import unicodedata
from fractions import Fraction

UNITS = {
    "mg": ("g", Fraction(1, 1000)),
    "g": ("g", Fraction(1)),
    "kg": ("g", Fraction(1000)),
    "mL": ("mL", Fraction(1)),
    "cL": ("mL", Fraction(10)),
    "L": ("mL", Fraction(1000)),
    "piece": ("piece", Fraction(1)),
    "dozen": ("piece", Fraction(12)),
}


def canonical(value: object) -> bytes:
    return (
        json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False, separators=(",", ":")) + "\n"
    ).encode()


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def number(text: str) -> Fraction:
    return sum((Fraction(part) for part in text.split(" ")), Fraction(0))


def rendered(value: Fraction) -> str:
    # Decimal(int) is exact and independent of CPython's int-to-string digit cap.
    numerator = format(decimal.Decimal(value.numerator), "f")
    denominator = format(decimal.Decimal(value.denominator), "f")
    return numerator if denominator == "1" else numerator + "/" + denominator


def display(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).split())


def ingredient(name: str, quantity: str, unit: str) -> dict:
    return {"name": name, "quantity": quantity, "unit": unit}


def recipe(name: str, servings: str, rows: list[dict]) -> dict:
    return {"id": name, "title": name.title(), "servings": servings, "ingredients": rows}


def document() -> dict:
    return {
        "version": 1,
        "week_start": "2026-10-19",
        "recipes": [
            recipe(
                "pancakes",
                "4",
                [
                    ingredient(" Flour ", "1/2", "kg"),
                    ingredient("MILK", "250", "mL"),
                    ingredient("Egg", "2", "piece"),
                    ingredient("Salt", "0", "g"),
                ],
            ),
            recipe(
                "bread",
                "3",
                [
                    ingredient("flour", "1 1/2", "kg"),
                    ingredient("ｍｉｌｋ", "1/4", "L"),
                    ingredient("egg", "1/2", "dozen"),
                    ingredient("Salt", "500", "mg"),
                    ingredient("Straße", "1/3", "g"),
                    ingredient("milk", "1", "g"),
                ],
            ),
            recipe("snack", "1 1/2", [ingredient("STRASSE", "2/3", "g"), ingredient("water", "1/5", "cL")]),
        ],
        "plan": [
            {"day": 0, "recipe": "pancakes", "portions": "2"},
            {"day": 2, "recipe": "bread", "portions": "1"},
            {"day": 6, "recipe": "snack", "portions": "1/2"},
            {"day": 2, "recipe": "pancakes", "portions": "1"},
        ],
    }


def expected(source: dict) -> dict:
    start = dt.date.fromisoformat(source["week_start"])
    days = [(start + dt.timedelta(days=n)).isoformat() for n in range(7)]
    recipes = {row["id"]: row for row in source["recipes"]}
    selections, groups = [], {}
    for index, choice in enumerate(source["plan"]):
        original = recipes[choice["recipe"]]
        factor = number(choice["portions"]) / number(original["servings"])
        scaled = []
        for position, item in enumerate(original["ingredients"]):
            amount = number(item["quantity"]) * factor
            base, conversion = UNITS[item["unit"]]
            identity = display(item["name"]).casefold()
            scaled.append(
                {
                    "ingredient": position,
                    "name": item["name"],
                    "identity": identity,
                    "quantity": rendered(amount),
                    "unit": item["unit"],
                    "base_quantity": rendered(amount * conversion),
                    "base_unit": base,
                }
            )
            group = groups.setdefault((identity, base), {"name": display(item["name"]), "values": [], "details": []})
            group["values"].append(amount * conversion)
            group["details"].append(
                {
                    "selection": index,
                    "recipe": original["id"],
                    "ingredient": position,
                    "quantity": rendered(amount * conversion),
                }
            )
        selections.append(
            {
                "day": choice["day"],
                "date": days[choice["day"]],
                "recipe": original["id"],
                "title": original["title"],
                "original_servings": rendered(number(original["servings"])),
                "servings": rendered(number(choice["portions"])),
                "factor": rendered(factor),
                "ingredients": scaled,
            }
        )
    shopping = [
        {
            "identity": identity,
            "name": groups[(identity, base)]["name"],
            "unit": base,
            "quantity": rendered(sum(groups[(identity, base)]["values"], Fraction(0))),
            "contributions": groups[(identity, base)]["details"],
        }
        for identity, base in sorted(groups)
    ]
    return {"week_start": days[0], "days": days, "selections": selections, "shopping": shopping}


def scaled_source(results: dict, entry: dict) -> dict:
    return {
        "version": 1,
        "week_start": results["week_start"],
        "recipes": [
            {
                "id": entry["recipe"],
                "title": entry["title"],
                "servings": entry["servings"],
                "ingredients": [
                    {key: row[key] for key in ["name", "quantity", "unit"]} for row in entry["ingredients"]
                ],
            }
        ],
        "plan": [{"day": entry["day"], "recipe": entry["recipe"], "portions": entry["servings"]}],
    }
