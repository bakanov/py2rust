"""Bounded exact rational arithmetic for the service profile."""

import re
from fractions import Fraction

Rational = Fraction
_BITS = 65536


def _checked(value: Fraction) -> Rational:
    if value.numerator.bit_length() > _BITS or value.denominator.bit_length() > _BITS:
        raise ValueError("rational exceeds 65536 bits")
    return value


def _parse(text: str) -> int:
    if not 1 <= len(text) <= 4096 or re.fullmatch(r"[+-]?[0-9]+", text) is None:
        raise ValueError("expected 1..4096 characters of signed ASCII integer")
    digits = text.lstrip("+-")
    value = 0
    for start in range(0, len(digits), 9):
        chunk = digits[start : start + 9]
        value = value * 10 ** len(chunk) + int(chunk)
    return -value if text.startswith("-") else value


def _text(value: int) -> str:
    negative = value < 0
    value = abs(value)
    chunks = []
    while value:
        value, remainder = divmod(value, 1000000000)
        chunks.append(remainder)
    if not chunks:
        return "0"
    return ("-" if negative else "") + str(chunks[-1]) + "".join(f"{n:09d}" for n in reversed(chunks[:-1]))


def rational_new(numerator: str, denominator: str) -> Rational:
    return _checked(Fraction(_parse(numerator), _parse(denominator)))


def rational_decimal(text: str) -> Rational:
    if not 1 <= len(text) <= 4096 or re.fullmatch(r"[+-]?[0-9]+(?:\.[0-9]+)?", text) is None:
        raise ValueError("expected 1..4096 characters of finite ASCII decimal")
    places = len(text) - text.index(".") - 1 if "." in text else 0
    return _checked(Fraction(_parse(text.replace(".", "")), 10**places))


def rational_add(left: Rational, right: Rational) -> Rational:
    return _checked(left + right)


def rational_sub(left: Rational, right: Rational) -> Rational:
    return _checked(left - right)


def rational_mul(left: Rational, right: Rational) -> Rational:
    return _checked(left * right)


def rational_div(left: Rational, right: Rational) -> Rational:
    return _checked(left / right)


def rational_compare(left: Rational, right: Rational) -> int:
    return (left > right) - (left < right)


def rational_numerator(value: Rational) -> str:
    return _text(value.numerator)


def rational_denominator(value: Rational) -> str:
    return _text(value.denominator)


def rational_fixed(value: Rational, places: int) -> str:
    """Round once, ties to even, with exactly 0..18 decimal places and no negative zero."""
    if not 0 <= places <= 18:
        raise ValueError("decimal places must be 0..18")
    quotient, remainder = divmod(abs(value.numerator) * 10**places, value.denominator)
    twice = remainder * 2
    if twice > value.denominator or (twice == value.denominator and quotient % 2):
        quotient += 1
    digits = _text(quotient).zfill(places + 1)
    if places:
        digits = digits[:-places] + "." + digits[-places:]
    return ("-" if value < 0 and quotient else "") + digits
