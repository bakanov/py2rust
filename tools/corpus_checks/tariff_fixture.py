"""Independent tariff oracle using exact Fraction intersections on time and cumulative-energy axes."""

from __future__ import annotations

import bisect
import datetime as dt
import hashlib
import itertools
import json
from fractions import Fraction

EPOCH = dt.datetime(1970, 1, 1, tzinfo=dt.timezone.utc)
START = dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc)


def canonical(value: object) -> bytes:
    return (
        json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False, separators=(",", ":")) + "\n"
    ).encode()


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def seconds(text: str) -> int:
    delta = dt.datetime.fromisoformat(text).astimezone(dt.timezone.utc) - EPOCH
    assert delta.microseconds == 0
    return delta.days * 86400 + delta.seconds


def utc(value: int) -> str:
    return (EPOCH + dt.timedelta(seconds=value)).isoformat(timespec="microseconds")


def at(offset: int, base: dt.datetime = START) -> str:
    return (base + dt.timedelta(seconds=offset)).isoformat()


def fixed(value: Fraction, places: int) -> str:
    rounded = round(value * 10**places)
    sign = "-" if rounded < 0 else ""
    digits = str(abs(rounded)).zfill(places + 1)
    return sign + (digits[:-places] + "." + digits[-places:] if places else digits)


def ratio(value: Fraction) -> dict:
    return {"numerator": str(value.numerator), "denominator": str(value.denominator)}


def unr(value: dict) -> Fraction:
    return Fraction(int(value["numerator"]), int(value["denominator"]))


def flat(name: str = "flat", rate: str = "0.25", fee: str = "1") -> dict:
    return {
        "id": name,
        "fee": fee,
        "bands": [{"start_second": 0, "rate": rate}],
        "tiers": [{"up_to_kwh": None, "surcharge": "0"}],
    }


def document() -> dict:
    return {
        "version": 1,
        "period": {"start": at(0), "end": at(172800)},
        "intervals": [
            {"start": at(21599), "end": at(21602), "kwh": "1"},
            {"start": at(86398), "end": at(86402), "kwh": "3"},
            {"start": at(108000), "end": at(111600), "kwh": "4"},
        ],
        "tariffs": [
            flat(),
            {
                "id": "time",
                "fee": "0.75",
                "bands": [
                    {"start_second": 0, "rate": "0.10"},
                    {"start_second": 21600, "rate": "0.30"},
                    {"start_second": 79200, "rate": "0.15"},
                ],
                "tiers": [
                    {"up_to_kwh": "2", "surcharge": "0"},
                    {"up_to_kwh": "5", "surcharge": "0.05"},
                    {"up_to_kwh": None, "surcharge": "0.10"},
                ],
            },
            flat("twin"),
        ],
    }


def expected_bill(source: dict, tariff: dict) -> dict:
    segments, consumed, charge = [], Fraction(0), Fraction(0)
    starts = [band["start_second"] for band in tariff["bands"]]
    for index, interval in enumerate(source["intervals"]):
        first, last = seconds(interval["start"]), seconds(interval["end"])
        boundaries = {first, last}
        for day in range(first // 86400, last // 86400 + 1):
            boundaries.update(day * 86400 + start for start in starts if first < day * 86400 + start < last)
        cuts = sorted(boundaries)
        for left, right in itertools.pairwise(cuts):
            band = bisect.bisect_right(starts, left % 86400) - 1
            energy = Fraction(interval["kwh"]) * Fraction(right - left, last - first)
            end_energy = consumed + energy
            lower, subtotal, allocations = Fraction(0), Fraction(0), []
            for tier_index, tier in enumerate(tariff["tiers"]):
                upper = Fraction(tier["up_to_kwh"]) if tier["up_to_kwh"] is not None else end_energy
                amount = max(Fraction(0), min(end_energy, upper) - max(consumed, lower))
                if amount:
                    rate = Fraction(tariff["bands"][band]["rate"]) + Fraction(tier["surcharge"])
                    cost = amount * rate
                    allocations.append(
                        {"tier": tier_index, "kwh": ratio(amount), "rate": fixed(rate, 6), "charge": ratio(cost)}
                    )
                    subtotal += cost
                lower = upper
            assert sum((unr(row["kwh"]) for row in allocations), Fraction(0)) == energy
            consumed = end_energy
            charge += subtotal
            segments.append(
                {
                    "interval": index,
                    "start": utc(left),
                    "end": utc(right),
                    "band": band,
                    "kwh": ratio(energy),
                    "charge": ratio(subtotal),
                    "allocations": allocations,
                }
            )
    assert consumed == sum((Fraction(row["kwh"]) for row in source["intervals"]), Fraction(0))
    fee = Fraction(tariff["fee"])
    return {
        "id": tariff["id"],
        "kwh": ratio(consumed),
        "energy_charge": ratio(charge),
        "fee": ratio(fee),
        "total": ratio(charge + fee),
        "rounded_total": fixed(charge + fee, 2),
        "segments": segments,
    }


def expected(source: dict) -> dict:
    bills = [expected_bill(source, tariff) for tariff in source["tariffs"]]
    ordered = sorted(bills, key=lambda bill: (unr(bill["total"]), bill["id"]))
    return {
        "period": {key: utc(seconds(value)) for key, value in source["period"].items()},
        "bills": bills,
        "ranking": [bill["id"] for bill in ordered],
        "cheapest": [bill["id"] for bill in ordered if bill["total"] == ordered[0]["total"]],
    }
