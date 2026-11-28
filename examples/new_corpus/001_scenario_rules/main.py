"""Load a tiny scenario and exercise shared rules as borrowed and owned values."""

from collections import Counter

from rules import (
    CIVILIZATIONS,
    RuleCatalog,
    available_technologies,
    catalog,
    integer,
    resource_counts,
    terrain_total,
)

from py2rust.stdlib import Json


def main() -> None:
    rules: RuleCatalog = catalog()
    scenario: dict[str, Json] = {"name": "Tiny continents", "discount": 1, "optional": None}
    print("Scenario: " + str(scenario["name"]))
    print("Civilizations: " + ", ".join(CIVILIZATIONS))
    print("Pottery cost: " + str(rules.research_cost("Pottery", integer(scenario, "discount"))))
    print("Optional modifier: " + str(integer(scenario, "optional", 2)))
    known: set[str] = {"Alphabet"}
    print("Available: " + ", ".join(available_technologies(rules, known)))
    yields: tuple[int, int, int] = terrain_total(("grassland", "plains", "forest"))
    print("Worked yields: " + str(yields[0]) + " food, " + str(yields[1]) + " shields")
    counts: Counter[str] = resource_counts(["wheat", "iron", "wheat", "spices", "iron", "wheat"])
    for name in sorted(counts):
        print("Resource " + name + ": " + str(counts[name]))
    missing: int | None = rules.find_technology("Writing")
    print("Missing technology: " + (str(missing) if missing is not None else "None"))
    return


if __name__ == "__main__":
    main()
