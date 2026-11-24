"""Block parsing and collision-free heading IDs for a deliberately defined Markdown subset."""

# ruff: noqa: PIE810 - supported string prefix checks take one string

from dataclasses import dataclass

from inline import Inline, escape, render

from py2rust.stdlib import Json, unicode_normalize


@dataclass
class Page:
    html: str
    headings: list[Json]
    links: list[str]


def heading_level(line: str) -> int:
    level: int = 0
    while level < len(line) and line[level] == "#":
        level = level + 1
    return level if 1 <= level <= 6 and line[level : level + 1] == " " else 0


def slug(text: str) -> str:
    base: str = ""
    separator: bool = False
    for character in unicode_normalize("NFKC", text).casefold():
        if character in "abcdefghijklmnopqrstuvwxyz0123456789" or character >= "\x80":
            if separator and base != "":
                base = base + "-"
            base = base + character
            separator = False
        else:
            separator = True
        if len(base) >= 64:
            break
    return base[:64] if base != "" else "section"


def compile_page(source: str, page: str) -> Page:
    text: str = source.replace("\r\n", "\n")
    for character in text:
        assert (character >= " " or character in "\n\t") and character != "\x7f", "source control character"
    lines: list[str] = text.split("\n")
    assert len(lines) <= 4096, "page exceeds 4096 source lines"
    html: str = ""
    headings: list[Json] = []
    links: list[str] = []
    used: set[str] = set()
    index: int = 0
    while index < len(lines):
        line: str = lines[index]
        assert len(line.encode()) <= 8192, "source line exceeds 8192 bytes"
        if line.strip() == "":
            index = index + 1
            continue
        if line.startswith("```"):
            language: str = line[3:]
            assert len(language) <= 32, "code language exceeds 32 characters"
            for character in language:
                assert (
                    character in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-"
                ), "invalid code language"
            index = index + 1
            code: list[str] = []
            while index < len(lines) and lines[index] != "```":
                assert len(lines[index].encode()) <= 8192, "source line exceeds 8192 bytes"
                code.append(lines[index])
                index = index + 1
            assert index < len(lines), "unclosed code fence"
            attribute: str = ' class="language-' + language + '"' if language != "" else ""
            html = html + "<pre><code" + attribute + ">" + escape("\n".join(code)) + "</code></pre>\n"
            index = index + 1
            continue
        level: int = heading_level(line)
        tag: str = "p"
        value: str = line
        if level > 0:
            value = line[level + 1 :]
            tag = "h" + str(level)
        elif line.startswith("- "):
            tag = "li"
            value = line[2:]
            if index == 0 or not lines[index - 1].startswith("- "):
                html = html + "<ul>\n"
        else:
            while index + 1 < len(lines):
                following: str = lines[index + 1]
                if (
                    following.strip() == ""
                    or heading_level(following) > 0
                    or following.startswith("- ")
                    or following.startswith("```")
                ):
                    break
                assert len(following.encode()) <= 8192, "source line exceeds 8192 bytes"
                value = value + " " + following
                index = index + 1
        rendered: Inline = render(value, page)
        links = links + rendered.links
        attribute: str = ""
        if level > 0:
            assert len(headings) < 256, "page exceeds 256 headings"
            base: str = slug(rendered.plain)
            anchor: str = base
            number: int = 2
            while anchor in used:
                anchor = base + "-" + str(number)
                number = number + 1
            used.add(anchor)
            headings.append({"level": level, "text": rendered.plain, "id": anchor})
            attribute = ' id="' + escape(anchor) + '"'
        html = html + "<" + tag + attribute + ">" + rendered.html + "</" + tag + ">\n"
        if tag == "li" and (index + 1 == len(lines) or not lines[index + 1].startswith("- ")):
            html = html + "</ul>\n"
        index = index + 1
    return Page(html, headings, links)
