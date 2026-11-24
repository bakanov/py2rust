"""Independent standings oracle: scan each team's fixtures and rank by counting stronger records."""

from __future__ import annotations

import hashlib
import json
import unicodedata


def canonical(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode()


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def display(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).split())


def fixture(name: str, home: str, away: str, left: int | None, right: int | None) -> dict:
    return {"id": name, "home": home, "away": away, "home_score": left, "away_score": right}


def document() -> dict:
    return {
        "version": 1,
        "title": "Four-team demonstration",
        "teams": [
            {"id": name, "name": label}
            for name, label in [("A", "Aurora"), ("B", "Birch"), ("C", "Cedar"), ("D", "Delta")]
        ],
        "fixtures": [
            fixture("ab", "A", "B", 2, 0),
            fixture("ac", "A", "C", 1, 1),
            fixture("ad", "A", "D", None, None),
            fixture("bc", "B", "C", 2, 1),
            fixture("bd", "B", "D", 0, 0),
            fixture("cd", "C", "D", 3, 1),
        ],
    }


def expected(source: dict) -> dict:
    completed = [row for row in source["fixtures"] if row["home_score"] is not None]
    table = []
    for team in source["teams"]:
        played = []
        for match in completed:
            if team["id"] == match["home"]:
                played.append((match["id"], match["away"], match["home_score"], match["away_score"]))
            elif team["id"] == match["away"]:
                played.append((match["id"], match["home"], match["away_score"], match["home_score"]))
        wins = sum(left > right for _, _, left, right in played)
        draws = sum(left == right for _, _, left, right in played)
        goals_for = sum(left for _, _, left, _ in played)
        goals_against = sum(right for _, _, _, right in played)
        table.append(
            {
                "id": team["id"],
                "name": team["name"],
                "played": len(played),
                "won": wins,
                "drawn": draws,
                "lost": len(played) - wins - draws,
                "goals_for": goals_for,
                "goals_against": goals_against,
                "difference": goals_for - goals_against,
                "points": 3 * wins + draws,
                "contributions": [
                    {
                        "fixture": name,
                        "opponent": opponent,
                        "goals_for": left,
                        "goals_against": right,
                        "points": 3 if left > right else int(left == right),
                        "outcome": "win" if left > right else "draw" if left == right else "loss",
                    }
                    for name, opponent, left, right in played
                ],
            }
        )
    keys = [(row["points"], row["difference"], row["goals_for"]) for row in table]
    for row, key in zip(table, keys):
        row["rank"] = 1 + sum(other > key for other in keys)
    table.sort(key=lambda row: (row["rank"], row["id"]))
    decisive = sum(row["home_score"] != row["away_score"] for row in completed)
    assert sum(row["won"] for row in table) == sum(row["lost"] for row in table) == decisive
    assert sum(row["drawn"] for row in table) == 2 * (len(completed) - decisive)
    assert sum(row["points"] for row in table) == 3 * decisive + 2 * (len(completed) - decisive)
    assert sum(row["goals_for"] for row in table) == sum(row["goals_against"] for row in table)
    count = len(source["teams"])
    possible = count * (count - 1) // 2
    return {
        "title": source["title"],
        "teams": count,
        "possible_fixtures": possible,
        "scheduled": len(source["fixtures"]),
        "played": len(completed),
        "unplayed": len(source["fixtures"]) - len(completed),
        "unscheduled": possible - len(source["fixtures"]),
        "draws": len(completed) - decisive,
        "leaders": [row["id"] for row in table if row["rank"] == 1],
        "standings": table,
    }
