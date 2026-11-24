"""Exact timestamp microseconds through offsets, negative epochs and the full supported calendar."""

import datetime as dt
import json
import random
from pathlib import Path

import pytest

from .test_services import parity, run


@pytest.mark.parametrize("engine", ["python", "rust"])
def test_datetime_microseconds_are_exact(tmp_path: Path, engine: str) -> None:
    rng = random.Random(105105)
    epoch = dt.datetime(1970, 1, 1, tzinfo=dt.timezone.utc)
    points = [-62135596800000000, -1, 0, 1, 999999, 1000000, 253402300799999999]
    points += [rng.randrange(-62135596800000000, 253402300800000000) for _ in range(1000)]
    rows = [(epoch + dt.timedelta(microseconds=value)).isoformat(timespec="microseconds") for value in points]
    for text in ["1970-01-01T05:00:00.000001+05:00", "1969-12-31T18:59:59.999999-05:00", "2000-02-29T00:00:00Z"]:
        delta = dt.datetime.fromisoformat(text) - epoch
        rows.append(text)
        points.append((delta.days * 86400 + delta.seconds) * 1000000 + delta.microseconds)
    (tmp_path / "times.json").write_text(json.dumps(rows))
    result = run(
        tmp_path,
        """
from py2rust.stdlib import json_array, json_string, json_loads, read_text, datetime_parse, datetime_unix_microseconds
def check() -> None:
    for row in json_array(json_loads(read_text("times.json"))):
        print(datetime_unix_microseconds(datetime_parse(json_string(row))))
    return
if __name__ == "__main__":
    check()
""",
        engine,
    )
    assert result.returncode == 0 and not result.stderr, result.stderr
    assert [int(line) for line in result.stdout.splitlines()] == points
    return  # noqa: PLR1711


def test_datetime_microseconds_evaluate_once_and_preserve_integer_seconds(tmp_path: Path) -> None:
    output = parity(
        tmp_path,
        """
from py2rust.stdlib import DateTime, datetime_parse, datetime_from_unix, datetime_unix_microseconds
def observed() -> DateTime:
    print("called")
    return datetime_parse("1969-12-31T23:59:59.999999Z")
def check() -> None:
    assert datetime_unix_microseconds(observed()) == -1
    for value in [-62135596800, -1, 0, 1, 253402300799]:
        assert datetime_unix_microseconds(datetime_from_unix(value)) == value * 1000000
    print("exact")
    return
if __name__ == "__main__":
    check()
""",
    )
    assert output == "called\nexact\n"
    return  # noqa: PLR1711
