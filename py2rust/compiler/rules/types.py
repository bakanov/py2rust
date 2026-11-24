"""Owned Rust representations for types already admitted by the frontend.

This is representation selection, not validation of source type annotations.
Borrowed parameter and recursive-field policies are applied separately.
"""


def render_owned_type(name: str, arguments: list[str]) -> str:
    if name == "int":
        return "i64"
    if name == "float":
        return "f64"
    if name == "str":
        return "String"
    if name == "bytes":
        return "Vec<u8>"
    if name == "bytearray":
        return "Vec<u8>"
    if name == "bool":
        return "bool"
    if name == "None":
        return "()"
    if name == "Json":
        return "rt::Json"
    if name == "DateTime":
        return "rt::DateTime"
    if name == "Rational":
        return "rt::Rational"
    if name == "HttpServer":
        return "rt::HttpServer"
    if name == "HttpResponse":
        return "rt::HttpResponse"
    if name == "WebRequest":
        return "rt::WebRequest"
    if name == "WebResponse":
        return "rt::WebResponse"
    if name == "StreamChunk":
        return "rt::StreamChunk"
    if name == "FileHandle":
        return "rt::FileHandle"
    if name == "GzipReader":
        return "rt::GzipReader"
    if name == "GzipWriter":
        return "rt::GzipWriter"
    if name == "LineReader":
        return "rt::LineReader"
    if name == "HttpReader":
        return "rt::HttpReader"
    if name == "TcpListener":
        return "rt::TcpListener"
    if name == "TcpStream":
        return "rt::TcpStream"
    if name == "UnixListener":
        return "rt::UnixListener"
    if name == "UnixStream":
        return "rt::UnixStream"
    if name == "UdpSocket":
        return "rt::UdpSocket"
    if name == "ProcessPool":
        return "rt::ProcessPool"
    if name == "Sha256":
        return "rt::Sha256"
    if name == "Exception":
        return "String"
    contents = ", ".join(arguments)
    if name == "tuple":
        return "(" + contents + ",)"
    if name == "list" or name == "tuple_var":
        return "Vec<" + contents + ">"
    if name == "dict":
        return "indexmap::IndexMap<" + contents + ">"
    if name == "set":
        return "std::collections::BTreeSet<" + contents + ">"
    return name
