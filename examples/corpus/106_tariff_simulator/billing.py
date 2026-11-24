"""Split uniform interval consumption at UTC band boundaries, then allocate chronological tier energy."""

from model import Band, Interval, Tariff, Tier, Usage, fraction, text, utc

from py2rust.stdlib import (
    Json,
    Rational,
    rational_add,
    rational_compare,
    rational_decimal,
    rational_fixed,
    rational_mul,
    rational_new,
    rational_sub,
)


def price(usage: Usage, tariff: Tariff) -> Json:
    zero: Rational = rational_decimal("0")
    consumed: Rational = zero
    charge: Rational = zero
    tier_index: int = 0
    segments: list[Json] = []
    for index in range(len(usage.intervals)):
        interval: Interval = usage.intervals[index]
        cursor: int = interval.start
        while cursor < interval.end:
            day: int = cursor // 86400 * 86400
            band_index: int = 0
            for candidate in range(len(tariff.bands)):
                if day + tariff.bands[candidate].start <= cursor:
                    band_index = candidate
            band: Band = tariff.bands[band_index]
            boundary: int = day + 86400
            if band_index + 1 < len(tariff.bands):
                boundary = day + tariff.bands[band_index + 1].start
            stop: int = min(interval.end, boundary)
            portion: Rational = rational_new(str(stop - cursor), str(interval.end - interval.start))
            energy: Rational = rational_mul(interval.energy, portion)
            remaining: Rational = energy
            allocations: list[Json] = []
            segment_charge: Rational = zero
            while rational_compare(remaining, zero) > 0:
                tier: Tier = tariff.tiers[tier_index]
                if not tier.unlimited and rational_compare(consumed, tier.limit) == 0:
                    tier_index = tier_index + 1
                else:
                    amount: Rational = remaining
                    if not tier.unlimited:
                        available: Rational = rational_sub(tier.limit, consumed)
                        if rational_compare(available, amount) < 0:
                            amount = available
                    rate: Rational = rational_add(band.rate, tier.rate)
                    cost: Rational = rational_mul(amount, rate)
                    allocations.append(
                        {
                            "tier": tier_index,
                            "kwh": fraction(amount),
                            "rate": rational_fixed(rate, 6),
                            "charge": fraction(cost),
                        }
                    )
                    segment_charge = rational_add(segment_charge, cost)
                    consumed = rational_add(consumed, amount)
                    remaining = rational_sub(remaining, amount)
            charge = rational_add(charge, segment_charge)
            segments.append(
                {
                    "interval": index,
                    "start": utc(cursor),
                    "end": utc(stop),
                    "band": band_index,
                    "kwh": fraction(energy),
                    "charge": fraction(segment_charge),
                    "allocations": allocations,
                }
            )
            cursor = stop
    total: Rational = rational_add(charge, tariff.fee)
    return {
        "id": tariff.name,
        "kwh": fraction(consumed),
        "energy_charge": fraction(charge),
        "fee": fraction(tariff.fee),
        "total": fraction(total),
        "rounded_total": rational_fixed(total, 2),
        "segments": segments,
    }


def total(bill: Json) -> Rational:
    return rational_new(text(bill["total"]["numerator"]), text(bill["total"]["denominator"]))


def simulate(usage: Usage) -> Json:
    bills: list[Json] = []
    order: list[int] = []
    for tariff in usage.tariffs:
        order.append(len(bills))
        bills.append(price(usage, tariff))
    for left in range(len(order)):
        for right in range(left + 1, len(order)):
            comparison: int = rational_compare(total(bills[order[left]]), total(bills[order[right]]))
            if comparison > 0 or (comparison == 0 and text(bills[order[left]]["id"]) > text(bills[order[right]]["id"])):
                saved: int = order[left]
                order[left] = order[right]
                order[right] = saved
    ranking: list[str] = []
    cheapest: list[str] = []
    for index in order:
        ranking.append(text(bills[index]["id"]))
        if rational_compare(total(bills[index]), total(bills[order[0]])) == 0:
            cheapest.append(text(bills[index]["id"]))
    return {
        "period": {"start": utc(usage.start), "end": utc(usage.end)},
        "bills": bills,
        "ranking": ranking,
        "cheapest": cheapest,
    }
