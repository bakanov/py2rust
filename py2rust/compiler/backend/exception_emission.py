"""Render prepared exception regions without inspecting Python or compiler IR."""

# Joins keep the actual renderer in the native subset and avoid repeated copies.
# ruff: noqa: FLY002


def render_finally(
    body: str,
    cleanup: str,
    result_type: str,
    region: int,
    inherited_error: str,
    nested_return: bool,
    body_terminates: bool,
    cleanup_terminates: bool,
    statement_terminates: bool,
) -> str:
    pending = "__pending_result_" + str(region)
    active = "__finally_error_" + str(region)
    completion = "" if body_terminates else "Ok(rt::TryFlow::Continue)"
    cleanup_completion = "" if cleanup_terminates else "Ok(rt::TryFlow::Continue)"
    returned = "rt::TryFlow::Return(__value)" if nested_return else "__value"
    continued = 'unreachable!("protected statement always returns")' if statement_terminates else ""
    return "".join(
        [
            "{ let ",
            pending,
            " = (|| -> rt::Result<rt::TryFlow<",
            result_type,
            ">> {\n",
            body,
            "\n",
            completion,
            "\n})();\nlet ",
            active,
            ": String = ",
            pending,
            ".as_ref().err().map(|__error| __error.to_string()).unwrap_or_else(|| ",
            inherited_error,
            ");\nlet __cleanup_result = (|| -> rt::Result<rt::TryFlow<",
            result_type,
            ">> {\n",
            cleanup,
            "\n",
            cleanup_completion,
            "\n})();\nmatch __cleanup_result? {\nrt::TryFlow::Return(__value) => return Ok(",
            returned,
            "),\nrt::TryFlow::Continue => match ",
            pending,
            "? {\nrt::TryFlow::Return(__value) => return Ok(",
            returned,
            "),\nrt::TryFlow::Continue => { ",
            continued,
            " }\n}\n}\n}",
        ]
    )


def render_handler(
    body: str,
    success: str,
    failure: str,
    result_type: str,
    active_error: str,
    nested_return: bool,
    body_terminates: bool,
) -> str:
    returned = "rt::TryFlow::Return(__value)" if nested_return else "__value"
    completion = "" if body_terminates else "Ok(rt::TryFlow::Continue)"
    if body_terminates:
        success = 'unreachable!("protected block always returns")'
    return "".join(
        [
            "match (|| -> rt::Result<rt::TryFlow<",
            result_type,
            ">> {\n",
            body,
            "\n",
            completion,
            "\n})() {\nOk(rt::TryFlow::Continue) => { ",
            success,
            " },\nOk(rt::TryFlow::Return(__value)) => return Ok(",
            returned,
            "),\nErr(",
            active_error,
            ") => { ",
            failure,
            " }\n}",
        ]
    )


def render_resource(value: str, name: str, resource_type: str, body: str) -> str:
    return "".join(
        [
            "{ let __resource_guard = rt::ResourceGuard::new(",
            value,
            ")?;\nlet ",
            name,
            ": ",
            resource_type,
            " = __resource_guard.handle();\n",
            body,
            "\n}",
        ]
    )
