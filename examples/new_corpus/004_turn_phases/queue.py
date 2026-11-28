"""A phase queue with a cursor instead of quadratic removal from index zero."""

from dataclasses import dataclass, field


@dataclass
class PhaseEvent:
    owner: int
    name: str
    turn: int


@dataclass
class TurnQueue:
    pending: list[PhaseEvent] = field(default_factory=list)
    cursor: int = 0
    processed: int = 0

    def append(self, event: PhaseEvent) -> None:
        self.pending.append(event)
        return

    def next_event(self) -> PhaseEvent | None:
        if self.cursor >= len(self.pending):
            return None
        event: PhaseEvent = self.pending[self.cursor]
        self.cursor += 1
        self.processed += 1
        return event

    def compact(self) -> None:
        if self.cursor > 0:
            self.pending = self.pending[self.cursor :]
            self.cursor = 0
        return


def run_round(queue: TurnQueue) -> list[str]:
    messages: list[str] = []
    while True:
        event: PhaseEvent | None = queue.next_event()
        if event is None:
            break
        messages.append(str(event.turn) + ":" + str(event.owner) + ":" + event.name)
        if event.name == "human":
            queue.append(PhaseEvent(event.owner, "economic", event.turn))
        if event.name == "barbarian":
            queue.append(PhaseEvent(event.owner, "cleanup", event.turn))
    return messages
