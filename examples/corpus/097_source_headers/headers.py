"""Locate leading headers and propose one exact UTF-8 byte splice per file."""

# ruff: noqa: I001, PIE810 - compact imports and single-string prefix operands
from py2rust.stdlib import (
    Json, base64_encode, json_array, json_int, json_string, regex_capture,
)


def issue(kind: str, line: int) -> Json:
    return {"kind": kind, "line": line}


def analyze(data: bytes, style: str, policy: Json) -> Json:
    base: int = 3 if data.startswith(b"\xef\xbb\xbf") else 0
    text: str = data[base:].decode()
    assert "\x00" not in text and "\r" not in text.replace("\r\n", ""), "expected UTF-8 LF or CRLF text"
    pieces: list[str] = text.split("\n")
    lines: list[str] = []
    offsets: list[int] = [base]
    newline: str = "\n"
    for index in range(len(pieces)):
        line: str = pieces[index]
        if index + 1 < len(pieces):
            line = line + "\n"
        if line != "":
            lines.append(line)
            offsets.append(offsets[-1] + len(line.encode()))
    assert len(lines) <= 4096, "physical line limit exceeded"
    for line in lines:
        if line.endswith("\n"):
            newline = "\r\n" if line.endswith("\r\n") else "\n"
            break
    prefix: int = 1 if len(lines) > 0 and lines[0].startswith("#!") else 0
    if style == "hash":
        for index in range(min(2, len(lines))):
            cookie: Json = regex_capture(r"^[ \t]*#.*?coding[:=][ \t]*([-_.a-zA-Z0-9]+)", lines[index], False)
            if cookie is not None and (index == 0 or lines[0].strip() == "" or lines[0].lstrip().startswith("#")):
                encoding: str = json_string(json_array(cookie["groups"])[1]).lower()
                assert encoding in ["utf-8", "utf8"], "only UTF-8 encoding declarations are supported"
                prefix = max(prefix, index + 1)
    marker: str = "#" if style == "hash" else "//"
    findings: list[Json] = []
    copyright_lines: list[int] = []
    license_lines: list[int] = []
    for index in range(prefix, len(lines)):
        stripped: str = lines[index].strip()
        if stripped != "" and not stripped.startswith(marker):
            break
        content: str = stripped[len(marker) :].lstrip() if stripped.startswith(marker) else ""
        if content.lower().startswith("copyright"):
            copyright_lines.append(index)
        elif content.lower().startswith("spdx-license-identifier"):
            license_lines.append(index)
    for index in range(prefix):
        content: str = lines[index].lstrip()[len(marker) :].lstrip().lower()
        if content.startswith("copyright") or content.startswith("spdx-license-identifier"):
            findings.append(issue("header_in_preamble", index + 1))
    if len(findings) > 0:
        return {"issues": findings, "edit": None, "manual": True}
    owners: list[str] = []
    licenses: list[str] = []
    for value in json_array(policy["owners"]):
        owners.append(json_string(value))
    for value in json_array(policy["licenses"]):
        licenses.append(json_string(value))
    current: int = json_int(policy["year"])
    start: int = current
    owner: str = owners[0]
    license: str = licenses[0]
    if len(copyright_lines) == 0:
        findings.append(issue("missing_copyright", prefix + 1))
    for position in range(len(copyright_lines)):
        index: int = copyright_lines[position]
        if position > 0:
            findings.append(issue("duplicate_copyright", index + 1))
        matched: Json = regex_capture(
            r"^" + marker + r" Copyright \(c\) ([0-9]{4})(-[0-9]{4})? (.+)$", lines[index].rstrip("\r\n"), True
        )
        if matched is None:
            findings.append(issue("copyright_format", index + 1))
            continue
        groups: list[Json] = json_array(matched["groups"])
        first: int = int(json_string(groups[1]))
        last: int = first if groups[2] is None else int(json_string(groups[2])[1:])
        valid_year: bool = 1900 <= first <= last <= current
        if not valid_year:
            findings.append(issue("year_range", index + 1))
        elif last != current:
            findings.append(issue("outdated_year", index + 1))
        candidate: str = json_string(groups[3])
        if candidate not in owners:
            findings.append(issue("owner", index + 1))
        if position == 0:
            start = first if valid_year else current
            owner = candidate if candidate in owners else owners[0]
    if len(license_lines) == 0:
        findings.append(issue("missing_license", prefix + 1))
    for position in range(len(license_lines)):
        index: int = license_lines[position]
        if position > 0:
            findings.append(issue("duplicate_license", index + 1))
        matched: Json = regex_capture(
            r"^" + marker + r" SPDX-License-Identifier: ([A-Za-z0-9][A-Za-z0-9.+-]{0,63})$",
            lines[index].rstrip("\r\n"),
            True,
        )
        if matched is None:
            findings.append(issue("license_format", index + 1))
            continue
        candidate: str = json_string(json_array(matched["groups"])[1])
        if candidate not in licenses:
            findings.append(issue("license", index + 1))
        if position == 0 and candidate in licenses:
            license = candidate
    if len(copyright_lines) > 0 and copyright_lines[0] != prefix:
        findings.append(issue("copyright_position", copyright_lines[0] + 1))
    if len(license_lines) > 0 and license_lines[0] != prefix + 1:
        findings.append(issue("license_position", license_lines[0] + 1))
    if len(findings) == 0:
        return {"issues": findings, "edit": None, "manual": False}
    years: str = str(start) if start == current else str(start) + "-" + str(current)
    replacement: str = marker + " Copyright (c) " + years + " " + owner + newline
    replacement = replacement + marker + " SPDX-License-Identifier: " + license + newline
    if prefix > 0 and not lines[prefix - 1].endswith("\n"):
        replacement = newline + replacement
    end: int = prefix
    for index in copyright_lines + license_lines:
        end = max(end, index + 1)
    for index in range(prefix, end):
        if index not in copyright_lines and index not in license_lines:
            replacement = replacement + lines[index]
    return {
        "issues": findings,
        "manual": False,
        "edit": {
            "start": offsets[prefix],
            "end": offsets[end],
            "removed": base64_encode(data[offsets[prefix] : offsets[end]]),
            "replacement": base64_encode(replacement.encode()),
        },
    }
