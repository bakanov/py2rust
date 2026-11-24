"""Budgeted iterative backtracking with valid incumbents and explicit optimality status."""

from model import Problem, Shift, Worker

from py2rust.stdlib import Json


def static_reasons(worker: Worker, shift: Shift) -> list[str]:
    reasons: list[str] = []
    if shift.skill not in worker.skills:
        reasons.append("skill")
    available: bool = False
    for window in worker.availability:
        if window[0] <= shift.start and shift.end <= window[1]:
            available = True
    if not available:
        reasons.append("availability")
    if worker.max_shifts == 0:
        reasons.append("max_shifts")
    if shift.end - shift.start > worker.max_minutes:
        reasons.append("max_minutes")
    return reasons


def reasons(problem: Problem, slots: list[int], assigned: list[int], candidate: int, target: int) -> list[str]:
    worker: Worker = problem.workers[candidate]
    shift: Shift = problem.shifts[target]
    result: list[str] = static_reasons(worker, shift)
    minutes: int = shift.end - shift.start
    count: int = 1
    conflict: bool = False
    for position in range(len(assigned)):
        if assigned[position] == candidate:
            other: Shift = problem.shifts[slots[position]]
            minutes = minutes + other.end - other.start
            count = count + 1
            if not (other.end + problem.rest <= shift.start or shift.end + problem.rest <= other.start):
                conflict = True
    if conflict:
        result.append("overlap_or_rest")
    if count > worker.max_shifts and "max_shifts" not in result:
        result.append("max_shifts")
    if minutes > worker.max_minutes and "max_minutes" not in result:
        result.append("max_minutes")
    return result


def schedule(problem: Problem, slots: list[int], assigned: list[int]) -> list[Json]:
    result: list[Json] = []
    for index in range(len(problem.shifts)):
        crew: list[str] = []
        for position in range(len(assigned)):
            if slots[position] == index and assigned[position] >= 0:
                crew.append(problem.workers[assigned[position]].name)
        result.append({"shift": problem.shifts[index].name, "workers": sorted(crew)})
    return result


def signature(problem: Problem, slots: list[int], assigned: list[int]) -> list[str]:
    result: list[str] = []
    for index in range(len(problem.shifts)):
        crew: list[str] = []
        for position in range(len(assigned)):
            if slots[position] == index:
                crew.append(problem.workers[assigned[position]].name)
        result.extend(sorted(crew))
    return result


def solve(problem: Problem) -> Json:
    eligible: list[list[int]] = []
    ranks: list[tuple[int, int, str, int]] = []
    shortages: list[Json] = []
    for index in range(len(problem.shifts)):
        shift: Shift = problem.shifts[index]
        candidates: list[int] = []
        for candidate in range(len(problem.workers)):
            if len(static_reasons(problem.workers[candidate], shift)) == 0:
                candidates.append(candidate)
        eligible.append(candidates)
        ranks.append((len(candidates), shift.start, shift.name, index))
        if len(candidates) < shift.required:
            shortages.append({"shift": shift.name, "required": shift.required, "eligible": len(candidates)})
    slots: list[int] = []
    for rank in sorted(ranks):
        for position in range(problem.shifts[rank[3]].required):
            slots.append(rank[3])
    assigned: list[int] = []
    cursors: list[int] = []
    counts: list[int] = []
    for position in range(len(slots)):
        assigned.append(-1)
        cursors.append(0)
    for worker in problem.workers:
        counts.append(0)
    depth: int = 0
    attempts: int = 0
    score: int = 0
    best_score: int = 0
    found: bool = False
    complete: bool = True
    best: list[int] = []
    best_key: list[str] = []
    deepest: list[int] = []
    if len(shortages) > 0:
        depth = -1
    while depth >= 0:
        if depth == len(slots):
            key: list[str] = signature(problem, slots, assigned)
            if not found or score < best_score or (score == best_score and key < best_key):
                best = assigned.copy()
                best_key = key
                best_score = score
                found = True
            depth = depth - 1
            continue
        target: int = slots[depth]
        shift: Shift = problem.shifts[target]
        if assigned[depth] >= 0:
            old: int = assigned[depth]
            counts[old] = counts[old] - 1
            score = (
                score - problem.workers[old].preferences.get(shift.name, 0) - problem.balance * (2 * counts[old] + 1)
            )
            assigned[depth] = -1
        candidates: list[int] = eligible[target]
        if cursors[depth] == len(candidates):
            cursors[depth] = 0
            depth = depth - 1
            continue
        if attempts == problem.budget:
            complete = False
            break
        candidate: int = candidates[cursors[depth]]
        cursors[depth] = cursors[depth] + 1
        attempts = attempts + 1
        if depth > 0 and slots[depth - 1] == target and candidate <= assigned[depth - 1]:
            continue
        if len(reasons(problem, slots, assigned, candidate, target)) > 0:
            continue
        added: int = problem.workers[candidate].preferences.get(shift.name, 0) + problem.balance * (
            2 * counts[candidate] + 1
        )
        if found and score + added > best_score:
            continue
        assigned[depth] = candidate
        counts[candidate] = counts[candidate] + 1
        score = score + added
        depth = depth + 1
        if depth > len(deepest):
            deepest = assigned[:depth]
    status: str = (
        "optimal" if found and complete else "feasible" if found else "unsatisfiable" if complete else "search_limit"
    )
    assignments: list[Json] = []
    result_score: Json = None
    if found:
        assignments = schedule(problem, slots, best)
        result_score = best_score
    frontier: Json = None
    if not found and len(deepest) < len(slots):
        target: int = slots[len(deepest)]
        rejected: list[Json] = []
        for candidate in range(len(problem.workers)):
            rejected.append(
                {
                    "worker": problem.workers[candidate].name,
                    "reasons": reasons(problem, slots, deepest, candidate, target),
                }
            )
        frontier = {"next_shift": problem.shifts[target].name, "candidates": rejected}
    return {
        "status": status,
        "complete_search": complete,
        "attempts": attempts,
        "budget": problem.budget,
        "score": result_score,
        "schedule": assignments,
        "shortages": shortages,
        "diagnostic_prefix": schedule(problem, slots, deepest) if not found else [],
        "frontier": frontier,
    }
