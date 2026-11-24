"""A small line protocol with unique nicknames and room-isolated broadcasts."""

from model import broadcast, drop, enqueue, store

from py2rust.stdlib import (
    Json,
    json_dumps,
    json_int,
    json_keys,
    json_string,
    regex_fullmatch,
)


def command(state: Json, key: str, line: str, policy: Json) -> Json:
    split: int = line.find(" ")
    verb: str = line
    argument: str = ""
    if split >= 0:
        verb = line[:split]
        argument = line[split + 1 :]
    peer: Json = state["peers"][key]
    nick: str = json_string(peer["nick"])
    room: str = json_string(peer["room"])
    if verb == "PING":
        return enqueue(state, key, "PONG " + argument, policy)
    if verb == "NICK":
        if not regex_fullmatch("[A-Za-z][A-Za-z0-9_]{0,23}", argument):
            return enqueue(state, key, "ERR NICK", policy)
        for other in json_keys(state["peers"]):
            if other != key and json_string(state["peers"][other]["nick"]).lower() == argument.lower():
                return enqueue(state, key, "ERR IN_USE", policy)
        peer["nick"] = argument
        state = store(state, key, peer)
        state = enqueue(state, key, "OK NICK " + argument, policy)
        if nick != "" and nick != argument:
            state = broadcast(state, room, "RENAME " + room + " " + nick + " " + argument, policy)
        return state
    if verb == "JOIN":
        if nick == "":
            return enqueue(state, key, "ERR NEED_NICK", policy)
        if not regex_fullmatch("[A-Za-z0-9_-]{1,32}", argument):
            return enqueue(state, key, "ERR ROOM", policy)
        target: str = argument.lower()
        occupied: set[str] = set()
        for other in json_keys(state["peers"]):
            existing: str = json_string(state["peers"][other]["room"])
            if other != key and existing != "":
                occupied.add(existing)
        if target not in occupied and len(occupied) >= json_int(policy["max_rooms"]):
            return enqueue(state, key, "ERR ROOM_LIMIT", policy)
        if target != room:
            peer["room"] = target
            state = store(state, key, peer)
            state = broadcast(state, room, "LEAVE " + room + " " + nick + " move", policy)
            state = enqueue(state, key, "OK JOIN " + target, policy)
            return broadcast(state, target, "JOIN " + target + " " + nick, policy)
        return enqueue(state, key, "OK JOIN " + target, policy)
    if verb == "SAY":
        if nick == "" or room == "":
            return enqueue(state, key, "ERR NEED_ROOM", policy)
        if argument.strip() == "":
            return enqueue(state, key, "ERR EMPTY", policy)
        sequence: int = json_int(state["sequence"]) + 1
        state["sequence"] = sequence
        return broadcast(state, room, "MSG " + str(sequence) + " " + room + " " + nick + " " + argument, policy)
    if argument != "":
        return enqueue(state, key, "ERR ARGUMENT", policy)
    if verb == "WHO":
        if room == "":
            return enqueue(state, key, "ERR NEED_ROOM", policy)
        names: list[str] = []
        for other in json_keys(state["peers"]):
            if json_string(state["peers"][other]["room"]) == room:
                names.append(json_string(state["peers"][other]["nick"]))
        names.sort()
        return enqueue(state, key, "USERS " + room + " " + ",".join(names), policy)
    if verb == "ROOMS":
        rooms: set[str] = set()
        for other in json_keys(state["peers"]):
            joined: str = json_string(state["peers"][other]["room"])
            if joined != "":
                rooms.add(joined)
        names: list[str] = []
        for joined in rooms:
            names.append(joined)
        names.sort()
        return enqueue(state, key, "ROOMS " + ",".join(names), policy)
    if verb == "STATS":
        return enqueue(
            state,
            key,
            "STATS "
            + json_dumps(
                {"peers": len(json_keys(state["peers"])), "messages": state["sequence"], "closed": state["closed"]}
            ),
            policy,
        )
    if verb == "QUIT":
        state = enqueue(state, key, "BYE", policy)
        return drop(state, key, "quit", True, policy)
    return enqueue(state, key, "ERR COMMAND", policy)
