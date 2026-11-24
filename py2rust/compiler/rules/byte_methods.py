"""Byte-buffer methods, with explicit overloads and receiver-first evaluation."""

from dataclasses import dataclass


@dataclass
class ByteMethodRule:
    key: str
    form: str
    target: str
    result: str
    argument: str


def select_byte_method(receiver: str, method: str, arity: int, encoding: str) -> ByteMethodRule:
    if receiver != "bytes" and receiver != "bytearray":
        return ByteMethodRule("", "", "", "", "")
    if method == "decode" and (arity == 0 or arity == 1):
        if encoding == "utf-8" or encoding == "utf8":
            return ByteMethodRule("bytes.decode.utf8", "utf8", "", "str", "")
        if encoding == "latin-1" or encoding == "latin1" or encoding == "iso-8859-1" or encoding == "iso8859-1":
            return ByteMethodRule("bytes.decode.latin1", "decode", "decode_latin1", "str", "")
        if encoding == "cp437" or encoding == "437" or encoding == "ibm437":
            return ByteMethodRule("bytes.decode.cp437", "decode", "decode_cp437", "str", "")
        if encoding == "ascii":
            return ByteMethodRule("bytes.decode.ascii", "decode_checked", "decode_ascii", "str", "")
    if method == "hex" and arity == 0:
        return ByteMethodRule("bytes.hex", "decode", "bytes_hex", "str", "")
    if receiver == "bytes" and arity == 1:
        if method == "find":
            return ByteMethodRule("bytes.find", "find", "bytes_find", "int", "bytes")
        if method == "join":
            return ByteMethodRule("bytes.join", "join", "", "bytes", "list[bytes]")
        if method == "startswith":
            return ByteMethodRule("bytes.startswith", "predicate", "starts_with", "bool", "bytes")
        if method == "endswith":
            return ByteMethodRule("bytes.endswith", "predicate", "ends_with", "bool", "bytes")
    return ByteMethodRule("", "", "", "", "")


def render_byte_method(rule: ByteMethodRule, receiver: str, argument: str) -> str:
    if rule.form == "utf8":
        return "String::from_utf8(" + receiver + ")?"
    if rule.form == "decode" or rule.form == "decode_checked":
        result = "rt::" + rule.target + "(&(" + receiver + "))"
        if rule.form == "decode_checked":
            result = result + "?"
        return result
    if rule.form == "find":
        return "rt::bytes_find(&(" + receiver + "), &(" + argument + "))"
    if rule.form == "predicate":
        return "(" + receiver + ")." + rule.target + "(&(" + argument + "))"
    if rule.form == "join":
        return (
            "{ let __separator = "
            + receiver
            + "; let __parts: Vec<Vec<u8>> = "
            + argument
            + "; __parts.join(__separator.as_slice()) }"
        )
    return ""
