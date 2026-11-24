"""Independent website fixture checks URL graph traversal and broken-link provenance."""

import contextlib
import http.server
import json
import threading
from collections.abc import Iterator
from pathlib import Path

from .common import Application


@contextlib.contextmanager
def website() -> Iterator[tuple[str, dict, list]]:
    routes = {}
    calls = []

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            calls.append(self.path)
            route = routes.get(self.path, {"status": 404, "body": "missing"})
            if route.get("disconnect"):
                self.close_connection = True
                return
            body = route.get("body", "")
            if isinstance(body, str):
                body = body.encode()
            self.send_response(route.get("status", 200))
            self.send_header("Content-Type", route.get("type", "text/html; charset=utf-8"))
            self.send_header("Content-Length", str(len(body)))
            for name, value in route.get("headers", {}).items():
                self.send_header(name, value)
            self.end_headers()
            with contextlib.suppress(OSError):
                self.wfile.write(body)
            return

        def log_message(self, *args: object) -> None:
            return

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}", routes, calls
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)
    return


def check(application: Application, directory: Path) -> dict:
    config = directory / "audit.json"
    report_path = directory / "report.json"
    settings = {"AUDIT_CONFIG": str(config), "AUDIT_REPORT": str(report_path)}
    observations = {}
    with website() as (base, routes, calls), website() as (foreign, foreign_routes, foreign_calls):
        foreign_routes["/steal"] = {"body": "must not be fetched"}
        root = f"""<!doctype html><html><head><base href="./pages/"><base href="/ignored/">
<script>const bad = '<a href="/script-fiction">';</script></head><body>
<!-- <a href="/comment-fiction"> -->
<a href="a.html?x=1&amp;y=2">page A</a><a href="a.html?x=1&amp;y=2#part">same page</a>
<img src="../img/世界.png"><a href="../index.html#top">home</a>
<a href="/missing">missing</a><a href="/redirect">redirect</a>
<a href="/loop-a">loop</a><a href="/offline">offline</a><a href="/plain">plain text</a>
<a href="{foreign}/steal">external</a><a href="//{foreign.split('//')[1]}/other">external origin</a>
<a href="mailto:person@example.org">mail</a><a href="javascript:alert(1)">script</a>
<a href="http://127.1/">ambiguous IPv4</a><textarea><a href="/textarea-fiction"></textarea>
<template><a href="/template-fiction"></a></template>
<noscript><a href="/noscript-fiction"></a></noscript></body></html>"""
        routes.update(
            {
                "/site/index.html": {"body": root},
                "/site/pages/a.html?x=1&y=2": {"body": '<a href="b.html">B</a><a href="../index.html">back</a>'},
                "/site/pages/b.html": {"body": '<a href="deep.html">deeper</a>'},
                "/site/pages/deep.html": {"body": '<a href="/site/index.html">cycle</a>'},
                "/site/img/%E4%B8%96%E7%95%8C.png": {"body": b"\x00\xff\x80", "type": "image/png"},
                "/redirect": {"status": 302, "headers": {"Location": "/site/pages/final.html"}},
                "/site/pages/final.html": {"body": '<a href="/missing#again">still missing</a>'},
                "/loop-a": {"status": 301, "headers": {"Location": "/loop-b"}},
                "/loop-b": {"status": 308, "headers": {"Location": "/loop-a"}},
                "/offline": {"disconnect": True},
                "/plain": {"body": '<a href="/plain-fiction">not HTML</a>', "type": "text/plain"},
                "/clean/": {"body": '<a href="a">A</a><a href="b">B</a>'},
                "/clean/a": {"body": '<a href="b">B again</a>'},
                "/clean/b": {"body": '<a href="./">cycle</a>'},
                "/shortest/": {"body": '<a href="branch">branch</a><a href="jump">jump</a>'},
                "/shortest/branch": {"body": '<a href="target">target at depth 2</a>'},
                "/shortest/jump": {"status": 307, "headers": {"Location": "target"}},
                "/shortest/target": {"body": '<a href="leaf">reachable at depth 2</a>'},
                "/shortest/leaf": {"body": "done"},
            }
        )

        def run(start: str, patch: dict | None = None, code: int = 0) -> dict:
            policy = {"start": base + start, "max_depth": 3, "timeout_ms": 1000, **(patch or {})}
            config.write_text(json.dumps(policy))
            calls.clear()
            result = application.run(directory, settings)
            assert result.returncode == code, result.stderr + result.stdout
            report = json.loads(report_path.read_text())
            assert json.loads(result.stdout) == report["summary"]
            urls = [page["url"] for page in report["pages"]]
            assert len(urls) == len(set(urls)) == len(calls)
            assert not foreign_calls
            return report

        first = run("/site/index.html", code=1)
        expected_paths = {
            "/site/index.html",
            "/site/pages/a.html?x=1&y=2",
            "/site/pages/b.html",
            "/site/pages/deep.html",
            "/site/img/%E4%B8%96%E7%95%8C.png",
            "/missing",
            "/redirect",
            "/site/pages/final.html",
            "/loop-a",
            "/loop-b",
            "/offline",
            "/plain",
        }
        assert set(calls) == expected_paths, calls
        assert first["complete"] and first["summary"]["broken_pages"] == 4 and first["summary"]["broken_links"] == 7
        failures = {page["url"].removeprefix(base): page["terminal"]["outcome"] for page in first["broken_pages"]}
        assert failures == {
            "/missing": "http_error",
            "/loop-a": "redirect_loop",
            "/loop-b": "redirect_loop",
            "/offline": "transport",
        }
        assert first["summary"]["outcomes"]["external"] == first["summary"]["outcomes"]["ignored_scheme"] == 2
        normalized = json.loads(
            json.dumps(first)
            .replace(base, "<site>")
            .replace(foreign, "<external>")
            .replace(foreign.removeprefix("http:"), "//<external>")
        )
        observations["site"] = normalized
        repeated = run("/site/index.html", code=1)
        assert repeated == first

        clean = run("/clean/")
        assert set(calls) == {"/clean/", "/clean/a", "/clean/b"} and clean["summary"]["broken_links"] == 0
        budgets = {}
        for name, patch, expected in [
            ("depth", {"max_depth": 0}, ["/clean/"]),
            ("pages", {"max_pages": 2}, ["/clean/", "/clean/a"]),
            ("edges", {"max_edges": 1}, ["/clean/", "/clean/a"]),
        ]:
            limited = run("/clean/", patch, code=2)
            assert calls == expected and not limited["complete"]
            budgets[name] = {"requests": calls.copy(), "links": limited["summary"]["links"]}
        observations["budgets"] = budgets
        short = run("/shortest/", {"max_depth": 2})
        depths = {page["url"].removeprefix(base): page["depth"] for page in short["pages"]}
        assert depths == {
            "/shortest/": 0,
            "/shortest/branch": 1,
            "/shortest/jump": 1,
            "/shortest/target": 1,
            "/shortest/leaf": 2,
        }
        assert short["summary"]["outcomes"]["shorter"] == 1 and short["complete"]
        observations["shortest_depth"] = depths

        rejection_cases = {
            "invalid-utf8": {"body": b"\xff"},
            "wrong-charset": {"body": '<a href="/no">', "type": "text/html; charset=windows-1251"},
            "fake-charset": {"body": '<a href="/no">', "type": "text/html; charset=utf-8-malformed"},
            "gzip": {"body": b"\x00", "headers": {"Content-Encoding": "gzip"}},
            "invalid-base": {"body": '<base href="javascript:bad"><a href="/no">'},
            "bad-redirect": {"status": 302},
            "file-redirect": {"status": 302, "headers": {"Location": "file:///private"}},
            "transport": {"disconnect": True},
        }
        outcomes = {}
        for name, route in rejection_cases.items():
            routes["/reject"] = route
            rejected = run("/reject", code=1)
            assert calls == ["/reject"] and rejected["summary"]["broken_pages"] == 1
            outcomes[name] = rejected["pages"][0]["kind"]
        assert outcomes == {
            "invalid-utf8": "parse_error",
            "wrong-charset": "parse_error",
            "fake-charset": "parse_error",
            "gzip": "parse_error",
            "invalid-base": "base_error",
            "bad-redirect": "redirect_error",
            "file-redirect": "redirect_error",
            "transport": "transport",
        }
        routes["/reject"] = {"body": '<a href="/one">one</a><a href="/two">two</a>'}
        assert run("/reject", {"max_links": 1}, code=1)["pages"][0]["kind"] == "parse_error"
        assert calls == ["/reject"]
        assert run("/reject", {"max_body": 1}, code=1)["pages"][0]["kind"] == "transport"
        assert calls == ["/reject"]
        observations["rejections"] = outcomes

        routes["/external-base"] = {"body": f'<base href="{foreign}/"><a href="steal">outside</a>'}
        external = run("/external-base")
        assert calls == ["/external-base"] and external["summary"]["outcomes"] == {"external": 1}
        routes["/away"] = {"status": 302, "headers": {"Location": foreign + "/steal"}}
        assert run("/away")["summary"]["outcomes"] == {"external": 1} and calls == ["/away"]
        observations["external_requests"] = len(foreign_calls)

        protected = report_path.read_bytes()
        for change in [
            {"max_pages": 0},
            {"max_depth": -1},
            {"max_depth": True},
            {"max_edges": 0},
            {"max_links": 10001},
            {"timeout_ms": 0},
            {"max_body": 0},
            {"extra": 1},
            {"start": foreign + "/bad%escape"},
            {"start": "http://user@localhost/"},
        ]:
            config.write_text(json.dumps({"start": base + "/clean/", **change}))
            before_calls = calls.copy()
            assert application.run(directory, settings).returncode != 0
            assert calls == before_calls and report_path.read_bytes() == protected
        config.write_text(json.dumps({"start": base + "/clean/"}))
        old_config = config.read_bytes()
        for destination in [config, directory / "hardlink.json", directory / "symlink.json"]:
            if destination.name == "hardlink.json":
                destination.hardlink_to(config)
            elif destination.name == "symlink.json":
                destination.symlink_to(config)
            before_calls = calls.copy()
            assert application.run(directory, dict(settings, AUDIT_REPORT=str(destination))).returncode != 0
            assert calls == before_calls and config.read_bytes() == old_config
        observations["protected_configuration"] = True
    return observations
