"""Render control-flow forms from checked conditions and prepared return plans.

No parsing or syntax-tree wrappers are needed to compose these forms. The source
adapter still proves tail position and tracks pending exception/resource regions.
"""


def render_result_return(value: str, result_call: str, pending: bool, forward: bool, implicit: bool) -> str:
    assert not pending or (not forward and not implicit), "pending cleanup requires an explicit wrapped return"
    if pending:
        value = "rt::TryFlow::Return(" + value + ")"
    result = "Ok(" + value + ")"
    if forward:
        assert result_call != "", "Result forwarding requires an emitted Result call"
        result = result_call
    if implicit:
        return result
    return "return " + result + ";"


def render_borrow(value: str, style: str) -> str:
    if style == "existing":
        return value
    if style == "name":
        return "&" + value
    if style == "expression":
        return "&(" + value + ")"
    return ""


def render_function(signature: str, body: list[str], return_success: str) -> str:
    return signature + " {\n" + "\n".join(body) + "\n " + return_success + "}\n"


def render_if(condition: str, body: list[str], otherwise: list[str]) -> str:
    result = "if " + condition + " {\n" + "\n".join(body) + "\n}"
    if len(otherwise) > 0:
        result = result + " else {\n" + "\n".join(otherwise) + "\n}"
    return result


def render_while(condition: str, body: list[str]) -> str:
    if condition == "true":
        return "loop {\n" + "\n".join(body) + "\n}"
    return "while " + condition + " {\n" + "\n".join(body) + "\n}"


def render_assert(condition: str, message: str) -> str:
    return "if !(" + condition + ") { rt::assertion(false, &(" + message + "))?; }"


def render_raise(message: str) -> str:
    return "return Err(" + message + ".into());"


def render_reraise(active_error: str) -> str:
    return "return Err(" + active_error + ".to_string().into());"
