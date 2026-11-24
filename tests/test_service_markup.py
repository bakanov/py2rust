"""HTML and URL adapters checked against independently specified extraction and resolution cases."""

import json
from pathlib import Path

from .test_services import parity


def test_html5_links_and_inert_content(tmp_path: Path) -> None:
    document = """<!doctype html><html><head><base href="../assets/"><base href="/ignored/">
<style>a { content: '<a href="fake-style">'; }</style>
<script>const text = '<a href="fake-script">';</script></head><body>
<!-- <a href="fake-comment"> --><a HREF="first?a=1&amp;b=2" href="second">one</a>
<a href='entity&notit=1'>&copy;</a><area href=unquoted><a href>empty</a>
<img src="世界.png"><textarea><a href="fake-textarea"></textarea>
<template><a href="fake-template"></a></template>
<noscript><a href="fake-noscript"></a></noscript>
<svg><a href="fake-svg"></a></svg><video src="movie.webm" poster="cover.jpg"></video>
<object data="file.pdf"></object><link href="theme.css"><script src="app.js"></script>
</body></html>"""
    (tmp_path / "input.html").write_text(document)
    links = [
        ("a", "href", "first?a=1&b=2"),
        ("a", "href", "entity&notit=1"),
        ("area", "href", "unquoted"),
        ("a", "href", ""),
        ("img", "src", "世界.png"),
        ("video", "src", "movie.webm"),
        ("video", "poster", "cover.jpg"),
        ("object", "data", "file.pdf"),
        ("link", "href", "theme.css"),
        ("script", "src", "app.js"),
    ]
    expected = {
        "base": "../assets/",
        "links": [{"tag": tag, "attribute": attr, "value": value} for tag, attr, value in links],
    }
    (tmp_path / "expected.json").write_text(json.dumps(expected))
    output = parity(
        tmp_path,
        """from py2rust.stdlib import Json, html_links, json_dumps, json_loads, json_equal, read_text
def run() -> None:
    document: str = read_text("input.html")
    result: Json = html_links(document, 10)
    assert json_equal(result, json_loads(read_text("expected.json")))
    errors: int = 0
    for maximum in [0, -1, 9, 10001]:
        try:
            html_links(document, maximum)
        except Exception:
            errors = errors + 1
    assert errors == 4
    print(json_dumps(result))
    return
if __name__ == "__main__":
    run()
""",
    )
    assert json.loads(output) == expected
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def test_url_resolution_and_origin(tmp_path: Path) -> None:
    cases = [
        ("", "http://example.com/a/b?old=1"),
        ("#new", "http://example.com/a/b?old=1"),
        ("?", "http://example.com/a/b?"),
        ("?q=a b&quote='", "http://example.com/a/b?q=a%20b&quote=%27"),
        ("../x", "http://example.com/x"),
        ("%2e%2E/x", "http://example.com/x"),
        ("a//b", "http://example.com/a/a//b"),
        ("//Other.Example:443/x", "http://other.example:443/x"),
        ("/a/./b/../c", "http://example.com/a/c"),
        ("世界.png", "http://example.com/a/%E4%B8%96%E7%95%8C.png"),
        ("HTTP://example.COM:80", "http://example.com/"),
        ("/%2f?q=%ab", "http://example.com/%2F?q=%AB"),
        ("https://127.0.0.1:0443/a#fragment", "https://127.0.0.1/a"),
        ("/a/..", "http://example.com/"),
        ("/a//../b", "http://example.com/a/b"),
        ("../../../../../", "http://example.com/"),
    ]
    (tmp_path / "urls.json").write_text(json.dumps(cases))
    output = parity(
        tmp_path,
        """from py2rust.stdlib import Json, json_array, json_loads, json_string, read_text, url_resolve, url_origin
def run() -> None:
    base: str = "http://EXAMPLE.com:80/a/b?old=1#frag"
    for pair in json_array(json_loads(read_text("urls.json"))):
        assert url_resolve(base, json_string(pair[0])) == json_string(pair[1])
    assert url_origin(base) == "http://example.com"
    assert url_origin("https://example.com:443/a") == "https://example.com"
    assert url_origin("http://example.com:8080/a") == "http://example.com:8080"
    errors: int = 0
    for bad in ["file:///tmp/private", "javascript:alert(1)", "http:foo", "http:///empty", "http://user@example.com/", "http://127.1/", "http://0127.0.0.1/", "http://a.1/", "http://[::1]/", "http://example.com:0/", "http://example.com:65536/", "/bad%escape", "/bad\\nline", " /leading", "/trailing ", "/back\\\\slash"]:
        try:
            url_resolve(base, bad)
        except Exception:
            errors = errors + 1
    assert errors == 16
    print("URL resolution passed")
    return

if __name__ == "__main__":
    run()
""",
    )
    assert output == "URL resolution passed\n"
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def test_url_resolution_matrix(tmp_path: Path) -> None:
    bases = [
        "http://example.com/a/b",
        "https://example.com:443/a//b/?",
        "http://example.com/a/%2e%2e/b?q=old",
        "http://127.0.0.1:8000/",
        "http://example.com/?x=1",
        "http://example.com/a/../b/.",
    ]
    references = [
        "",
        "?",
        "#f",
        "../",
        "/.",
        "/..",
        "a//b",
        "./a/..",
        "//example.org/",
        "https://example.org/",
        "//EXAMPLE.org:0080/?",
        "?a='[]{}^`|",
        "/x;param",
        "/%2E./x",
        "%2e/%2e%2e/x",
        "http://0xfood/",
        "../../../a",
        "/a//../b",
        "/a/.../b",
        "//127.0.0.1./",
    ]
    references += [f"a{character}b" for character in " !\"$&'()+,;=@[]^`{|}~世界"]
    cases = [[base, ref] for base in bases for ref in references]
    (tmp_path / "matrix.json").write_text(json.dumps(cases))
    output = parity(
        tmp_path,
        """from py2rust.stdlib import Json, json_array, json_loads, json_string, json_dumps, read_text, url_resolve
def run() -> None:
    answers: list[Json] = []
    for pair in json_array(json_loads(read_text("matrix.json"))):
        result: str = "invalid"
        try:
            result = url_resolve(json_string(pair[0]), json_string(pair[1]))
        except Exception:
            pass
        answers.append({"input": pair, "result": result})
    print(json_dumps(answers))
    return
if __name__ == "__main__":
    run()
""",
    )
    assert len(json.loads(output)) == len(cases)
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def test_html_recovery_and_input_bounds(tmp_path: Path) -> None:
    (tmp_path / "oversized.txt").write_text("x" * 1048577)
    (tmp_path / "long-url.txt").write_text("x" * 8193)
    output = parity(
        tmp_path,
        """from py2rust.stdlib import Json, html_links, json_equal, read_text, url_resolve
def run() -> None:
    result: Json = html_links("<div><A HREF=x><b>unterminated &amp; <img SRC='y'>", 10)
    expected: Json = {"base": None, "links": [{"tag": "a", "attribute": "href", "value": "x"}, {"tag": "img", "attribute": "src", "value": "y"}]}
    assert json_equal(result, expected)
    assert json_equal(html_links("<!-- never closed <a href='/fake'>", 10), {"base": None, "links": []})
    failures: int = 0
    try:
        html_links(read_text("oversized.txt"), 10)
    except Exception:
        failures = failures + 1
    try:
        url_resolve("http://example.com/", read_text("long-url.txt"))
    except Exception:
        failures = failures + 1
    assert failures == 2
    print("HTML recovery and bounds passed")
    return
if __name__ == "__main__":
    run()
""",
    )
    assert output == "HTML recovery and bounds passed\n"
    return  # noqa: PLR1711 - explicit return required by repository guidelines
