"""A phase queue with a cursor instead of quadratic removal from index zero."""

from __future__ import annotations

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

    def append(self, event: PhaseEvent) -> TurnQueue:
        self.pending.append(event)
        return self

    def next_event(self) -> tuple[TurnQueue, PhaseEvent | None]:
        if self.cursor >= len(self.pending):
            return self, None
        event: PhaseEvent = self.pending[self.cursor]
        self.cursor += 1
        self.processed += 1
        return self, event

    def compact(self) -> TurnQueue:
        if self.cursor > 0:
            self.pending = self.pending[self.cursor :]
            self.cursor = 0
        return self


def run_round(queue: TurnQueue) -> tuple[TurnQueue, list[str]]:
    messages: list[str] = []
    steps: int = 0
    while steps < 100:
        steps += 1
        event: PhaseEvent | None
        updated: TurnQueue
        updated, event = queue.next_event()
        queue = updated
        if event is None:
            break
        messages.append(str(event.turn) + ":" + str(event.owner) + ":" + event.name)
        if event.name == "human":
            queue = queue.append(PhaseEvent(event.owner, "economic", event.turn))
        if event.name == "barbarian":
            queue = queue.append(PhaseEvent(event.owner, "cleanup", event.turn))
    assert queue.cursor >= len(queue.pending), "turn processing exceeded its phase budget"
    return queue, messages
