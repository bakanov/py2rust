"""Explicit ASCII dot-atom mailbox and ESMTP SIZE/BODY subsets."""

from py2rust.stdlib import Json, json_int, regex_fullmatch


def greeting_valid(value: str) -> bool:
    if regex_fullmatch("\\[[0-9]{1,3}([.][0-9]{1,3}){3}\\]", value):
        for part in value[1:-1].split("."):
            if int(part) > 255:
                return False
        return True
    if len(value) > 255:
        return False
    for label in value.split("."):
        if not regex_fullmatch("[A-Za-z0-9]([A-Za-z0-9-]{0,61}[A-Za-z0-9])?", label):
            return False
    return True


def mailbox(address: str, allow_empty: bool) -> bool:
    if address == "":
        return allow_empty
    parts: list[str] = address.split("@")
    if len(parts) != 2 or len(parts[0]) > 64 or len(address) > 254:
        return False
    atom: str = "[A-Za-z0-9!#$%&'*+/=?^_`{|}~-]+"
    if not regex_fullmatch(atom + "([.]" + atom + ")*", parts[0]):
        return False
    for label in parts[1].split("."):
        if not regex_fullmatch("[A-Za-z0-9]([A-Za-z0-9-]{0,61}[A-Za-z0-9])?", label):
            return False
    return True


def parse_path(argument: str, sender: bool, extended: bool, policy: Json) -> Json:
    prefix: str = "TO:<"
    if sender:
        prefix = "FROM:<"
    end: int = argument.find(">")
    if not argument.upper().startswith(prefix) or end < len(prefix):
        return {"code": 501}
    address: str = argument[len(prefix) : end]
    if not mailbox(address, sender):
        return {"code": 501}
    if address != "":
        parts: list[str] = address.split("@")
        address = parts[0] + "@" + parts[1].lower()
    tail: str = argument[end + 1 :]
    body: str = "7BIT"
    seen: set[str] = set()
    if tail != "":
        if not tail.startswith(" ") or tail.strip() == "":
            return {"code": 501}
        if not sender or not extended:
            return {"code": 555}
        for option in tail.strip().split():
            pair: list[str] = option.upper().split("=")
            if len(pair) != 2 or pair[0] in seen:
                return {"code": 501}
            seen.add(pair[0])
            if pair[0] == "SIZE":
                if not regex_fullmatch("[0-9]{1,9}", pair[1]):
                    return {"code": 501}
                if int(pair[1]) > json_int(policy["max_bytes"]):
                    return {"code": 552}
            elif pair[0] == "BODY":
                if pair[1] not in ["7BIT", "8BITMIME"]:
                    return {"code": 501}
                body = pair[1]
            else:
                return {"code": 555}
    return {"code": 250, "address": address, "body": body}
