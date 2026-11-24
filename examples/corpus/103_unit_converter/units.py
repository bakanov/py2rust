"""Explicit conversion factors and SI dimension vectors: m, kg, s, A, K, mol, cd."""

from dataclasses import dataclass


@dataclass
class Unit:
    factor: float
    powers: list[int]
    offset: float


def basis(factor: float, dimension: int) -> Unit:
    powers: list[int] = [0, 0, 0, 0, 0, 0, 0]
    if dimension >= 0:
        powers[dimension] = 1
    return Unit(factor, powers, 0.0)


def catalog() -> dict[str, Unit]:
    # Customary-unit factors follow NIST SP 811; prefixes are explicit and case-sensitive.
    return {
        "1": basis(1.0, -1),
        "m": basis(1.0, 0),
        "km": basis(1000.0, 0),
        "cm": basis(0.01, 0),
        "mm": basis(0.001, 0),
        "um": basis(0.000001, 0),
        "nm": basis(0.000000001, 0),
        "in": basis(0.0254, 0),
        "ft": basis(0.3048, 0),
        "yd": basis(0.9144, 0),
        "mi": basis(1609.344, 0),
        "s": basis(1.0, 2),
        "ms": basis(0.001, 2),
        "us": basis(0.000001, 2),
        "min": basis(60.0, 2),
        "h": basis(3600.0, 2),
        "d": basis(86400.0, 2),
        "kg": basis(1.0, 1),
        "g": basis(0.001, 1),
        "mg": basis(0.000001, 1),
        "lb": basis(0.45359237, 1),
        "A": basis(1.0, 3),
        "mA": basis(0.001, 3),
        "K": basis(1.0, 4),
        "mol": basis(1.0, 5),
        "cd": basis(1.0, 6),
        "delta_degC": basis(1.0, 4),
        "delta_degF": basis(5.0 / 9.0, 4),
        "degC": Unit(1.0, [0, 0, 0, 0, 1, 0, 0], 273.15),
        "degF": Unit(5.0 / 9.0, [0, 0, 0, 0, 1, 0, 0], 459.67 * (5.0 / 9.0)),
        "L": Unit(0.001, [3, 0, 0, 0, 0, 0, 0], 0.0),
        "mL": Unit(0.000001, [3, 0, 0, 0, 0, 0, 0], 0.0),
        "Hz": Unit(1.0, [0, 0, -1, 0, 0, 0, 0], 0.0),
        "N": Unit(1.0, [1, 1, -2, 0, 0, 0, 0], 0.0),
        "Pa": Unit(1.0, [-1, 1, -2, 0, 0, 0, 0], 0.0),
        "kPa": Unit(1000.0, [-1, 1, -2, 0, 0, 0, 0], 0.0),
        "bar": Unit(100000.0, [-1, 1, -2, 0, 0, 0, 0], 0.0),
        "atm": Unit(101325.0, [-1, 1, -2, 0, 0, 0, 0], 0.0),
        "J": Unit(1.0, [2, 1, -2, 0, 0, 0, 0], 0.0),
        "kJ": Unit(1000.0, [2, 1, -2, 0, 0, 0, 0], 0.0),
        "W": Unit(1.0, [2, 1, -3, 0, 0, 0, 0], 0.0),
        "kW": Unit(1000.0, [2, 1, -3, 0, 0, 0, 0], 0.0),
        "C": Unit(1.0, [0, 0, 1, 1, 0, 0, 0], 0.0),
        "V": Unit(1.0, [2, 1, -3, -1, 0, 0, 0], 0.0),
        "ohm": Unit(1.0, [2, 1, -3, -2, 0, 0, 0], 0.0),
    }


def checked(unit: Unit) -> Unit:
    assert 1e-100 <= unit.factor <= 1e100, "unit factor out of range"
    for power in unit.powers:
        assert -32 <= power <= 32, "dimension exponent out of range"
    return unit


def combine(left: Unit, right: Unit, divide: bool) -> Unit:
    powers: list[int] = []
    for index in range(7):
        powers.append(left.powers[index] - right.powers[index] if divide else left.powers[index] + right.powers[index])
    factor: float = left.factor / right.factor if divide else left.factor * right.factor
    return checked(Unit(factor, powers, 0.0))


def power(unit: Unit, exponent: int) -> Unit:
    assert -8 <= exponent <= 8, "power out of range"
    result: Unit = basis(1.0, -1)
    for _index in range(abs(exponent)):
        result = combine(result, unit, exponent < 0)
    return result


def dimension_name(powers: list[int]) -> str:
    names: list[str] = ["m", "kg", "s", "A", "K", "mol", "cd"]
    terms: list[str] = []
    for index in range(7):
        if powers[index] != 0:
            terms.append(names[index] if powers[index] == 1 else names[index] + "^" + str(powers[index]))
    return "1" if len(terms) == 0 else "*".join(terms)
