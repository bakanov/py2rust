"""Adapt prepared readability choices to portable control-flow renderers."""

from ..readability import ReturnStyle
from ..rules.control_flow import render_borrow, render_result_return


def render_return(value: str, result_call: str | None, style: ReturnStyle) -> str:
    if style.forward_result and result_call is None:
        raise ValueError("Result forwarding requires an emitted Result call")
    return render_result_return(value, result_call or "", style.pending, style.forward_result, style.implicit)


def render_reference(value: str, style: str) -> str:
    if style not in {"existing", "name", "expression"}:
        raise ValueError("unknown reference style: " + style)
    return render_borrow(value, style)
