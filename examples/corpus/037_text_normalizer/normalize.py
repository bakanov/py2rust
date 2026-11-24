"""Pure Unicode normalization rules, independent of filesystem operations."""

from py2rust.stdlib import Json, json_bool, json_get, json_string


def trim_horizontal(line: str) -> str:
    result: str = line
    while len(result) > 0:
        if result[-1] != " " and result[-1] != "\t":
            return result
        result = result[0:-1]
    return result


def normalized(text: str, options: Json) -> str:
    unified: str = text.replace("\r\n", "\n").replace("\r", "\n")
    lines: list[str] = []
    trim: bool = json_bool(json_get(options, "trim_trailing", True))
    for line in unified.split("\n"):
        if trim:
            line = trim_horizontal(line)
        lines.append(line)
    result: str = "\n".join(lines)
    ending: str = json_string(json_get(options, "final_newline", "preserve"))
    if ending == "remove":
        while result.endswith("\n"):
            result = result[0:-1]
    if ending == "ensure" and len(result) > 0 and not result.endswith("\n"):
        result = result + "\n"
    if json_string(json_get(options, "newline", "lf")) == "crlf":
        result = result.replace("\n", "\r\n")
    return result


def line_count(text: str) -> int:
    if text == "":
        return 0
    unified: str = text.replace("\r\n", "\n").replace("\r", "\n")
    count: int = len(unified.split("\n"))
    if unified.endswith("\n"):
        count = count - 1
    return count


def first_difference(before: str, after: str) -> Json:
    old_lines: list[str] = before.split("\n")
    new_lines: list[str] = after.split("\n")
    count: int = max(len(old_lines), len(new_lines))
    for index in range(count):
        old: str = ""
        new: str = ""
        if index < len(old_lines):
            old = old_lines[index]
        if index < len(new_lines):
            new = new_lines[index]
        if old != new:
            return {"line": index + 1, "before": old[0:120], "after": new[0:120]}
    return {"line": count, "before": "", "after": "", "reason": "final newline changed"}


def describe(name: str, before: str, after: str) -> Json:
    result: Json = {
        "file": name,
        "changed": before != after,
        "bytes_before": len(before.encode()),
        "bytes_after": len(after.encode()),
        "lines_before": line_count(before),
        "lines_after": line_count(after),
    }
    if before != after:
        result["preview"] = first_difference(before, after)
    return result
