"""Scale every ingredient exactly and group compatible shopping quantities with complete provenance."""


from dataclasses import dataclass

from model import Cookbook, Ingredient, Recipe, Selection, day_date, display
from quantities import rendered

from py2rust.stdlib import (
    Json,
    Rational,
    rational_add,
    rational_decimal,
    rational_div,
    rational_mul,
)


@dataclass
class Group:
    identity: str
    name: str
    unit: str
    total: Rational
    indices: list[int]


def plan(book: Cookbook) -> Json:
    groups: dict[str, Group] = {}
    contributions: list[Json] = []
    selections: list[Json] = []
    days: list[str] = []
    for day in range(7):
        days.append(day_date(book.week, day))
    for index in range(len(book.selections)):
        selection: Selection = book.selections[index]
        recipe: Recipe = book.recipes[selection.recipe]
        factor: Rational = rational_div(selection.portions, recipe.servings)
        scaled: list[Json] = []
        for position in range(len(recipe.ingredients)):
            ingredient: Ingredient = recipe.ingredients[position]
            amount: Rational = rational_mul(ingredient.amount, factor)
            base: Rational = rational_mul(amount, ingredient.factor)
            scaled.append(
                {
                    "ingredient": position,
                    "name": ingredient.name,
                    "identity": ingredient.identity,
                    "quantity": rendered(amount),
                    "unit": ingredient.unit,
                    "base_quantity": rendered(base),
                    "base_unit": ingredient.base,
                }
            )
            key: str = ingredient.identity + "\x00" + ingredient.base
            if key not in groups:
                groups[key] = Group(
                    ingredient.identity, display(ingredient.name), ingredient.base, rational_decimal("0"), []
                )
            group: Group = groups[key]
            group.total = rational_add(group.total, base)
            # Keep small indices in owned groups; store each provenance record once.
            group.indices = group.indices + [len(contributions)]
            contributions.append(
                {"selection": index, "recipe": recipe.name, "ingredient": position, "quantity": rendered(base)}
            )
            groups[key] = group
        selections.append(
            {
                "day": selection.day,
                "date": days[selection.day],
                "recipe": recipe.name,
                "title": recipe.title,
                "original_servings": rendered(recipe.servings),
                "servings": rendered(selection.portions),
                "factor": rendered(factor),
                "ingredients": scaled,
            }
        )
    shopping: list[Json] = []
    for key in sorted(groups):
        item: Group = groups[key]
        details: list[Json] = []
        for index in item.indices:
            details.append(contributions[index])
        shopping.append(
            {
                "identity": item.identity,
                "name": item.name,
                "unit": item.unit,
                "quantity": rendered(item.total),
                "contributions": details,
            }
        )
    return {"week_start": days[0], "days": days, "selections": selections, "shopping": shopping}
