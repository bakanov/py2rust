"""Conversation permissions, searching and message validation."""

from py2rust.stdlib import Json, datetime_iso, json_int, random_token, utc_now

from .store import items, save_state, text


def current_user(state: Json, cookie: str) -> Json:
    token: str = ""
    for part in cookie.split(";"):
        entry: str = part.strip()
        if entry.startswith("paperplane="):
            token = entry[11:]
    for user in items(state, "users"):
        if token != "" and text(user, "token") == token:
            return user
    return {}


def visible(chat: Json, user_id: str) -> bool:
    return text(chat, "kind") == "chat" or text(chat, "owner") == user_id


def find_chat(state: Json, chat_id: str, user_id: str) -> Json:
    for chat in items(state, "chats"):
        if text(chat, "id") == chat_id and visible(chat, user_id):
            return chat
    return {}


def commit(state: Json) -> None:
    state["revision"] = json_int(state["revision"]) + 1
    save_state(state)


def timestamp() -> str:
    return datetime_iso(utc_now())


def create_chat(state: Json, user: Json, title: str, kind: str) -> Json:
    chat: Json = {"id": random_token(), "title": title, "kind": kind, "owner": text(user, "id")}
    chats: list[Json] = items(state, "chats")
    chats.append(chat)
    state["chats"] = chats
    commit(state)
    return chat


def matches(message: Json, query: str) -> bool:
    if query.lower() in text(message, "body").lower():
        return True
    for attachment in items(message, "attachments"):
        if query.lower() in text(attachment, "name").lower():
            return True
    return False


def message_preview(message: Json) -> str:
    body: str = text(message, "body").replace("*", "").replace("\n", " ")
    if body != "":
        return body[:80]
    attachments: list[Json] = items(message, "attachments")
    if len(attachments) > 0:
        return text(attachments[0], "name")
    return "No messages yet"


def attachment_error(state: Json, user: Json, attachments: list[Json]) -> str:
    if len(attachments) > 10:
        return "Attach at most 10 files per message."
    for attachment in attachments:
        found: bool = False
        for upload in items(state, "uploads"):
            if text(upload, "id") == text(attachment, "id") and text(upload, "owner") == text(user, "id"):
                found = True
        if not found:
            return "One of the attachments is unavailable. Please attach it again."
    return ""


def resolve_attachments(state: Json, requested: list[Json]) -> list[Json]:
    result: list[Json] = []
    for attachment in requested:
        for upload in items(state, "uploads"):
            if text(upload, "id") == text(attachment, "id"):
                result.append(upload)
    return result


def can_download(state: Json, attachment_id: str, user_id: str) -> bool:
    for upload in items(state, "uploads"):
        if text(upload, "id") == attachment_id and text(upload, "owner") == user_id:
            return True
    for message in items(state, "messages"):
        chat: Json = find_chat(state, text(message, "chat"), user_id)
        if text(chat, "id") != "":
            for attachment in items(message, "attachments"):
                if text(attachment, "id") == attachment_id:
                    return True
    return False
