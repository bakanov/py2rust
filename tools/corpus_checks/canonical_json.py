"""Independent decimal-arithmetic oracle for the service's canonical JSON encoding."""

import decimal
import json


def canonical(value: object) -> bytes:
    if type(value) is float:
        if value == 0.0:
            return b"-0e0" if decimal.Decimal.from_float(value).is_signed() else b"0e0"
        # Decimal uses the exact binary64 value, independently of binary printf/ryu.
        with decimal.localcontext() as context:
            context.prec = 1100
            context.rounding = decimal.ROUND_HALF_EVEN
            scientific = format(decimal.Decimal.from_float(value), ".16e")
        mantissa, exponent = scientific.split("e")
        return (mantissa.rstrip("0").rstrip(".") + "e" + str(int(exponent))).encode()
    if isinstance(value, (list, tuple)):
        return b"[" + b",".join(canonical(item) for item in value) + b"]"
    if isinstance(value, dict):
        return b"{" + b",".join(canonical(key) + b":" + canonical(value[key]) for key in sorted(value)) + b"}"
    return json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode()
