"""Runtime record fields shared by frontend typing and Rust place selection."""


def runtime_field_type(record: str, field: str) -> str:
    if record == "WebRequest":
        if field == "method" or field == "path" or field == "target":
            return "str"
        if field == "body":
            return "bytes"
        if field == "headers" or field == "query":
            return "dict[str, str]"
    if record == "WebResponse":
        if field == "status":
            return "int"
        if field == "body":
            return "bytes"
        if field == "headers":
            return "dict[str, str]"
    if record == "HttpResponse":
        if field == "status":
            return "int"
        if field == "body":
            return "str"
    if record == "HttpReader":
        if field == "status":
            return "int"
        if field == "headers":
            return "dict[str, str]"
    return ""


def borrowed_runtime_field(record: str, field: str) -> bool:
    """Only owned web value fields have reviewed representation/lifetime rules.

    Status fields may require numeric conversion. HttpReader is a resource;
    knowing its field type is not permission to borrow through that resource.
    """
    if record != "WebRequest" and record != "WebResponse":
        return False
    typ: str = runtime_field_type(record, field)
    return typ == "str" or typ == "bytes" or typ == "dict[str, str]"


def dictionary_get_style(stable: bool, local_place: bool, literal_key: bool, empty_string_default: bool) -> str:
    """Only elide an effect-free literal default; arbitrary defaults stay eager."""
    if stable and local_place:
        if literal_key and empty_string_default:
            return "literal_default"
        return "borrow"
    return "preserve"
