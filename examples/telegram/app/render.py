"""Render escaped HTML in Python; the browser only handles interactions."""

from py2rust.stdlib import Json, json_int

from .model import find_chat, matches, message_preview, visible
from .store import items, text


def escape(value: str) -> str:
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )


def inline_format(body: str, depth: int) -> str:
    """A deliberately small Markdown dialect: **bold** and *italic*, safely escaped."""
    output: str = ""
    position: int = 0
    while position < len(body):
        remaining: str = body[position:]
        marker: str = "*"
        opening: str = "<em>"
        ending: str = "</em>"
        if remaining.startswith("**"):
            marker = "**"
            opening = "<strong>"
            ending = "</strong>"
        if remaining.startswith("***"):
            marker = "***"
            opening = "<strong><em>"
            ending = "</em></strong>"
        if remaining.startswith(marker) and depth < 2:
            tail: str = remaining[len(marker) :]
            closing: int = tail.find(marker)
            if marker == "**" and closing > 0 and tail[closing : closing + 3] == "***":
                closing = closing + 1
            if closing > 0:
                output = output + opening + inline_format(tail[:closing], depth + 1) + ending
                position = position + len(marker) + closing + len(marker)
                continue
        if body[position] == "\n":
            output = output + "<br>"
        else:
            output = output + escape(body[position])
        position = position + 1
    return output


def avatar(title: str, kind: str) -> str:
    symbol: str = escape(title[:1].upper())
    if kind == "note":
        symbol = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7"><path d="M6 4h12v17l-6-4-6 4z"/></svg>'
    return '<span class="avatar ' + kind + '">' + symbol + "</span>"


def chat_list(state: Json, user_id: str, selected: str, category: str, query: str) -> str:
    output: str = ""
    for chat in items(state, "chats"):
        kind: str = text(chat, "kind")
        chat_id: str = text(chat, "id")
        if not visible(chat, user_id):
            continue
        if category == "notes" and kind != "note":
            continue
        if query != "" and query.lower() not in text(chat, "title").lower():
            continue
        latest: Json = {}
        count: int = 0
        for message in items(state, "messages"):
            if text(message, "chat") == chat_id:
                latest = message
                count = count + 1
        active: str = ""
        if chat_id == selected:
            active = " active"
        preview: str = "Your own space for messages and files"
        if kind == "chat":
            preview = "Start a conversation"
        if count > 0:
            preview = message_preview(latest)
        output = (
            output
            + '<button class="chat-row'
            + active
            + '" data-chat="'
            + chat_id
            + '">'
            + avatar(text(chat, "title"), kind)
        )
        output = (
            output
            + '<span class="chat-copy"><span class="chat-line"><strong>'
            + escape(text(chat, "title"))
            + "</strong><time>"
            + escape(text(latest, "created")[11:16])
            + "</time></span>"
        )
        output = output + '<span class="chat-preview">' + escape(preview) + "</span></span></button>"
    if output == "":
        output = '<p class="list-empty">No conversations here yet.</p>'
    return output


def attachment_html(attachment: Json) -> str:
    file_id: str = text(attachment, "id")
    name: str = escape(text(attachment, "name"))
    url: str = "/files/" + file_id
    output: str = ""
    if text(attachment, "mime").startswith("image/"):
        output = (
            '<button class="photo-button" data-image="'
            + url
            + '" aria-label="Open image: '
            + name
            + '"><img class="message-image" loading="lazy" src="'
            + url
            + '" alt="'
            + name
            + '"></button>'
        )
    output = (
        output
        + '<a class="file-card" href="'
        + url
        + '?download=1" download="'
        + name
        + '"><span class="file-icon">↓</span><span><strong>'
        + name
        + "</strong><small>"
        + str(json_int(attachment["size"]))
        + " bytes · Download</small></span></a>"
    )
    return output


def message_html(message: Json, user_id: str, kind: str) -> str:
    own: bool = text(message, "user") == user_id
    classes: str = "message"
    if own:
        classes = classes + " outgoing"
    output: str = '<article class="' + classes + '" id="message-' + text(message, "id") + '"><div class="bubble">'
    if kind == "chat" and not own:
        output = output + '<strong class="sender">' + escape(text(message, "author")) + "</strong>"
    for attachment in items(message, "attachments"):
        output = output + attachment_html(attachment)
    output = (
        output
        + '<div class="message-text">'
        + inline_format(text(message, "body"), 0)
        + '</div><footer class="message-meta">'
    )
    if text(message, "edited") != "":
        output = output + "edited · "
    output = (
        output
        + '<time datetime="'
        + escape(text(message, "created"))
        + '">'
        + escape(text(message, "created")[11:16])
        + "</time>"
    )
    if own:
        output = output + '<span class="delivered" title="Saved on server">✓✓</span>'
    output = output + "</footer></div>"
    if own:
        output = (
            output
            + '<div class="message-actions"><button data-edit="'
            + text(message, "id")
            + '" aria-label="Edit message">Edit</button><button data-delete="'
            + text(message, "id")
            + '" aria-label="Delete message">Delete</button></div>'
        )
    return output + "</article>"


def conversation(state: Json, chat: Json, user_id: str) -> str:
    output: str = ""
    previous_date: str = ""
    for message in items(state, "messages"):
        if text(message, "chat") != text(chat, "id"):
            continue
        date: str = text(message, "created")[:10]
        if date != previous_date:
            output = output + '<div class="date-divider"><span>' + escape(date) + "</span></div>"
            previous_date = date
        output = output + message_html(message, user_id, text(chat, "kind"))
    if output == "":
        title: str = "A conversation starts here"
        description: str = "Send a message, share a screenshot, or attach a file."
        if text(chat, "kind") == "note":
            title = "A little space for everything"
            description = "Ideas, screenshots, links, and files. Only you can see this notebook."
        output = (
            '<div class="empty-conversation"><span class="empty-bookmark">✧</span><h2>'
            + title
            + "</h2><p>"
            + description
            + '</p><span class="empty-tip">Try **bold** or *italic* text</span></div>'
        )
    return output


def search_results(state: Json, user_id: str, query: str, scope: str) -> str:
    output: str = ""
    count: int = 0
    if query == "":
        return ""
    for message in items(state, "messages"):
        chat: Json = find_chat(state, text(message, "chat"), user_id)
        if text(chat, "id") == "" or not matches(message, query):
            continue
        if scope != "" and text(chat, "id") != scope:
            continue
        count = count + 1
        output = (
            output
            + '<button class="search-result" data-chat="'
            + text(chat, "id")
            + '" data-message="'
            + text(message, "id")
            + '"><strong>'
            + escape(text(chat, "title"))
            + "</strong><span>"
            + escape(message_preview(message))
            + "</span><small>"
            + escape(text(message, "author"))
            + " · "
            + escape(text(message, "created")[:10])
            + "</small></button>"
        )
    return '<div class="results-label">' + str(count) + " matching messages</div>" + output
