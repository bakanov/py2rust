"""Process a complete round and choose deterministic exploration missions."""

from planning import Plan, Unit, explore_plans, ordered_units
from queue import PhaseEvent, TurnQueue, run_round


def main() -> None:
    queue: TurnQueue = TurnQueue()
    for event in [
        PhaseEvent(0, "human", 3),
        PhaseEvent(1, "ai", 3),
        PhaseEvent(2, "ai", 3),
        PhaseEvent(9, "barbarian", 3),
    ]:
        queue.append(event)
    for message in run_round(queue):
        print(message)
    print("Queue cursor/processed/pending: " + str(queue.cursor) + "/" + str(queue.processed) + "/" + str(len(queue.pending)))
    queue.compact()
    print("After compaction: " + str(queue.cursor) + "/" + str(len(queue.pending)))
    units: list[Unit] = [Unit(4, 4, 2, True), Unit(2, 0, 0, True), Unit(7, 2, 2, False)]
    for unit in ordered_units(units, (2, 2)):
        print("Activation: " + str(unit.identifier))
    plans: list[Plan] = explore_plans(units, [(4, 4), (1, 3), (3, 1)])
    for plan in plans:
        assert plan.destination is not None
        print(
            "Plan " + str(plan.unit_id) + " -> " + str(plan.destination[0]) + "," + str(plan.destination[1])
            + " score=" + str(plan.score)
        )
    idle: list[Plan] = explore_plans([Unit(8, 0, 0, False)], [(1, 1)])
    print("Manual unit plans: " + str(len(idle)))
    return


if __name__ == "__main__":
    main()
