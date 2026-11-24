"""Scalar conversion rules for the bounded, finite numeric subset."""

from dataclasses import dataclass


@dataclass
class ConversionRule:
    key: str
    form: str
    target: str
    result: str
    fallible: bool


def select_conversion(target: str, source: str) -> ConversionRule:
    if target == "str":
        if source == "float":
            return ConversionRule("str.float", "runtime_value", "float_to_string", "str", True)
        if source == "str" or source == "int" or source == "Exception":
            return ConversionRule("str." + source, "display", "to_string", "str", False)
    if target == "int" and source == "str":
        return ConversionRule("int.decimal", "runtime_reference", "int_from_decimal", "int", True)
    if target == "float":
        if source == "str":
            return ConversionRule("float.decimal", "runtime_reference", "float_from_decimal", "float", True)
        if source == "int":
            return ConversionRule("float.integer", "cast", "f64", "float", False)
        if source == "float":
            return ConversionRule("float.identity", "identity", "", "float", False)
    return ConversionRule("", "", "", "", False)


def render_conversion(rule: ConversionRule, value: str, reference: str) -> str:
    """Return the expression before Result propagation, as directed by the rule."""
    if rule.form == "runtime_value":
        return "rt::" + rule.target + "(" + value + ")"
    if rule.form == "runtime_reference":
        return "rt::" + rule.target + "(" + reference + ")"
    if rule.form == "display":
        return "(" + value + ").to_string()"
    if rule.form == "cast":
        return "(" + value + " as f64)"
    if rule.form == "identity":
        return value
    return ""
