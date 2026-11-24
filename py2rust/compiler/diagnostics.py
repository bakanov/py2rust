"""Versioned, scoped optimization explanations and deterministic cost gates."""

from __future__ import annotations

import ast
from dataclasses import asdict, dataclass
from fnmatch import fnmatchcase

from .effects import summarize_functions


@dataclass(frozen=True)
class LoweringDecision:
    function: str
    line: int
    column: int
    operation: str
    mode: str
    reason: str


def build_report(
    functions: list[ast.FunctionDef],
    parameters: dict,
    decisions: list[LoweringDecision],
    *,
    summaries: dict | None = None,
) -> dict:
    if summaries is None:
        summaries = summarize_functions(functions)
    rows = []
    for name, summary in sorted(summaries.items()):
        effects = asdict(summary.effects)
        effects["costs"] = sorted(summary.effects.costs)
        rows.append(
            {
                "symbol": name,
                "file": summary.filename,
                "line": summary.line,
                "effects": effects,
                "parameters_may_write": sorted(summary.parameters_may_write),
                "callees": sorted(summary.callees),
                "unknown_calls": sorted(summary.unknown_calls),
                "parameters": [asdict(value) for value in parameters.get(name, {}).values()],
                "decisions": [asdict(value) for value in dict.fromkeys(decisions) if value.function == name],
            }
        )
    return {
        "schema_version": 1,
        "coverage": {
            "scope": "declared Python functions; main-guard statements and native bodies are excluded",
            "effects": "conservative transitive summaries; unknown is not pure",
            "costs": "possible symbolic costs, not execution counts, time bounds, or an exhaustive allocation inventory",
            "decisions": "actual parameter ABI, direct-local assignment/return ownership, selected builders, declared views, and direct-local iteration lowering",
            "strict_checks": ["unknown-effects", "snapshot-iteration", "owned-boundary-copy"],
        },
        "functions": rows,
    }


def select_and_check(report: dict, symbols: dict, patterns: list[str], denied: list[str]) -> dict:
    """Never silently pass an unmatched function selector or unsupported gate."""
    supported = set(report["coverage"]["strict_checks"])
    if set(denied) - supported:
        raise ValueError("unknown cost check: " + ", ".join(sorted(set(denied) - supported)))
    selected, matched = [], set()
    for row in report["functions"]:
        source = symbols.get(row["symbol"], {})
        selector = f"{source.get('file', row['file'])}:{source.get('name', row['symbol'])}"
        matches = {
            pattern for pattern in patterns if fnmatchcase(selector, pattern) or fnmatchcase(row["symbol"], pattern)
        }
        if matches:
            matched.update(matches)
            selected.append(dict(row, selector=selector))
    if set(patterns) - matched:
        raise ValueError("no functions matched: " + ", ".join(sorted(set(patterns) - matched)))
    violations = []
    for row in selected:
        if "unknown-effects" in denied and row["effects"]["unknown"]:
            violations.append(
                {
                    "function": row["selector"],
                    "line": row["line"],
                    "check": "unknown-effects",
                    "reason": "unreviewed direct or transitive call/cleanup effects",
                }
            )
        if {"snapshot-iteration", "owned-boundary-copy"} & set(denied):
            all_rows = {item["symbol"]: item for item in report["functions"]}
            pending, visited = [row["symbol"]], set()
            while pending:
                name = pending.pop()
                if name in visited or name not in all_rows:
                    continue
                visited.add(name)
                origin = all_rows[name]
                pending.extend(sorted(origin["callees"], reverse=True))
                source = symbols.get(name, {})
                origin_selector = f"{source.get('file', origin['file'])}:{source.get('name', name)}"
                for decision in origin["decisions"]:
                    check = None
                    if (
                        "snapshot-iteration" in denied
                        and decision["operation"] == "iteration"
                        and decision["mode"] == "snapshot"
                    ):
                        check = "snapshot-iteration"
                    elif (
                        "owned-boundary-copy" in denied
                        and decision["operation"] == "owned_boundary"
                        and decision["mode"] in {"copy", "materialize"}
                    ):
                        check = "owned-boundary-copy"
                    if check is not None:
                        violations.append(
                            {
                                "function": row["selector"],
                                "origin": origin_selector,
                                "line": decision["line"],
                                "check": check,
                                "reason": decision["reason"],
                            }
                        )
    return dict(report, functions=selected, denied=sorted(set(denied)), violations=violations)
