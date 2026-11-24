"""Parse decimal quantities, check dimensions before arithmetic, and verify conversion round trips."""

# ruff: noqa: BLE001 - explicit bounded numeric validation
from parsing import parse
from units import Unit, dimension_name

from py2rust.stdlib import (
    Json,
    json_array,
    json_kind,
    json_string,
    regex_capture,
    regex_fullmatch,
)


def text(value: Json) -> str:
    assert json_kind(value) == "string", "expected text"
    return json_string(value)


def identifier(value: Json) -> str:
    name: str = text(value)
    assert regex_fullmatch("[A-Za-z][A-Za-z0-9_-]{0,31}", name), "invalid conversion identifier"
    return name


def number(value: str) -> float:
    try:
        assert regex_fullmatch("[-+0-9_eE.]+", value), "expected ASCII decimal text"
        parsed: float = float(value)
        mantissa: str = value.lower().split("e")[0].replace("_", "").strip("+-0.")
        assert -1e100 <= parsed <= 1e100 and (parsed == 0.0 or abs(parsed) >= 1e-100), "quantity out of range"
        assert parsed != 0.0 or mantissa == "", "quantity underflow"
        return 0.0 if parsed == 0.0 else parsed
    except Exception:
        assert False, "quantity out of range"
    return 0.0


def describe(unit: Unit) -> Json:
    return {
        "factor": unit.factor,
        "offset": unit.offset,
        "dimensions": unit.powers,
        "base_unit": dimension_name(unit.powers),
    }


def convert(quantity: str, destination: str, available: dict[str, Unit]) -> Json:
    assert 1 <= len(quantity) <= 256, "quantity text length limit"
    captured: Json = regex_capture("([^ \\t]+)[ \\t]+(.+)", quantity.strip(" \t"), True)
    assert captured is not None, "expected decimal quantity and unit"
    groups: list[Json] = json_array(captured["groups"])
    value: float = number(json_string(groups[1]))
    source_text: str = json_string(groups[2])
    source: Unit = parse(source_text, available)
    target: Unit = parse(destination, available)
    assert source.powers == target.powers, "incompatible dimensions"
    base: float = value * source.factor + source.offset
    converted: float = (base - target.offset) / target.factor
    assert -1e100 <= converted <= 1e100 and (converted == 0.0 or abs(converted) >= 1e-100), "result out of range"
    recovered: float = (converted * target.factor + target.offset - source.offset) / source.factor
    tolerance: float = max(1e-12, abs(value) * 1e-12)
    error: float = abs(recovered - value)
    assert error <= tolerance, "round trip loses precision"
    return {
        "value": value,
        "source_unit": source_text,
        "target_unit": destination,
        "source": describe(source),
        "target": describe(target),
        "base_value": base,
        "converted": 0.0 if converted == 0.0 else converted,
        "round_trip": {"value": recovered, "error": error, "tolerance": tolerance},
    }
