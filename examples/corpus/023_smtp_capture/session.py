"""SMTP command state remains Python; transport and persistence are separate modules."""

from enum import Enum

from config import stopping
from envelope import greeting_valid, parse_path
from storage import capture, fault, load
from wire import data, line, reply

from py2rust.stdlib import Json, TcpStream, json_int, json_string, tcp_set_deadline


class Stage(Enum):
    CONNECTED = 0
    GREETED = 1
    SENDER = 2
    RECIPIENT = 3


def serve(stream: TcpStream, policy: Json) -> None:
    stage: Stage = Stage.CONNECTED
    greeting: str = ""
    extended: bool = False
    sender: str = ""
    recipients: list[str] = []
    body: str = "7BIT"
    buffer: bytes = b""
    reply(stream, "220 capture.local ESMTP capture", policy)
    for command_index in range(json_int(policy["max_commands"])):
        if stopping():
            reply(stream, "421 Server stopping", policy)
            return
        tcp_set_deadline(stream, json_int(policy["command_ms"]))
        incoming: tuple[bytes, bytes, bool] = line(stream, buffer, 554)
        if not incoming[2]:
            return
        buffer = incoming[1]
        valid: bool = True
        for index in range(len(incoming[0])):
            if incoming[0][index] < 32 or incoming[0][index] > 126:
                valid = False
        if not valid:
            reply(stream, "500 ASCII command required", policy)
            continue
        text: str = incoming[0].decode()
        command: str = text.upper()
        argument: str = ""
        split: int = text.find(" ")
        if split >= 0:
            command = text[:split].upper()
            argument = text[split + 1 :]
        if command != "MAIL" and len(incoming[0]) > 510:
            reply(stream, "500 Command too long", policy)
        elif command in ["QUIT", "RSET", "DATA"] and argument != "":
            reply(stream, "501 Unexpected argument", policy)
        elif command == "QUIT":
            reply(stream, "221 Bye", policy)
            return
        elif command == "NOOP":
            reply(stream, "250 OK", policy)
        elif command == "RSET":
            recipients.clear()
            sender = ""
            if greeting != "":
                stage = Stage.GREETED
            reply(stream, "250 Reset", policy)
        elif command in ["EHLO", "HELO"]:
            if not greeting_valid(argument):
                reply(stream, "501 Invalid greeting", policy)
            else:
                greeting = argument
                extended = command == "EHLO"
                stage = Stage.GREETED
                recipients.clear()
                sender = ""
                response: str = "250 capture.local"
                if extended:
                    response = (
                        "250-capture.local\r\n250-SIZE " + str(json_int(policy["max_bytes"])) + "\r\n250 8BITMIME"
                    )
                reply(stream, response, policy)
        elif command == "MAIL":
            if stage != Stage.GREETED:
                reply(stream, "503 Greeting or RSET required", policy)
            else:
                parsed: Json = parse_path(argument, True, extended, policy)
                code: int = json_int(parsed["code"])
                if code == 250:
                    sender = json_string(parsed["address"])
                    body = json_string(parsed["body"])
                    recipients.clear()
                    stage = Stage.SENDER
                reply(stream, str(code) + " Sender", policy)
        elif command == "RCPT":
            if stage not in [Stage.SENDER, Stage.RECIPIENT]:
                reply(stream, "503 MAIL required", policy)
            else:
                parsed: Json = parse_path(argument, False, extended, policy)
                code: int = json_int(parsed["code"])
                if code == 250:
                    recipient: str = json_string(parsed["address"])
                    if recipient not in recipients:
                        if len(recipients) >= json_int(policy["max_recipients"]):
                            code = 452
                        else:
                            recipients.append(recipient)
                    if code == 250:
                        stage = Stage.RECIPIENT
                reply(stream, str(code) + " Recipient", policy)
        elif command == "DATA":
            if stage != Stage.RECIPIENT:
                reply(stream, "503 RCPT required", policy)
            elif len(load(policy, False)) >= json_int(policy["max_messages"]):
                reply(stream, "452 Capture storage full", policy)
            else:
                reply(stream, "354 End with CRLF dot CRLF", policy)
                received: tuple[bytes, bytes, int] = data(stream, buffer, body, policy)
                buffer = received[1]
                code: int = received[2]
                response: str = str(code) + " Message rejected"
                if code == 250:
                    name: str = capture(sender, recipients, greeting, body, received[0], policy)
                    response = "250 Captured " + name
                stage = Stage.GREETED
                recipients.clear()
                sender = ""
                reply(stream, response, policy)
                fault("after_reply")
        else:
            reply(stream, "502 Command not implemented", policy)
    reply(stream, "421 Command budget exhausted", policy)
    return
