"""Real project acceptance checks against both Python and generated Rust."""

import contextlib
import http.client
import json
import os
import select
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

import pytest
from py2rust.compiler.rust_imports import symbol_name

from .test_project import build
from .test_services import ROOT, parity

APP = ROOT / "examples/telegram"


@pytest.fixture(scope="module")
def chat_binary(tmp_path_factory):
    return build(APP, tmp_path_factory.mktemp("chat-rust"))


@contextlib.contextmanager
def running(command, data):
    process = subprocess.Popen(
        command,
        cwd=APP,
        env=dict(os.environ, PAPER_PLANE_DATA=str(data), PAPER_PLANE_PORT="0", PYTHONUNBUFFERED="1"),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        assert select.select([process.stdout], [], [], 15)[0], "server startup timed out"
        line = process.stdout.readline()
        assert line.startswith("LISTENING http://127.0.0.1:"), line
        yield int(line.strip().rsplit(":", 1)[1])
    finally:
        process.terminate()
        process.communicate(timeout=10)


class Client:
    def __init__(self, port):
        self.port, self.cookie = port, ""

    def request(self, path, value=None, raw=None, method=None, headers=None):
        method = method or ("POST" if value is not None or raw is not None else "GET")
        body = raw if raw is not None else json.dumps(value).encode() if value is not None else None
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=15)
        connection.request(method, path, body, {"Cookie": self.cookie, **(headers or {})})
        response = connection.getresponse()
        data, status = response.read(), response.status
        result_headers = {key.lower(): value for key, value in response.getheaders()}
        cookie = response.getheader("Set-Cookie")
        if cookie:
            self.cookie = cookie.split(";", 1)[0]
        connection.close()
        if response.getheader("Content-Type", "").startswith("application/json"):
            data = json.loads(data)
        return status, data, result_headers

    def ok(self, path, value=None, raw=None):
        status, value, _ = self.request(path, value, raw)
        assert status in {200, 201}, value
        return value


@pytest.mark.parametrize("engine", ["python", "rust"])
def test_real_chat_workflow(tmp_path, chat_binary, engine):
    command = [sys.executable, str(APP / "main.py")] if engine == "python" else [str(chat_binary)]
    data = tmp_path / "persistent"
    with running(command, data) as port:
        alice, bob, anonymous = Client(port), Client(port), Client(port)
        assert anonymous.request("/api/view")[0] == 401
        shell = anonymous.ok("/")
        assert b"Paper Plane" in shell
        account = alice.ok("/api/register", {"name": "Alice"})
        assert len(account["key"]) == 64
        bob.ok("/api/register", {"name": "Bob"})
        first_note = alice.ok("/api/view")["chat_id"]
        note = alice.ok("/api/chats", {"kind": "note", "title": "Research 世界"})
        room = alice.ok("/api/chats", {"kind": "chat", "title": "Project room"})
        assert note["id"] != first_note
        assert "Research 世界" not in bob.ok("/api/view")["sidebar"]
        assert "Project room" in bob.ok("/api/view")["sidebar"]
        body = "**Important** and *useful* 世界 ***both*** **bold with *italic***\n<script>alert(1)</script>"
        sent = alice.ok("/api/messages", {"chat": room["id"], "body": body})
        view = bob.ok("/api/view?chat=" + room["id"])
        assert "<strong>Important</strong>" in view["thread"]
        assert "<em>useful</em>" in view["thread"]
        assert "<strong><em>both</em></strong>" in view["thread"]
        assert "<strong>bold with <em>italic</em></strong>" in view["thread"]
        assert "<script>" not in view["thread"]
        assert "&lt;script&gt;" in view["thread"]
        assert "Alice" in view["thread"]
        assert bob.request("/api/messages", {"chat": note["id"], "body": "intruder"})[0] == 404
        assert bob.request("/api/edit", {"id": sent["id"], "body": "tampered"})[0] == 404
        assert bob.request("/api/rename", {"id": room["id"], "title": "stolen"})[0] == 403
        alice.ok("/api/rename", {"id": note["id"], "title": "Reading list"})
        assert "Reading list" in alice.ok("/api/view")["sidebar"]
        # Exact binary downloads, Unicode filenames, and safe image MIME sniffing.
        png = b"\x89PNG\r\n\x1a\n" + bytes(range(256))
        photo = alice.ok("/api/upload?name=screenshot.png", raw=png)
        document = alice.ok("/api/upload?name=notes-%E4%B8%96%E7%95%8C.txt", raw=b"notes\x00\xff\r\n")
        assert photo["mime"] == "image/png"
        assert document["name"] == "notes-世界.txt"
        private = alice.ok(
            "/api/messages", {"chat": note["id"], "body": "private research", "attachments": [photo, document]}
        )
        assert bob.request("/files/" + photo["id"])[0] == 404
        assert anonymous.request("/files/" + photo["id"])[0] == 401
        assert alice.ok("/files/" + photo["id"]) == png
        assert alice.ok("/files/" + document["id"]) == b"notes\x00\xff\r\n"
        assert (
            "filename*=UTF-8''notes-%E4%B8%96%E7%95%8C.txt"
            in alice.request("/files/" + document["id"])[2]["content-disposition"]
        )
        assert '<img class="message-image"' in alice.ok("/api/view?chat=" + note["id"])["thread"]
        assert "private research" not in bob.ok("/api/view?q=research")["search"]
        assert "1 matching messages" in alice.ok("/api/view?q=notes-")["search"]
        assert private["id"] in alice.ok("/api/view?q=research")["search"]
        shared = alice.ok("/api/messages", {"chat": room["id"], "body": "Shared file", "attachments": [document]})
        assert bob.ok("/files/" + document["id"]) == b"notes\x00\xff\r\n"
        assert bob.request("/api/messages", {"chat": room["id"], "body": "forge", "attachments": [document]})[0] == 400
        alice.ok("/api/edit", {"id": sent["id"], "body": "Edited **message**"})
        assert "Edited <strong>message</strong>" in bob.ok("/api/view?chat=" + room["id"])["thread"]
        alice.ok("/api/delete", {"id": shared["id"]})
        assert bob.request("/api/message?id=" + shared["id"])[0] == 404
        assert alice.request("/api/messages", {"chat": room["id"], "body": ""})[0] == 400
        assert alice.request("/api/messages", raw=b"[]")[0] == 400
        assert (
            alice.request(
                "/api/messages", {"chat": room["id"], "body": "cross origin"}, headers={"Origin": "http://evil.invalid"}
            )[0]
            == 403
        )
        assert alice.request("/files/../../state.json")[0] == 404
        assert anonymous.request("/api/view", method="POST")[0] == 401

        # Concurrent requests must not lose read-modify-write updates.
        def send(index):
            client = Client(port)
            client.cookie = alice.cookie
            return client.ok("/api/messages", {"chat": room["id"], "body": f"concurrent-{index}"})["id"]

        with ThreadPoolExecutor(max_workers=8) as pool:
            identifiers = list(pool.map(send, range(20)))
        thread = bob.ok("/api/view?chat=" + room["id"])["thread"]
        assert all(identifier in thread for identifier in identifiers)
        alice.ok("/api/logout", {})
        assert alice.request("/api/view")[0] == 401
    # Restart the actual process and recover the same profile, notes and bytes.
    with running(command, data) as port:
        restored = Client(port)
        restored.ok("/api/login", {"key": account["key"]})
        assert private["id"] in restored.ok("/api/view?chat=" + note["id"])["thread"]
        assert restored.ok("/files/" + photo["id"]) == png
        assert restored.ok("/api/account")["name"] == "Alice"


def test_new_subset_operations_match_python(tmp_path):
    parity(
        tmp_path,
        """
from py2rust.stdlib import Json, json_array, json_get, json_kind, json_parse, json_is_null, json_int, pretty, url_quote

def run() -> None:
    value: Json = {"count": 1, "rows": [{"name": "before"}]}
    value["count"] = json_int(value["count"]) + 1
    rows: list[Json] = []
    for row in json_array(value["rows"]):
        row["name"] = "after"
        rows.append(row)
    value["rows"] = rows
    assert json_kind(value) == "object"
    assert json_get(value, "missing", "fallback") == json_parse('"fallback"', None)
    assert json_is_null(json_parse("bad", None))
    text: str = "héllo 世界"
    assert text[-2:] == "世界"
    assert text[8:2] == ""
    assert text[-999:999] == text
    data: bytes = b"PNGdata"
    assert data.startswith(b"PNG")
    assert data.endswith(b"data")
    assert url_quote("a b/世界~.txt") == "a%20b%2F%E4%B8%96%E7%95%8C~.txt"
    print(pretty(value))
if __name__ == "__main__":
    run()
""",
    )


def test_readable_generated_names_do_not_collide():
    pairs = [
        ("a.b", "c"),
        ("a_b", "c"),
        ("a", "b__c"),
        ("a_", "b_c"),
        ("a", "escaped_5f"),
        ("a", "_"),
        ("世界", "name"),
    ]
    assert len({symbol_name(*pair) for pair in pairs}) == len(pairs)
    assert symbol_name("app.model", "find_chat") == "py__app__model__find_chat"
