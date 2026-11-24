"""Independent warehouse oracle using coordinate sets and full prior-state snapshots for undo."""

from __future__ import annotations

import hashlib
import json
import unicodedata

DELTAS = {"up": (-1, 0), "down": (1, 0), "left": (0, -1), "right": (0, 1)}


def canonical(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode()


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def display(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).split())


def program(grid: list[str], commands: list[str], title: str = "Warehouse demonstration") -> dict:
    return {"version": 1, "title": title, "grid": grid, "commands": commands}


def document() -> dict:
    return program(
        ["########", "#..$...#", "#.@$#..#", "#..$...#", "#......#", "########"],
        [
            "right",
            "up",
            "right",
            "right",
            "down",
            "undo",
            "left",
            "down",
            "left",
            "left",
            "undo",
            "down",
            "right",
            "undo",
            "up",
        ],
    )


def expected(source: dict) -> dict:
    height, width = len(source["grid"]), len(source["grid"][0])
    walls = {(r, c) for r, line in enumerate(source["grid"]) for c, cell in enumerate(line) if cell == "#"}
    boxes = {(r, c) for r, line in enumerate(source["grid"]) for c, cell in enumerate(line) if cell == "$"}
    robot = next((r, c) for r, line in enumerate(source["grid"]) for c, cell in enumerate(line) if cell == "@")
    original_boxes = len(boxes)
    history = []

    def inside(position: tuple[int, int]) -> bool:
        return 0 <= position[0] < height and 0 <= position[1] < width

    def snapshot() -> dict:
        assert inside(robot) and robot not in walls and robot not in boxes and len(boxes) == original_boxes
        assert all(inside(p) and p not in walls for p in boxes)
        rows = [
            "".join(
                "@" if (r, c) == robot else "$" if (r, c) in boxes else "#" if (r, c) in walls else "."
                for c in range(width)
            )
            for r in range(height)
        ]
        return {
            "grid": rows,
            "robot": list(robot),
            "boxes": [list(p) for p in sorted(boxes)],
            "history_depth": len(history),
        }

    initial = snapshot()
    trace = []
    for index, command in enumerate(source["commands"]):
        before = snapshot()
        action, reason = "blocked", ""
        if command == "undo":
            if not history:
                reason = "empty_history"
            else:
                old_robot, old_boxes, _ = history.pop()
                action = "undo_push" if old_boxes != boxes else "undo_move"
                robot, boxes = old_robot, set(old_boxes)
        else:
            dr, dc = DELTAS[command]
            adjacent = (robot[0] + dr, robot[1] + dc)
            beyond = (adjacent[0] + dr, adjacent[1] + dc)
            if not inside(adjacent):
                reason = "boundary"
            elif adjacent in walls:
                reason = "wall"
            elif adjacent in boxes and not inside(beyond):
                reason = "box_boundary"
            elif adjacent in boxes and beyond in walls:
                reason = "box_wall"
            elif adjacent in boxes and beyond in boxes:
                reason = "box_chain"
            else:
                history.append((robot, frozenset(boxes), command))
                assert len(history) <= 1024
                action = "push" if adjacent in boxes else "move"
                if adjacent in boxes:
                    boxes.remove(adjacent)
                    boxes.add(beyond)
                robot = adjacent
        after = snapshot()
        if action == "blocked":
            assert after == before
        trace.append({"index": index, "command": command, "action": action, "reason": reason, "state": after})
    counts = {
        "commands": len(trace),
        "walks": sum(r["action"] == "move" for r in trace),
        "pushes": sum(r["action"] == "push" for r in trace),
        "undos": sum(r["action"].startswith("undo_") for r in trace),
        "blocked": sum(r["action"] == "blocked" for r in trace),
        "history_depth": len(history),
    }
    assert counts["walks"] + counts["pushes"] - counts["undos"] == len(history)
    assert sum(counts[k] for k in ["walks", "pushes", "undos", "blocked"]) == len(trace)
    return {
        "title": source["title"],
        "initial": initial,
        "final": snapshot(),
        "summary": counts,
        "active_commands": [entry[2] for entry in history],
        "trace": trace,
    }
