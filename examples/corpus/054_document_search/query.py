"""Nested AND/OR expressions combine posting sets; distinct query terms contribute to ranking once."""

# ruff: noqa: C414 - typed list conversion is explicit in this subset

from index import Index
from lexicon import tokens

from py2rust.stdlib import Json, json_array, json_keys, json_kind, json_string


def evaluate(index: Index, expression: Json, depth: int) -> tuple[set[str], set[str], int]:
    assert depth <= 8, "query nesting exceeds 8"
    matches: set[str] = set()
    terms: set[str] = set()
    nodes: int = 1
    first: bool = True
    if json_kind(expression) == "string":
        text: str = json_string(expression)
        assert len(text.encode()) <= 1024, "query leaf exceeds 1024 bytes"
        terms = set(tokens(text))
        for term in terms:
            posting: dict[str, int] = index.postings.get(term, {})
            found: set[str] = set(list(posting))
            matches = found if first else matches & found
            first = False
    else:
        keys: list[str] = json_keys(expression)
        assert len(keys) == 1 and keys[0] in ["and", "or"], "query needs one and/or field"
        operation: str = keys[0]
        children: list[Json] = json_array(expression[operation])
        assert 1 <= len(children) <= 16, "query branch needs 1..16 children"
        for child in children:
            result: tuple[set[str], set[str], int] = evaluate(index, child, depth + 1)
            terms = terms | result[1]
            nodes = nodes + result[2]
            assert nodes <= 64, "query exceeds 64 nodes"
            if first:
                matches = result[0]
            elif operation == "and":
                matches = matches & result[0]
            else:
                matches = matches | result[0]
            first = False
    assert len(terms) <= 64, "query exceeds 64 distinct terms"
    return (matches, terms, nodes)


def search(index: Index, expression: Json, offset: int, limit: int) -> Json:
    assert 0 <= offset <= 128 and 1 <= limit <= 128, "invalid search pagination"
    selected: tuple[set[str], set[str], int] = evaluate(index, expression, 0)
    ranking: list[tuple[int, str]] = []
    for name in selected[0]:
        score: int = 0
        for term in selected[1]:
            posting: dict[str, int] = index.postings.get(term, {})
            score = score + posting.get(name, 0)
        ranking.append((-score, name))
    ranking.sort()
    hits: list[Json] = []
    for position in range(offset, min(len(ranking), offset + limit)):
        row: tuple[int, str] = ranking[position]
        name: str = row[1]
        matched: list[str] = []
        for term in sorted(list(selected[1])):
            posting: dict[str, int] = index.postings.get(term, {})
            if name in posting:
                matched.append(term)
        value: Json = index.records[name]
        hits.append(
            {
                "id": name,
                "title": value["title"],
                "preview": json_string(value["text"])[:160],
                "score": -row[0],
                "terms": matched,
            }
        )
    return {
        "hits": hits,
        "count": len(ranking),
        "more": offset + limit < len(ranking),
        "terms": sorted(list(selected[1])),
    }
