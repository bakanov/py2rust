"""A finite event calendar with completion, expiry, dispatch, then arrival ordering."""

# ruff: noqa: I001 - compact imports within the executable-project line budget
import heapq
from dataclasses import dataclass
from py2rust.stdlib import Json, json_int, json_string


@dataclass
class State:
    jobs: list[Json]
    trace: list[Json]
    counts: dict[str, int]
    now: int
    queue_area: int
    busy_area: int
    peak_queue: int


def transition(state: State, index: int, status: str, worker: int) -> State:
    jobs: list[Json] = state.jobs
    counts: dict[str, int] = state.counts
    trace: list[Json] = state.trace
    job: Json = jobs[index]
    previous: str = json_string(job["status"])
    counts[previous] = counts[previous] - 1
    counts[status] = counts[status] + 1
    job["status"] = status
    if status == "running":
        job["started"] = state.now
        job["worker"] = worker
    elif status != "queued":
        job["finished"] = state.now
    jobs[index] = job
    state.jobs = jobs
    state.counts = counts
    terminal: int = len(state.jobs) - state.counts["pending"] - state.counts["queued"] - state.counts["running"]
    trace.append(
        {
            "sequence": len(state.trace) + 1,
            "tick": state.now,
            "job": job["id"],
            "status": status,
            "worker": job["worker"],
            "pending": state.counts["pending"],
            "queued": state.counts["queued"],
            "running": state.counts["running"],
            "terminal": terminal,
        }
    )
    state.trace = trace
    state.peak_queue = max(state.peak_queue, state.counts["queued"])
    return state


def free_worker(owners: list[int]) -> int:
    for worker in range(len(owners)):
        if owners[worker] == -1:
            return worker
    return -1


def simulate(jobs: list[Json], workers: int, capacity: int) -> State:
    counts: dict[str, int] = {}
    owners: list[int] = []
    queue: list[int] = []
    for status in ["pending", "queued", "running", "on_time", "late", "expired", "rejected"]:
        counts[status] = 0
    counts["pending"] = len(jobs)
    for worker in range(workers):
        owners.append(-1)
    calendar: list[tuple[int, int, int]] = []
    for index in range(len(jobs)):
        job: Json = jobs[index]
        job["status"] = "pending"
        job["started"] = -1
        job["finished"] = -1
        job["worker"] = -1
        jobs[index] = job
        heapq.heappush(calendar, (json_int(job["arrival"]), 3, index))
        heapq.heappush(calendar, (json_int(job["deadline"]), 1, index))
    state: State = State(jobs, [], counts, 0, 0, 0, 0)
    while state.counts["pending"] + state.counts["queued"] + state.counts["running"] > 0:
        now: int = calendar[0][0]
        state.queue_area = state.queue_area + (now - state.now) * state.counts["queued"]
        state.busy_area = state.busy_area + (now - state.now) * state.counts["running"]
        state.now = now
        # A synthetic dispatch event runs after every completion/expiry at this tick.
        heapq.heappush(calendar, (now, 2, 0))
        while len(calendar) > 0 and calendar[0][0] == now:
            event: tuple[int, int, int] = heapq.heappop(calendar)
            phase: int = event[1]
            index: int = event[2]
            if phase == 2:
                worker: int = free_worker(owners)
                while worker >= 0 and len(queue) > 0:
                    index = queue.pop(0)
                    owners[worker] = index
                    state = transition(state, index, "running", worker)
                    heapq.heappush(calendar, (now + json_int(state.jobs[index]["service"]), 0, index))
                    worker = free_worker(owners)
            else:
                job: Json = state.jobs[index]
                status: str = json_string(job["status"])
                if phase == 0:
                    assert status == "running", "unexpected completion"
                    owners[json_int(job["worker"])] = -1
                    outcome: str = "on_time" if now <= json_int(job["deadline"]) else "late"
                    state = transition(state, index, outcome, -1)
                elif phase == 1 and status == "queued":
                    for position in range(len(queue)):
                        if queue[position] == index:
                            queue.pop(position)
                            break
                    state = transition(state, index, "expired", -1)
                elif phase == 3:
                    worker: int = free_worker(owners)
                    if now == json_int(job["deadline"]):
                        state = transition(state, index, "expired", -1)
                    elif worker >= 0:
                        owners[worker] = index
                        state = transition(state, index, "running", worker)
                        heapq.heappush(calendar, (now + json_int(job["service"]), 0, index))
                    elif len(queue) < capacity:
                        queue.append(index)
                        state = transition(state, index, "queued", -1)
                    else:
                        state = transition(state, index, "rejected", -1)
        assert len(queue) == state.counts["queued"] <= capacity, "queue conservation failed"
        assert 0 <= state.counts["running"] <= workers, "worker capacity exceeded"
    return state
