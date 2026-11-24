"""Portable UTC conversion and formatting, including pre-epoch and distant dates."""

import datetime as dt
import random
from pathlib import Path

import pytest

from .test_services import run


@pytest.mark.parametrize("engine", ["python", "rust"])
def test_unix_datetime_and_portable_format_vectors(tmp_path: Path, engine: str) -> None:
    rng = random.Random(3906)
    values = [-62135596800, -2208988800, -1, 0, 1, 951782400, 2147483647, 2147483648, 253402300799]
    values += [rng.randint(-62135596800, 253402300799) for _ in range(1000)]
    source = """
from py2rust.stdlib import DateTime, datetime_from_unix, datetime_format, datetime_iso
def check() -> None:
    values: list[int] = VALUES
    for number in values:
        value: DateTime = datetime_from_unix(number)
        print(datetime_iso(value))
        print(datetime_format(value, "%Y-%m-%d %H:%M:%S.%f %z %Z %j %a %A %b %B %w %u %% 世界"))
    return
if __name__ == "__main__":
    check()
""".replace("VALUES", repr(values))
    result = run(tmp_path, source, engine)
    assert result.returncode == 0, result.stderr
    expected = []
    epoch = dt.datetime(1970, 1, 1, tzinfo=dt.timezone.utc)
    for number in values:
        value = epoch + dt.timedelta(seconds=number)
        expected.append(value.isoformat(timespec="microseconds"))
        # Python/libc may leave years below 1000 unpadded: the portable API requires four digits.
        expected.append(f"{value.year:04d}" + value.strftime("-%m-%d %H:%M:%S.%f %z %Z %j %a %A %b %B %w %u %% 世界"))
    assert result.stdout.splitlines() == expected
    return  # noqa: PLR1711 - explicit return required by repository guidelines


@pytest.mark.parametrize("engine", ["python", "rust"])
def test_datetime_offsets_literals_and_recoverable_limits(tmp_path: Path, engine: str) -> None:
    result = run(
        tmp_path,
        r"""
from py2rust.stdlib import DateTime, datetime_from_unix, datetime_parse, datetime_format
def check() -> None:
    value: DateTime = datetime_parse("2000-03-01T00:15:06.000123+01:00")
    assert datetime_format(value, "%Y/%m/%d %H:%M:%S.%f %j %a %A") == "2000/02/29 23:15:06.000123 060 Tue Tuesday"
    assert datetime_format(value, "") == ""
    assert datetime_format(value, "%%%Y") == "%2000"
    assert datetime_format(value, "日付\n%Y\t%%") == "日付\n2000\t%"
    pattern: str = ""
    for attempt in range(512):
        pattern = pattern + "é"
    assert datetime_format(value, pattern) == pattern
    errors: int = 0
    for pattern_bad in ["%", "%Q", "%c", "%s", "%:z", "%EY", "%_d", "%4Y", "%é", pattern + "x"]:
        try:
            ignored: str = datetime_format(value, pattern_bad)
        except Exception:
            errors = errors + 1
    for timestamp in [-62135596801, 253402300800, -9223372036854775808, 9223372036854775807]:
        try:
            ignored_date: DateTime = datetime_from_unix(timestamp)
        except Exception:
            errors = errors + 1
    print(errors)
    return
if __name__ == "__main__":
    check()
""",
        engine,
    )
    assert result.returncode == 0 and result.stdout == "14\n", result.stderr
    return  # noqa: PLR1711 - explicit return required by repository guidelines
