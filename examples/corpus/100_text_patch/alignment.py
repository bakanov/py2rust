"""Bounded LCS alignment with deletion-first ties and merged context intervals."""

from dataclasses import dataclass

from text_model import identity, lines

from py2rust.stdlib import Json


@dataclass
class Edit:
    kind: str
    text: str


def align(before: list[str], after: list[str]) -> list[Edit]:
    width: int = len(after) + 1
    cells: int = (len(before) + 1) * width
    assert cells <= 1050625, "alignment cell budget exceeded"
    table: list[int] = []
    for cell in range(cells):
        table.append(0)
    for left in range(len(before) - 1, -1, -1):
        for right in range(len(after) - 1, -1, -1):
            here: int = left * width + right
            if before[left] == after[right]:
                table[here] = table[here + width + 1] + 1
            else:
                table[here] = max(table[here + width], table[here + 1])
    edits: list[Edit] = []
    left: int = 0
    right: int = 0
    while left < len(before) or right < len(after):
        if left < len(before) and right < len(after) and before[left] == after[right]:
            edits.append(Edit(" ", before[left]))
            left = left + 1
            right = right + 1
        elif left < len(before) and (
            right == len(after) or table[(left + 1) * width + right] >= table[left * width + right + 1]
        ):
            edits.append(Edit("-", before[left]))
            left = left + 1
        else:
            edits.append(Edit("+", after[right]))
            right = right + 1
    return edits


def hunks(edits: list[Edit], context: int) -> list[Json]:
    starts: list[int] = []
    ends: list[int] = []
    old: list[int] = [0]
    new: list[int] = [0]
    for index in range(len(edits)):
        kind: str = edits[index].kind
        old.append(old[-1] + (0 if kind == "+" else 1))
        new.append(new[-1] + (0 if kind == "-" else 1))
        if kind != " ":
            start: int = max(0, index - context)
            end: int = min(len(edits), index + context + 1)
            if len(ends) > 0 and start <= ends[-1]:
                ends[-1] = end
            else:
                starts.append(start)
                ends.append(end)
    result: list[Json] = []
    for index in range(len(starts)):
        start: int = starts[index]
        end: int = ends[index]
        operations: list[Json] = []
        for position in range(start, end):
            operations.append({"op": edits[position].kind, "text": edits[position].text})
        result.append(
            {
                "old_start": old[start],
                "old_count": old[end] - old[start],
                "new_start": new[start],
                "new_count": new[end] - new[start],
                "ops": operations,
            }
        )
    return result


def create(before: bytes, after: bytes, context: int) -> Json:
    assert 0 <= context <= 16, "context outside permitted range"
    edits: list[Edit] = align(lines(before), lines(after))
    return {
        "version": 1,
        "format": "line-lcs",
        "context": context,
        "before": identity(before),
        "after": identity(after),
        "hunks": hunks(edits, context),
    }
