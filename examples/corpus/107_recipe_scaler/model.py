"""Validate a complete cookbook and seven-day plan before scaling any ingredient."""

# ruff: noqa: PLR1711 - explicit returns
from dataclasses import dataclass

from quantities import quantity, unit

from py2rust.stdlib import (
    DateTime,
    Json,
    Rational,
    datetime_add_seconds,
    datetime_iso,
    datetime_parse,
    json_array,
    json_int,
    json_keys,
    json_kind,
    json_string,
    regex_fullmatch,
    unicode_normalize,
)


@dataclass
class Ingredient:
    name: str
    identity: str
    amount: Rational
    unit: str
    base: str
    factor: Rational


@dataclass
class Recipe:
    name: str
    title: str
    servings: Rational
    ingredients: list[Ingredient]


@dataclass
class Selection:
    day: int
    recipe: str
    portions: Rational


@dataclass
class Cookbook:
    week: DateTime
    recipes: dict[str, Recipe]
    selections: list[Selection]


def text(value: Json) -> str:
    assert json_kind(value) == "string", "expected text"
    return json_string(value)


def exact(value: Json, fields: list[str]) -> None:
    assert json_kind(value) == "object", "expected object"
    assert sorted(json_keys(value)) == sorted(fields), "unexpected fields"
    return


def array(value: Json, limit: int) -> list[Json]:
    assert json_kind(value) == "array", "expected array"
    rows: list[Json] = json_array(value)
    assert len(rows) <= limit, "array count limit"
    return rows


def display(value: str) -> str:
    return " ".join(unicode_normalize("NFKC", value).split())


def label(value: Json) -> str:
    raw: str = text(value)
    shown: str = display(raw)
    assert 1 <= len(raw) <= 100 and 1 <= len(shown) <= 100, "label character limit"
    for character in shown:
        assert ord(character) >= 32 and not 127 <= ord(character) <= 159, "control character in label"
    return raw


def day_date(week: DateTime, day: int) -> str:
    return datetime_iso(datetime_add_seconds(week, day * 86400))[:10]


def parse(source: Json) -> Cookbook:
    exact(source, ["version", "week_start", "recipes", "plan"])
    assert json_int(source["version"]) == 1, "unsupported source version"
    start: str = text(source["week_start"])
    assert regex_fullmatch("[0-9]{4}-[0-9]{2}-[0-9]{2}", start), "expected ISO week-start date"
    week: DateTime = datetime_parse(start + "T00:00:00Z")
    day_date(week, 6)
    recipes: dict[str, Recipe] = {}
    numeric_characters: int = 0
    ingredient_count: int = 0
    for row in array(source["recipes"], 32):
        exact(row, ["id", "title", "servings", "ingredients"])
        name: str = text(row["id"])
        assert regex_fullmatch("[A-Za-z][A-Za-z0-9_-]{0,31}", name), "invalid recipe identifier"
        assert name not in recipes, "duplicate recipe identifier"
        title: str = label(row["title"])
        servings: str = text(row["servings"])
        numeric_characters = numeric_characters + len(servings)
        ingredients: list[Ingredient] = []
        for item in array(row["ingredients"], 256):
            exact(item, ["name", "quantity", "unit"])
            ingredient: str = label(item["name"])
            identity: str = display(ingredient).casefold()
            spelling: str = text(item["quantity"])
            symbol: str = text(item["unit"])
            conversion: tuple[str, Rational] = unit(symbol)
            numeric_characters = numeric_characters + len(spelling)
            ingredients.append(
                Ingredient(ingredient, identity, quantity(spelling, False), symbol, conversion[0], conversion[1])
            )
        ingredient_count = ingredient_count + len(ingredients)
        assert ingredient_count <= 256, "total ingredient limit"
        recipes[name] = Recipe(name, title, quantity(servings, True), ingredients)
    selections: list[Selection] = []
    for row in array(source["plan"], 64):
        exact(row, ["day", "recipe", "portions"])
        day: int = json_int(row["day"])
        name: str = text(row["recipe"])
        assert 0 <= day <= 6 and name in recipes, "invalid plan day or recipe reference"
        portions: str = text(row["portions"])
        numeric_characters = numeric_characters + len(portions)
        selections.append(Selection(day, name, quantity(portions, True)))
    assert numeric_characters <= 8192, "total quantity character limit"
    return Cookbook(week, recipes, selections)
