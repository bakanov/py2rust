"""HTTP application: identity, notes, chats, messages, files, and rendered views."""

from py2rust.stdlib import (
    Json,
    WebRequest,
    WebResponse,
    env_get,
    json_dumps,
    json_kind,
    json_parse,
    random_token,
    read_bytes,
    regex_fullmatch,
    url_quote,
    web_response,
    write_bytes,
)

from .model import (
    attachment_error,
    can_download,
    commit,
    create_chat,
    current_user,
    find_chat,
    resolve_attachments,
    timestamp,
    visible,
)
from .render import avatar, chat_list, conversation, search_results
from .store import data_path, items, load_state, text


def respond(status: int, value: Json) -> WebResponse:
    return web_response(status, json_dumps(value).encode(), {"Content-Type": "application/json; charset=utf-8"})


def error(status: int, message: str) -> WebResponse:
    return respond(status, {"error": message})


def sign_in(user: Json, show_key: bool) -> WebResponse:
    key: str = ""
    if show_key:
        key = text(user, "token")
    body: Json = {"id": text(user, "id"), "name": text(user, "name"), "key": key}
    headers: dict[str, str] = {
        "Content-Type": "application/json; charset=utf-8",
        "Set-Cookie": "paperplane=" + text(user, "token") + "; HttpOnly; SameSite=Strict; Path=/; Max-Age=31536000",
    }
    return web_response(200, json_dumps(body).encode(), headers)


def register(state: Json, body: Json) -> WebResponse:
    name: str = text(body, "name").strip()
    if len(name) < 1 or len(name) > 40:
        return error(400, "Choose a name between 1 and 40 characters.")
    for existing in items(state, "users"):
        if text(existing, "name").lower() == name.lower():
            return error(409, "That name is already in use. Sign in with your access key, or choose another name.")
    user: Json = {"id": random_token(), "name": name, "token": random_token()}
    users: list[Json] = items(state, "users")
    users.append(user)
    state["users"] = users
    chats: list[Json] = items(state, "chats")
    chats.append({"id": random_token(), "title": "Saved Messages", "kind": "note", "owner": text(user, "id")})
    chats.append({"id": random_token(), "title": "Ideas & inspiration", "kind": "note", "owner": text(user, "id")})
    state["chats"] = chats
    commit(state)
    return sign_in(user, True)


def view(state: Json, user: Json, request: WebRequest) -> WebResponse:
    user_id: str = text(user, "id")
    chat_id: str = request.query.get("chat", "")
    chat: Json = find_chat(state, chat_id, user_id)
    if text(chat, "id") == "":
        for candidate in items(state, "chats"):
            if text(candidate, "kind") == "note" and visible(candidate, user_id):
                chat = candidate
                break
    chat_id = text(chat, "id")
    subtitle: str = "Shared room · everyone on this server"
    if text(chat, "kind") == "note":
        subtitle = "Your personal cloud · only visible to you"
    query: str = request.query.get("q", "").strip()
    scope: str = request.query.get("scope", "")
    result: Json = {
        "revision": state["revision"],
        "chat_id": chat_id,
        "kind": text(chat, "kind"),
        "title": text(chat, "title"),
        "subtitle": subtitle,
        "me": text(user, "name"),
        "avatar": avatar(text(chat, "title"), text(chat, "kind")),
        "sidebar": chat_list(state, user_id, chat_id, request.query.get("category", "all"), query),
        "thread": conversation(state, chat, user_id),
        "search": search_results(state, user_id, query, scope),
        "can_rename": text(chat, "owner") == user_id,
    }
    return respond(200, result)


def send_message(state: Json, user: Json, body: Json) -> WebResponse:
    chat: Json = find_chat(state, text(body, "chat"), text(user, "id"))
    if text(chat, "id") == "":
        return error(404, "Conversation not found.")
    content: str = text(body, "body").strip()
    attachments: list[Json] = items(body, "attachments")
    if len(content) > 16000 or (content == "" and len(attachments) == 0):
        return error(400, "Write a message (up to 16,000 characters) or attach a file.")
    problem: str = attachment_error(state, user, attachments)
    if problem != "":
        return error(400, problem)
    message: Json = {
        "id": random_token(),
        "chat": text(chat, "id"),
        "user": text(user, "id"),
        "author": text(user, "name"),
        "body": content,
        "attachments": resolve_attachments(state, attachments),
        "created": timestamp(),
        "edited": "",
    }
    messages: list[Json] = items(state, "messages")
    messages.append(message)
    state["messages"] = messages
    commit(state)
    return respond(201, message)


def change_message(state: Json, user: Json, body: Json, delete: bool) -> WebResponse:
    messages: list[Json] = []
    found: bool = False
    for message in items(state, "messages"):
        if text(message, "id") == text(body, "id") and text(message, "user") == text(user, "id"):
            found = True
            if delete:
                continue
            content: str = text(body, "body").strip()
            if len(content) > 16000 or (content == "" and len(items(message, "attachments")) == 0):
                return error(400, "Write a message or keep an attachment.")
            message["body"] = content
            message["edited"] = timestamp()
        messages.append(message)
    if not found:
        return error(404, "Message not found or belongs to someone else.")
    state["messages"] = messages
    commit(state)
    return respond(200, {"ok": True})


def upload(state: Json, user: Json, request: WebRequest) -> WebResponse:
    name: str = request.query.get("name", "attachment").replace("\\", "/").split("/")[-1]
    if len(name) < 1 or len(name) > 200 or len(request.body) == 0:
        return error(400, "Choose a nonempty file with a name up to 200 characters.")
    file_id: str = random_token()
    mime: str = "application/octet-stream"
    data: bytes = request.body
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        mime = "image/png"
    elif data.startswith(b"\xff\xd8\xff"):
        mime = "image/jpeg"
    elif data.startswith(b"GIF87a") or data.startswith(b"GIF89a"):  # noqa: PIE810 -- explicit subset signatures
        mime = "image/gif"
    elif (
        len(data) > 12
        and data.startswith(b"RIFF")
        and data[8] == 87
        and data[9] == 69
        and data[10] == 66
        and data[11] == 80
    ):
        mime = "image/webp"
    attachment: Json = {"id": file_id, "name": name, "mime": mime, "size": len(data), "owner": text(user, "id")}
    write_bytes(data_path("uploads/" + file_id), data)
    uploads: list[Json] = items(state, "uploads")
    uploads.append(attachment)
    state["uploads"] = uploads
    commit(state)
    return respond(201, attachment)


def download(state: Json, user: Json, file_id: str, force: str) -> WebResponse:
    if not regex_fullmatch("[a-f0-9]{64}", file_id) or not can_download(state, file_id, text(user, "id")):
        return error(404, "File not found.")
    for attachment in items(state, "uploads"):
        if text(attachment, "id") == file_id:
            disposition: str = "attachment"
            if text(attachment, "mime").startswith("image/") and force != "1":
                disposition = "inline"
            headers: dict[str, str] = {
                "Content-Type": text(attachment, "mime"),
                "Content-Disposition": disposition + "; filename*=UTF-8''" + url_quote(text(attachment, "name")),
                "Content-Security-Policy": "default-src 'none'; sandbox",
            }
            return web_response(200, read_bytes(data_path("uploads/" + file_id)), headers)
    return error(404, "File not found.")


def handle(request: WebRequest) -> WebResponse:
    """The application entry: no handwritten Rust routing or business logic."""
    if request.method == "GET" and request.path in ["/", "/app.css", "/app.js", "/icon.svg"]:
        file_name: str = "index.html"
        content_type: str = "text/html; charset=utf-8"
        if request.path == "/app.css":
            file_name = "app.css"
            content_type = "text/css; charset=utf-8"
        elif request.path == "/app.js":
            file_name = "app.js"
            content_type = "text/javascript; charset=utf-8"
        elif request.path == "/icon.svg":
            file_name = "icon.svg"
            content_type = "image/svg+xml"
        return web_response(
            200,
            read_bytes(env_get("PAPER_PLANE_WEB", "web") + "/" + file_name),
            {
                "Content-Type": content_type,
                "Content-Security-Policy": "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' blob: data:; object-src 'none'; base-uri 'none'; frame-ancestors 'none'",
            },
        )
    if request.method == "GET" and request.path == "/health":
        return respond(200, {"ok": True})
    state: Json = load_state()
    body: Json = {}
    if request.method != "GET" and request.path != "/api/upload":
        body = json_parse(request.body.decode(), {})
        if json_kind(body) != "object":
            return error(400, "Expected a JSON object.")
    if request.method == "POST" and request.path == "/api/register":
        return register(state, body)
    if request.method == "POST" and request.path == "/api/login":
        for account in items(state, "users"):
            if text(account, "token") == text(body, "key").strip():
                return sign_in(account, False)
        return error(401, "That access key was not recognized.")
    user: Json = current_user(state, request.headers.get("cookie", ""))
    if text(user, "id") == "":
        return error(401, "Sign in to continue.")
    if request.method == "GET" and request.path == "/api/view":
        return view(state, user, request)
    if request.method == "GET" and request.path == "/api/account":
        return respond(200, {"name": text(user, "name"), "key": text(user, "token")})
    if request.method == "POST" and request.path == "/api/logout":
        return web_response(
            200,
            b"{}",
            {
                "Content-Type": "application/json",
                "Set-Cookie": "paperplane=; Path=/; HttpOnly; SameSite=Strict; Max-Age=0",
            },
        )
    if request.method == "POST" and request.path == "/api/chats":
        title: str = text(body, "title").strip()
        kind: str = text(body, "kind")
        if len(title) < 1 or len(title) > 80 or kind not in ["note", "chat"]:
            return error(400, "Choose a title (1–80 characters) and a conversation type.")
        return respond(201, create_chat(state, user, title, kind))
    if request.method == "POST" and request.path == "/api/rename":
        title: str = text(body, "title").strip()
        if len(title) < 1 or len(title) > 80:
            return error(400, "Choose a title between 1 and 80 characters.")
        chats: list[Json] = []
        found: bool = False
        for chat in items(state, "chats"):
            if text(chat, "id") == text(body, "id") and text(chat, "owner") == text(user, "id"):
                chat["title"] = title
                found = True
            chats.append(chat)
        if not found:
            return error(403, "Only the creator can rename this conversation.")
        state["chats"] = chats
        commit(state)
        return respond(200, {"ok": True})
    if request.method == "POST" and request.path == "/api/messages":
        return send_message(state, user, body)
    if request.method == "POST" and request.path == "/api/edit":
        return change_message(state, user, body, False)
    if request.method == "POST" and request.path == "/api/delete":
        return change_message(state, user, body, True)
    if request.method == "GET" and request.path == "/api/message":
        for message in items(state, "messages"):
            chat: Json = find_chat(state, text(message, "chat"), text(user, "id"))
            if text(chat, "id") != "" and text(message, "id") == request.query.get("id", ""):
                return respond(200, message)
        return error(404, "Message not found.")
    if request.method == "POST" and request.path == "/api/upload":
        return upload(state, user, request)
    if request.method == "GET" and request.path.startswith("/files/"):
        return download(state, user, request.path[7:], request.query.get("download", ""))
    return error(404, "Not found.")
