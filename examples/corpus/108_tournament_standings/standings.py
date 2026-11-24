"""Recompute every team's metrics and sporting rank from the validated fixture collection."""

# ruff: noqa: PLC0206 - explicit subset dictionary iteration
from dataclasses import dataclass

from model import Fixture, Tournament

from py2rust.stdlib import Json


@dataclass
class Standing:
    identifier: str
    name: str
    played: int
    won: int
    drawn: int
    lost: int
    goals_for: int
    goals_against: int
    points: int


def result_points(scored: int, conceded: int) -> int:
    if scored > conceded:
        return 3
    if scored == conceded:
        return 1
    return 0


def add_result(row: Standing, scored: int, conceded: int) -> Standing:
    row.played = row.played + 1
    row.goals_for = row.goals_for + scored
    row.goals_against = row.goals_against + conceded
    row.points = row.points + result_points(scored, conceded)
    if scored > conceded:
        row.won = row.won + 1
    elif scored == conceded:
        row.drawn = row.drawn + 1
    else:
        row.lost = row.lost + 1
    return row


def ordering(row: Standing) -> tuple[int, int, int, str]:
    return (-row.points, row.goals_against - row.goals_for, -row.goals_for, row.identifier)


def contribution(fixture: Fixture, opponent: str, scored: int, conceded: int) -> Json:
    outcome: str = "draw"
    if scored > conceded:
        outcome = "win"
    elif scored < conceded:
        outcome = "loss"
    return {
        "fixture": fixture.identifier,
        "opponent": opponent,
        "goals_for": scored,
        "goals_against": conceded,
        "points": result_points(scored, conceded),
        "outcome": outcome,
    }


def calculate(tournament: Tournament) -> Json:
    table: dict[str, Standing] = {}
    details: dict[str, list[Json]] = {}
    for name in tournament.teams:
        table[name] = Standing(name, tournament.teams[name].name, 0, 0, 0, 0, 0, 0, 0)
        details[name] = []
    played: int = 0
    draws: int = 0
    for fixture in tournament.fixtures:
        if fixture.played:
            played = played + 1
            if fixture.home_score == fixture.away_score:
                draws = draws + 1
            table[fixture.home] = add_result(table[fixture.home], fixture.home_score, fixture.away_score)
            table[fixture.away] = add_result(table[fixture.away], fixture.away_score, fixture.home_score)
            details[fixture.home].append(contribution(fixture, fixture.away, fixture.home_score, fixture.away_score))
            details[fixture.away].append(contribution(fixture, fixture.home, fixture.away_score, fixture.home_score))
    rows: list[Standing] = []
    for name in table:
        rows.append(table[name])
    rows = sorted(rows, key=ordering)
    standings: list[Json] = []
    leaders: list[str] = []
    previous_points: int = -1
    previous_difference: int = 0
    previous_goals: int = 0
    rank: int = 0
    for index in range(len(rows)):
        row: Standing = rows[index]
        difference: int = row.goals_for - row.goals_against
        if row.points != previous_points or difference != previous_difference or row.goals_for != previous_goals:
            rank = index + 1
        if rank == 1:
            leaders.append(row.identifier)
        standings.append(
            {
                "id": row.identifier,
                "name": row.name,
                "rank": rank,
                "played": row.played,
                "won": row.won,
                "drawn": row.drawn,
                "lost": row.lost,
                "goals_for": row.goals_for,
                "goals_against": row.goals_against,
                "difference": difference,
                "points": row.points,
                "contributions": details[row.identifier],
            }
        )
        previous_points = row.points
        previous_difference = difference
        previous_goals = row.goals_for
    count: int = len(tournament.teams)
    possible: int = count * (count - 1) // 2
    return {
        "title": tournament.title,
        "teams": count,
        "possible_fixtures": possible,
        "scheduled": len(tournament.fixtures),
        "played": played,
        "unplayed": len(tournament.fixtures) - played,
        "unscheduled": possible - len(tournament.fixtures),
        "draws": draws,
        "leaders": leaders,
        "standings": standings,
    }
