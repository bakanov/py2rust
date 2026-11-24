"""Explicit numeric subset rules; Python spellings are not Rust semantics.

All operands are evaluated once, left to right. Integer overflow, invalid shifts
and division by zero are recoverable errors. Booleans are not integer operands.
Mixed operands must have been converted explicitly before selecting a rule.
"""

from dataclasses import dataclass


@dataclass
class NumericRule:
    key: str
    form: str
    target: str
    result: str


def select_numeric_rule(operator: str, left: str, right: str) -> NumericRule:
    if left != right or (left != "int" and left != "float"):
        return NumericRule("", "", "", "")
    if operator == "/":
        return NumericRule(left + ".true_divide", "runtime", left + "_true_div", "float")
    if left == "int":
        if operator == "//":
            return NumericRule("int.floor_divide", "runtime", "int_floor_div", "int")
        if operator == "%":
            return NumericRule("int.modulo", "runtime", "int_modulo", "int")
        if operator == "<<":
            return NumericRule("int.shift_left", "runtime", "int_lshift", "int")
        if operator == ">>":
            return NumericRule("int.shift_right", "runtime", "int_rshift", "int")
        if operator == "&" or operator == "|" or operator == "^":
            return NumericRule("int.bitwise." + operator, "infix", operator, "int")
        if operator == "+":
            return NumericRule("int.add", "checked", "checked_add", "int")
        if operator == "-":
            return NumericRule("int.subtract", "checked", "checked_sub", "int")
        if operator == "*":
            return NumericRule("int.multiply", "checked", "checked_mul", "int")
    if left == "float" and (operator == "+" or operator == "-" or operator == "*"):
        return NumericRule("float.finite." + operator, "finite", operator, "float")
    return NumericRule("", "", "", "")


def render_numeric(rule: NumericRule, left: str, right: str) -> str:
    if rule.form == "runtime":
        return "rt::" + rule.target + "(" + left + ", " + right + ")?"
    if rule.form == "checked":
        return "(" + left + ")." + rule.target + "(" + right + ').ok_or("integer overflow")?'
    if rule.form == "finite":
        return "rt::finite(" + left + " " + rule.target + " " + right + ")?"
    if rule.form == "infix":
        return "(" + left + " " + rule.target + " " + right + ")"
    return ""


def select_unary_rule(operator: str, operand: str) -> NumericRule:
    if operator == "not" and operand == "bool":
        return NumericRule("bool.not", "prefix", "!", "bool")
    if operator == "~" and operand == "int":
        return NumericRule("int.invert", "prefix", "!", "int")
    if operator == "-" and operand == "int":
        return NumericRule("int.negate", "checked_unary", "checked_neg", "int")
    if operator == "-" and operand == "float":
        return NumericRule("float.negate", "prefix", "-", "float")
    if operator == "abs" and operand == "int":
        return NumericRule("int.absolute", "checked_unary", "checked_abs", "int")
    if operator == "abs" and operand == "float":
        return NumericRule("float.absolute", "finite_unary", "abs", "float")
    return NumericRule("", "", "", "")


def render_unary(rule: NumericRule, operand: str) -> str:
    if rule.form == "prefix":
        return rule.target + "(" + operand + ")"
    if rule.form == "checked_unary":
        return "(" + operand + ")." + rule.target + '().ok_or("integer overflow")?'
    if rule.form == "finite_unary":
        return "rt::finite((" + operand + ")." + rule.target + "())?"
    return ""
