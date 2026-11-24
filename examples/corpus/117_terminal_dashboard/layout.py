"""Cell-bounded task rows, intact Unicode graphemes and compact narrow-window layouts."""

from model import empty, text

from py2rust.stdlib import Json, json_array, json_int, json_is_null, terminal_cells


def repeat(character: str, count: int) -> str:
    result: str = ""
    for index in range(count):
        result = result + character
    return result


def fit(value: str, width: int) -> str:
    cells: list[tuple[str, int]] = terminal_cells(value)
    total: int = 0
    for cell in cells:
        total = total + cell[1]
    budget: int = width if total <= width else max(0, width - 1)
    result: str = ""
    used: int = 0
    for cell in cells:
        if used + cell[1] > budget:
            break
        result = result + cell[0]
        used = used + cell[1]
    if total > width > 0:
        result = result + "~"
        used = used + 1
    return result + repeat(" ", width - used)


def progress(task: Json) -> int:
    if text(task["state"]) == "done":
        return 100
    total: int = json_int(task["total"])
    return -1 if total == 0 else json_int(task["done"]) * 100 // total


def row(task: Json, width: int) -> str:
    state: str = text(task["state"])
    symbol: str = {"queued": ".", "running": ">", "done": "+", "failed": "!"}[state]
    percent: int = progress(task)
    shown: str = " --%" if percent < 0 else fit(str(percent) + "%", 4)
    if width == 1:
        return symbol
    if width < 24:
        return fit(symbol + " " + text(task["label"]), width)
    if width < 50:
        return symbol + " " + shown + " " + fit(text(task["label"]), width - 7)
    bar_size: int = min(20, width // 6)
    filled: int = 0 if percent < 0 else percent * bar_size // 100
    bar: str = repeat("#", filled) + repeat("?" if percent < 0 else "-", bar_size - filled)
    return (
        fit(text(task["id"]), 8)
        + " "
        + fit(state, 7)
        + " "
        + shown
        + " ["
        + bar
        + "] "
        + fit(text(task["label"]), width - bar_size - 25)
    )


def frame(value: Json, width: int, height: int, index: int, count: int, status: str) -> list[str]:
    source: Json = empty() if json_is_null(value) else value
    tasks: list[Json] = json_array(source["tasks"])
    counts: dict[str, int] = {"queued": 0, "running": 0, "done": 0, "failed": 0}
    for task in tasks:
        name: str = text(task["state"])
        counts[name] = counts[name] + 1
    lines: list[str] = [fit(text(source["title"]), width)]
    if height == 1:
        return lines
    summary: str = (
        str(len(tasks)) + " tasks | " + str(counts["running"]) + " running | " + str(counts["done"]) + " done"
    )
    summary = summary + " | " + str(counts["failed"]) + " failed"
    lines.append(fit(summary, width))
    if height == 2:
        return lines
    if width >= 50 and height >= 5:
        lines.append(fit("ID       STATE   DONE  PROGRESS / TASK", width))
    visible: int = min(len(tasks), max(0, height - len(lines) - 1))
    for position in range(visible):
        lines.append(row(tasks[position], width))
    footer: str = str(len(tasks) - visible) + " hidden | frame " + str(index) + "/" + str(count) + " | " + status
    lines.append(fit(footer, width))
    return lines
