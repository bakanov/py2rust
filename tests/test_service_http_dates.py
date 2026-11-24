"""Independent calendar and deadline vectors for Retry-After in both execution engines."""

import datetime as dt
import json
from pathlib import Path

from .test_services import parity


def test_binary_chunks_join_without_text_decoding(tmp_path: Path) -> None:
    output = parity(
        tmp_path,
        """def run() -> None:
    chunks: list[bytes] = [b"", bytes.fromhex("00e4b8"), bytes.fromhex("96e7958cff"), b""]
    assert b"".join(chunks).hex() == "00e4b896e7958cff"
    assert b"--".join(chunks).hex() == "2d2d00e4b82d2d96e7958cff2d2d"
    empty: list[bytes] = []
    assert b"--".join(empty) == b""
    assert b"/".join([b"single"]) == b"single"
    print("binary chunks joined")
    return
if __name__ == "__main__":
    run()
""",
    )
    assert output == "binary chunks joined\n"
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def test_retry_after_calendar_and_decimal_delays(tmp_path: Path) -> None:
    now = dt.datetime(2024, 3, 1, 12, tzinfo=dt.timezone.utc).timestamp()
    cases = [["00012", now + 0.25, now + 12.25], ["\t 0 \t", now, now], ["0" * 64, now, now]]
    for year, month, day in [(1969, 12, 31), (1994, 11, 6), (2024, 2, 29), (2024, 3, 1), (2074, 3, 1)]:
        value = dt.datetime(year, month, day, 12, tzinfo=dt.timezone.utc)
        for pattern in ["%a, %d %b %Y %H:%M:%S GMT", "%A, %d-%b-%y %H:%M:%S GMT", "%a %b %e %H:%M:%S %Y"]:
            if year == 1969 and "%y" in pattern:
                continue
            cases.append([value.strftime(pattern), now, max(now, value.timestamp())])
    # One second beyond the rolling fifty-year boundary resolves to the previous century.
    cases.append(["Friday, 01-Mar-74 12:00:01 GMT", now, now])
    cases.append(
        [
            "Friday, 01-Jan-00 00:00:00 GMT",
            dt.datetime(2090, 1, 1, tzinfo=dt.timezone.utc).timestamp(),
            dt.datetime(2100, 1, 1, tzinfo=dt.timezone.utc).timestamp(),
        ]
    )
    cases += [
        ["Sat, 31 Dec 2016 23:59:60 GMT", 0.0, 1483228800.0],
        ["Sun Nov 06 08:49:37 1994", 0.0, 784111777.0],
        ["Fri, 31 Dec 9999 23:59:59 GMT", now, 253402300799.0],
        ["253402300799", 0.0, 253402300799.0],
    ]
    # Sweep month ends, leap days and weekdays without relying on the adapter as the oracle.
    start = dt.datetime(2024, 1, 1, tzinfo=dt.timezone.utc)
    for offset in range(0, 1462, 7):
        value = start + dt.timedelta(days=offset, seconds=offset)
        cases.append([value.strftime("%a, %d %b %Y %H:%M:%S GMT"), 0.0, value.timestamp()])
    (tmp_path / "dates.json").write_text(json.dumps(cases))
    output = parity(
        tmp_path,
        """from py2rust.stdlib import Json, json_array, json_loads, json_float, json_string, read_text, http_retry_after
def run() -> None:
    cases: list[Json] = json_array(json_loads(read_text("dates.json")))
    for case in cases:
        assert http_retry_after(json_string(case[0]), json_float(case[1])) == json_float(case[2])
    print(len(cases))
    return
if __name__ == "__main__":
    run()
""",
    )
    assert int(output) == len(cases)
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def test_retry_after_rejects_invalid_headers_and_times(tmp_path: Path) -> None:
    cases = [
        [value, 0.0]
        for value in [
            "",
            "  ",
            "-1",
            "+2",
            "1.5",
            "1e2",
            "١٢",
            "1\n",
            "1\r",
            "0" * 65,
            "9" * 64,
            "Sun, 06 Nov 1994 08:49:37 UTC",
            "Sun, 06 Nov 1994 08:49:37 +0000",
            "sun, 06 Nov 1994 08:49:37 GMT",
            "Mon, 06 Nov 1994 08:49:37 GMT",
            "Sun, 06 Xxx 1994 08:49:37 GMT",
            "Sun, 06 Nov 1994 24:49:37 GMT",
            "Sun, 06 Nov 1994 08:60:37 GMT",
            "Sun, 06 Nov 1994 08:49:61 GMT",
            "Sun, 31 Feb 1994 08:49:37 GMT",
            "Sun, 6 Nov 1994 08:49:37 GMT",
            "Sun, 06 Nov 0000 08:49:37 GMT",
            "Fri, 31 Dec 9999 23:59:60 GMT",
            "Sun,  06 Nov 1994 08:49:37 GMT",
            "Sun, 06 Nov 1994 08:49:37 GMT, 120",
        ]
    ]
    cases += [["1", 253402300799.0], ["0", -1.0], ["0", 253402300800.0]]
    (tmp_path / "invalid.json").write_text(json.dumps(cases))
    output = parity(
        tmp_path,
        """from py2rust.stdlib import Json, json_array, json_loads, json_float, json_string, read_text, http_retry_after
def run() -> None:
    cases: list[Json] = json_array(json_loads(read_text("invalid.json")))
    errors: int = 0
    for case in cases:
        try:
            http_retry_after(json_string(case[0]), json_float(case[1]))
        except Exception:
            errors = errors + 1
    assert errors == len(cases)
    print(errors)
    return
if __name__ == "__main__":
    run()
""",
    )
    assert int(output) == len(cases)
    return  # noqa: PLR1711 - explicit return required by repository guidelines
