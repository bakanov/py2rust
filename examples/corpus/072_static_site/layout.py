"""Validate references across every page, then render standalone, linked HTML documents."""

# ruff: noqa: PLR1711, PLC0206 - explicit returns and supported subset operations

from inline import destination, escape
from markdown import Page

from py2rust.stdlib import Json, json_string, url_quote


def validate(pages: dict[str, Page]) -> None:
    for identifier in pages:
        for target in pages[identifier].links:
            address: tuple[str, str, str] = destination(target, identifier)
            if address[1] == "":
                continue
            assert address[1] in pages, "link references unknown page: " + address[1]
            if address[2] != "":
                found: bool = False
                for heading in pages[address[1]].headings:
                    found = found or json_string(heading["id"]) == address[2]
                assert found, "link references unknown heading: " + target
    return


def document(title: str, identifier: str, entries: list[Json], page: Page) -> str:
    navigation: str = ""
    current_title: str = ""
    for entry in entries:
        name: str = json_string(entry["id"])
        label: str = json_string(entry["title"])
        active: str = ' aria-current="page"' if name == identifier else ""
        navigation = navigation + '<a href="' + name + '.html"' + active + ">" + escape(label) + "</a>\n"
        if name == identifier:
            current_title = label
    contents: str = ""
    for heading in page.headings:
        contents = (
            contents
            + '<li><a href="#'
            + url_quote(json_string(heading["id"]))
            + '">'
            + escape(json_string(heading["text"]))
            + "</a></li>\n"
        )
    return (
        '<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n<title>'
        + escape(current_title)
        + " — "
        + escape(title)
        + '</title>\n<link rel="stylesheet" href="style.css">\n</head>\n<body>\n<header><p>'
        + escape(title)
        + '</p><nav aria-label="Pages">\n'
        + navigation
        + "</nav></header>\n"
        + '<aside aria-label="On this page"><ol>\n'
        + contents
        + "</ol></aside>\n<main>\n"
        + page.html
        + "</main>\n</body>\n</html>\n"
    )


def stylesheet() -> str:
    return (
        "body{max-width:70rem;margin:auto;padding:2rem;font:17px/1.6 system-ui;color:#213547;background:#f5f7fa}"
        "header{border-bottom:1px solid #ccd4dc}nav{display:flex;gap:1.2rem;flex-wrap:wrap;padding-bottom:1rem}"
        "a{color:#1468a0}a[aria-current]{font-weight:700}aside{float:right;max-width:30%;margin:1rem}"
        "main{overflow-wrap:anywhere}pre{overflow:auto;padding:1rem;background:#e5ebf0}"
        "code{font-family:ui-monospace,monospace}h1,h2,h3,h4,h5,h6{scroll-margin-top:1rem}"
        "@media(max-width:45rem){aside{float:none;max-width:none}body{padding:1rem}}\n"
    )
