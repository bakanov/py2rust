"""Balanced inline markup, plain heading text, and checked hyperlink destinations."""

# ruff: noqa: PIE810 - supported string prefix checks take one string

from dataclasses import dataclass

from py2rust.stdlib import url_origin, url_quote


@dataclass
class Inline:
    html: str
    plain: str
    end: int
    links: list[str]


def escape(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )


def destination(target: str, page: str) -> tuple[str, str, str]:
    assert 1 <= len(target.encode()) <= 8192, "invalid link length"
    for character in target:
        assert character > " " and character not in '\x7f\\<>"', "invalid link character"
    if target.startswith("https://") or target.startswith("http://"):
        url_origin(target)
        return (target, "", "")
    parts: list[str] = target.split("#")
    assert len(parts) <= 2, "multiple link fragments"
    owner: str = parts[0] if parts[0] != "" else page
    anchor: str = parts[1] if len(parts) == 2 else ""
    assert len(parts) == 1 or anchor != "", "empty link fragment"
    return (owner + ".html" + ("#" + url_quote(anchor) if anchor != "" else ""), owner, anchor)


def parse(text: str, page: str, position: int, closing: str, depth: int, links_allowed: bool) -> Inline:
    assert depth <= 12, "inline nesting exceeds 12"
    html: str = ""
    plain: str = ""
    links: list[str] = []
    while position < len(text):
        tail: str = text[position:]
        if closing != "" and tail.startswith(closing):
            return Inline(html, plain, position + len(closing), links)
        character: str = text[position]
        if character == "\\":
            assert position + 1 < len(text), "unfinished inline escape"
            character = text[position + 1]
            html = html + escape(character)
            plain = plain + character
            position = position + 2
        elif character == "`":
            end: int = text[position + 1 :].find("`")
            assert end >= 0, "unclosed inline code"
            value: str = text[position + 1 : position + 1 + end]
            html = html + "<code>" + escape(value) + "</code>"
            plain = plain + value
            position = position + end + 2
        elif tail.startswith("**") or character == "_":
            delimiter: str = "**" if tail.startswith("**") else "_"
            tag: str = "strong" if delimiter == "**" else "em"
            child: Inline = parse(text, page, position + len(delimiter), delimiter, depth + 1, links_allowed)
            html = html + "<" + tag + ">" + child.html + "</" + tag + ">"
            plain = plain + child.plain
            links = links + child.links
            position = child.end
        elif character == "[":
            assert links_allowed, "nested links are unsupported"
            label: Inline = parse(text, page, position + 1, "]", depth + 1, False)
            assert text[label.end : label.end + 1] == "(", "link lacks destination"
            end: int = text[label.end + 1 :].find(")")
            assert end >= 0, "unclosed link destination"
            target: str = text[label.end + 1 : label.end + 1 + end]
            address: tuple[str, str, str] = destination(target, page)
            html = html + '<a href="' + escape(address[0]) + '">' + label.html + "</a>"
            plain = plain + label.plain
            links.append(target)
            position = label.end + end + 2
        else:
            html = html + escape(character)
            plain = plain + character
            position = position + 1
    assert closing == "", "unclosed inline delimiter"
    return Inline(html, plain, position, links)


def render(text: str, page: str) -> Inline:
    assert len(text.encode()) <= 8192, "inline block exceeds 8192 bytes"
    return parse(text, page, 0, "", 0, True)
