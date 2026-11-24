"""Host validation for the portable Rust string-literal renderer."""

from .rules.literals import quote_scalar_text


def quote(text: str) -> str:
    # Retain the host API's ValueError while the native input boundary accepts
    # only Unicode scalar text. Neither path can emit a Rust surrogate escape.
    for char in text:
        if 0xD800 <= ord(char) <= 0xDFFF:
            raise ValueError("surrogate code points are unsupported")
    return quote_scalar_text(text)
