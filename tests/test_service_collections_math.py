"""Collection clearing and bounded ceiling for protocol retry calculations."""

import json
import shutil
import subprocess
from pathlib import Path

import pytest
from py2rust.compiler.service import ServiceCompiler, ServiceError

from .test_services import parity, program, run


def test_indexed_reads_and_tuple_length_evaluation(tmp_path: Path) -> None:
    output = parity(
        tmp_path,
        """
from py2rust.stdlib import Json, json_int
def source() -> list[str]:
    print("source")
    return ["hello", "世界"]
def index() -> int:
    print("index")
    return -1
def pair() -> tuple[str, str]:
    print("tuple")
    return ("a", "b")
def check() -> None:
    assert source()[index()] == "世界"
    values: list[str] = source()
    assert values[index()] == "世界"
    assert values[0:1] == ["hello"]
    mapping: dict[str, list[int]] = {"a": [1]}
    copied: list[int] = mapping["a"].copy()
    copied.append(2)
    assert mapping["a"] == [1]
    data: Json = {"a": 7}
    assert json_int(data["a"]) == 7
    text: str = "世界😀"
    assert text[-1] == "😀" and text[1:] == "界😀" and len(text) == 3
    raw: bytes = text.encode()
    assert raw[-1] == 128 and len(raw[:3]) == 3
    assert len(pair()) == 2
    named: tuple[str, str] = pair()
    assert len(named) == 2 and named[1] == "b"
    return
if __name__ == "__main__":
    check()
""",
    )
    assert output == "source\nindex\nsource\nindex\ntuple\ntuple\n"
    owned = run(
        tmp_path,
        """
from py2rust.stdlib import Json, json_int
def check() -> None:
    outer: list[list[int]] = [[1]]
    item: list[int] = outer[0]
    item[0] = 2
    assert outer[0][0] == 1
    mapping: dict[str, list[int]] = {"a": [3]}
    entry: list[int] = mapping["a"]
    entry.append(4)
    assert len(mapping["a"]) == 1
    pair: tuple[list[int], list[int]] = ([5], [6])
    field: list[int] = pair[0]
    field.clear()
    assert pair[0][0] == 5
    state: Json = {"nested": {"value": 7}}
    child: Json = state["nested"]
    child["value"] = 8
    assert json_int(state["nested"]["value"]) == 7
    return
if __name__ == "__main__":
    check()
""",
        "rust",
        "owned_reads",
    )
    assert owned.returncode == 0, owned.stderr
    return  # noqa: PLR1711 - explicit return required by repository guidelines


@pytest.mark.parametrize("kind", ["list", "dict"])
def test_named_lookup_does_not_duplicate_large_container(tmp_path: Path, kind: str) -> None:
    limiter = shutil.which("prlimit")
    assert limiter, "this bounded-memory regression requires Linux prlimit"
    (tmp_path / "block.txt").write_text("x" * 1024)
    declaration = "items: list[str] = []" if kind == "list" else "items: dict[int, str] = {}"
    append = "items.append(block)" if kind == "list" else "items[index] = block"
    source = f"""
from py2rust.stdlib import read_text
def check() -> None:
    block: str = read_text("block.txt")
    {declaration}
    for index in range(80000):
        {append}
    assert len(items) == 80000
    selected: str = items[79999]
    assert len(selected) == 1024
    assert items[0][0] == "x"
    print("large lookup passed")
    return
if __name__ == "__main__":
    check()
"""
    command = program(tmp_path, source, "rust", "bounded_lookup")
    result = subprocess.run(
        [limiter, "--as=134217728", "--", *command],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    assert result.returncode == 0 and result.stdout == "large lookup passed\n", result.stderr
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def test_conditional_expressions_evaluate_only_the_selected_branch(tmp_path: Path) -> None:
    output = parity(
        tmp_path,
        """
from dataclasses import dataclass
from py2rust.stdlib import Json, pretty
@dataclass
class Label:
    name: str
def condition() -> bool:
    print("condition")
    return False
def chosen() -> str:
    print("chosen")
    return "世界"
def forbidden() -> str:
    assert False, "unchosen branch evaluated"
    return ""
def check() -> None:
    text: str = forbidden() if condition() else chosen()
    assert text == "世界"
    empty: list[int] = [] if True else [1]
    assert len(empty) == 0
    nested: int = (4 if False else 7) if True else 9
    assert nested == 7
    decimal: float = 3 if True else 4.5
    assert decimal == 3.0
    value: Json = {"ok": True} if True else None
    print(pretty(value))
    label: Label = Label("first") if True else Label("second")
    assert label.name == "first"
    return
if __name__ == "__main__":
    check()
""",
    )
    assert output.startswith("condition\nchosen\n")
    return  # noqa: PLR1711 - explicit return required by repository guidelines


@pytest.mark.parametrize("expression", ['1 if True else "two"', "1 if 1 else 2"])
def test_conditional_expressions_reject_incompatible_types(expression: str) -> None:
    with pytest.raises(ServiceError, match="expected"):
        ServiceCompiler().compile(
            "def check() -> int:\n    return " + expression + '\nif __name__ == "__main__":\n    check()\n'
        )
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def test_homogeneous_tuple_iteration_evaluates_once(tmp_path: Path) -> None:
    assert parity(
        tmp_path,
        """
from py2rust.stdlib import pretty
def values() -> tuple[str, str, str]:
    print("tuple evaluated")
    return ("a", "世界", "c")
def check() -> None:
    result: list[str] = []
    for value in values():
        if value == "a":
            continue
        value = value + "!"
        result.append(value)
        if value == "世界!":
            break
    assert result == ["世界!"]
    original: tuple[list[int], list[int]] = ([1], [2])
    for item in original:
        copied: list[int] = item.copy()
        copied.append(3)
        print(pretty(copied))
    assert original[0] == [1] and original[1] == [2]
    for single in (7,):
        assert single == 7
    return
if __name__ == "__main__":
    check()
""",
    ).startswith("tuple evaluated\n")
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def test_tuple_iteration_preserves_resource_aliases_and_records(tmp_path: Path) -> None:
    parity(
        tmp_path,
        """
from dataclasses import dataclass
from py2rust.stdlib import FileHandle, file_open, file_read, file_write, file_seek
@dataclass
class Named:
    name: str
def check() -> None:
    pair: tuple[Named, Named] = (Named("one"), Named("two"))
    for record in pair:
        print(record.name)
    with file_open("data.bin", "w+b") as original:
        handles: tuple[FileHandle, FileHandle] = (original, original)
        for handle in handles:
            file_write(handle, b"x")
        file_seek(original, 0, 0)
        assert file_read(original, 10) == b"xx"
    return
if __name__ == "__main__":
    check()
""",
    )
    return  # noqa: PLR1711 - explicit return required by repository guidelines


@pytest.mark.parametrize(
    "expression, message",
    [("()", "empty collection"), ('(1, "two")', "tuple iteration requires"), ("(1, 2.0)", "tuple iteration requires")],
)
def test_tuple_iteration_rejects_ambiguous_element_types(expression: str, message: str) -> None:
    with pytest.raises(ServiceError, match=message):
        ServiceCompiler().compile(
            "def check() -> None:\n    for value in "
            + expression
            + ':\n        pass\n    return\nif __name__ == "__main__":\n    check()\n'
        )
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def test_list_slicing_bounds_order_and_copies(tmp_path: Path) -> None:
    source = """
def observed(value: int) -> int:
    print(value)
    return value
def values() -> list[str]:
    print("values")
    return ["a", "世界", "c", "d"]
def check() -> None:
    items: list[str] = values()[observed(1):observed(-1)]
    assert items == ["世界", "c"]
    original: list[int] = [0, 1, 2, 3]
    copied: list[int] = original[:]
    copied[0] = 9
    assert original[0] == 0
    for start in [-9223372036854775808, -5, -4, -1, 0, 1, 4, 5, 9223372036854775807]:
        for end in [-9223372036854775808, -5, -4, -1, 0, 1, 4, 5, 9223372036854775807]:
            selected: list[int] = original[start:end]
            for item in selected:
                print(item)
            print("end")
    assert original[2:] == [2, 3] and original[:-2] == [0, 1]
    empty: list[int] = []
    assert len(empty[-10:10]) == 0
    return
if __name__ == "__main__":
    check()
"""
    result = parity(tmp_path, source)
    assert result.startswith("values\n1\n-1\n")
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def test_explicit_numeric_float_conversion(tmp_path: Path) -> None:
    assert (
        parity(
            tmp_path,
            """
def check() -> None:
    assert float(250) * 0.001 == 0.25
    assert float(-9223372036854775808) == -9223372036854775808.0
    assert float(9223372036854775807) == 9223372036854775808.0
    assert float(9007199254740993) == 9007199254740992.0
    assert float(-0.0) == 0.0 and float(1.25) == 1.25
    print("converted")
    return
if __name__ == "__main__":
    check()
""",
        )
        == "converted\n"
    )
    return  # noqa: PLR1711 - explicit return required by repository guidelines


@pytest.mark.parametrize("expression", ["float(True)", "[1, 2][::1]", "[1, 2][::-1]"])
def test_unsupported_conversions_and_slice_steps(expression: str) -> None:
    with pytest.raises(ServiceError, match="float conversion|slice steps"):
        ServiceCompiler().compile(
            "def check() -> None:\n    " + expression + '\n    return\nif __name__ == "__main__":\n    check()\n'
        )
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def test_dictionary_key_iteration_order_and_expression(tmp_path: Path) -> None:
    source = """
def mapping() -> dict[int, str]:
    print("evaluated once")
    return {3: "three", -2: "minus", 0: "zero"}
def run() -> None:
    names: dict[str, int] = {"世界": 1, "second": 2, "last": 3}
    names["second"] = 4
    del names["世界"]
    names["世界"] = 5
    keys: list[str] = []
    for key in names:
        keys.append(key)
        names[key] = names[key] + 10
    assert keys == ["second", "last", "世界"]
    assert names["世界"] == 15
    numbers: list[int] = []
    for number in mapping():
        numbers.append(number)
    assert numbers == [3, -2, 0]
    empty: dict[str, int] = {}
    for unused in empty:
        assert False
    print("dictionary keys passed")
    return
if __name__ == "__main__":
    run()
"""
    assert parity(tmp_path, source) == "evaluated once\ndictionary keys passed\n"
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def test_checked_decimal_strings(tmp_path: Path) -> None:
    source = r"""
from py2rust.stdlib import int_from_decimal
def run() -> None:
    values: list[tuple[str, int]] = [("0", 0), ("-0", 0), ("+00042", 42), ("  -7\t\r\n\v\f", -7),
        ("9223372036854775807", 9223372036854775807), ("-9223372036854775808", -9223372036854775808)]
    for pair in values:
        assert int_from_decimal(pair[0]) == pair[1]
        assert int(pair[0]) == pair[1]
    errors: int = 0
    for value in ["", " ", "+", "--1", "1.0", "1_0", "0x10", "1 2", "١", "１", "\u00a01",
        "9223372036854775808", "-9223372036854775809", "1\x00"]:
        try:
            int_from_decimal(value)
        except Exception:
            errors = errors + 1
    assert errors == 14
    long: str = ""
    for index in range(4096):
        long = long + "0"
    assert int_from_decimal(long) == 0
    try:
        int_from_decimal(long + "0")
    except Exception:
        errors = errors + 1
    assert errors == 15
    print("checked decimal passed")
    return
if __name__ == "__main__":
    run()
"""
    assert parity(tmp_path, source) == "checked decimal passed\n"
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def test_clear_preserves_explicit_copies(tmp_path: Path) -> None:
    source = """
def run() -> None:
    items: list[str] = ["世界", "second"]
    saved_items: list[str] = items.copy()
    items.clear()
    assert len(items) == 0 and saved_items == ["世界", "second"]
    items.append("new")
    entries: dict[str, int] = {"one": 1, "two": 2}
    saved_entries: dict[str, int] = entries.copy()
    entries.clear()
    assert len(entries) == 0 and saved_entries["two"] == 2
    entries["three"] = 3
    names: set[str] = {"a", "b"}
    saved_names: set[str] = names.copy()
    names.clear()
    assert len(names) == 0 and "a" in saved_names
    names.add("c")
    assert "a" not in names and "c" in names
    print("clear passed")
    return
if __name__ == "__main__":
    run()
"""
    assert parity(tmp_path, source) == "clear passed\n"


def test_ceiling_values_and_integer_precision(tmp_path: Path) -> None:
    source = """import math
from py2rust.stdlib import ceil
def run() -> None:
    values: list[tuple[float, int]] = [(0.0, 0), (-0.0, 0), (0.001, 1), (-0.001, 0), (1.0, 1),
        (1.000001, 2), (-1.5, -1), (3.999, 4), (-9223372036854775808.0, -9223372036854775808),
        (9223372036854774784.0, 9223372036854774784)]
    for pair in values:
        assert ceil(pair[0]) == pair[1]
        assert math.ceil(pair[0]) == pair[1]
    assert ceil(9223372036854775807) == 9223372036854775807
    assert math.ceil(9223372036854775807) == 9223372036854775807
    assert ceil(-9223372036854775808) == -9223372036854775808
    print("ceiling passed")
    return
if __name__ == "__main__":
    run()
"""
    assert parity(tmp_path, source) == "ceiling passed\n"


@pytest.mark.parametrize("engine", ["python", "rust"])
def test_ceiling_overflow_is_recoverable(tmp_path: Path, engine: str) -> None:
    source = """from py2rust.stdlib import ceil
def run() -> None:
    failures: int = 0
    for value in [9223372036854775808.0, -9223372036854777856.0, 1e308]:
        try:
            ceil(value)
        except Exception:
            failures = failures + 1
    assert failures == 3
    print("overflow passed")
    return
if __name__ == "__main__":
    run()
"""
    result = run(tmp_path, source, engine)
    assert result.returncode == 0, result.stderr
    assert result.stdout == "overflow passed\n"


def test_set_from_typed_list_evaluates_once_and_copies(tmp_path: Path) -> None:
    output = parity(
        tmp_path,
        """
def source() -> list[str]:
    print("source")
    return ["世界", "a", "世界"]
def check() -> None:
    values: list[str] = source()
    unique: set[str] = set(values)
    unique.add("new")
    assert len(values) == 3 and len(unique) == 3 and "世界" in unique
    assert len(set(source())) == 2
    integers: set[int] = set([1, -2, 1, 0])
    flags: set[bool] = set([True, False, True])
    empty: list[int] = []
    assert len(set(empty)) == 0
    assert len(integers) == 3 and -2 in integers and len(flags) == 2
    return
if __name__ == "__main__":
    check()
""",
    )
    assert output == "source\nsource\n"
    for expression in ["[1.5]", "[[1]]", '"abc"']:
        with pytest.raises(ServiceError, match="set\\(value\\) requires"):
            ServiceCompiler().compile(
                f"def check() -> None:\n    print(len(set({expression})))\nif __name__ == '__main__':\n    check()\n"
            )
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def test_indexed_list_updates_and_nested_reads(tmp_path: Path) -> None:
    output = parity(
        tmp_path,
        """
def index() -> int:
    print("index")
    return -1
def key() -> str:
    print("key")
    return "a"
def value() -> int:
    print("value")
    return 7
def check() -> None:
    groups: list[list[int]] = [[1], [2]]
    groups[index()].append(value())
    assert groups[1][1] == 7 and len(groups[index()]) == 2
    groups[0].extend(groups[0])
    assert groups[0] == [1, 1]
    mapping: dict[str, list[int]] = {"a": [3]}
    mapping[key()].append(value())
    mapping["a"].extend(mapping["a"])
    assert mapping[key()][index()] == 7
    assert mapping["a"] == [3, 7, 3, 7]
    try:
        mapping["missing"].append(value())
    except Exception:
        print("missing before value")
    try:
        groups[999].extend([value()])
    except Exception:
        print("bounds before value")
    deep: dict[str, list[list[int]]] = {"a": [[4, 5]]}
    assert deep[key()][0][index()] == 5
    assert len(deep["a"][0]) == 2
    return
if __name__ == "__main__":
    check()
""",
    )
    assert (
        output == "index\nvalue\nindex\nkey\nvalue\nkey\nindex\nmissing before value\nbounds before value\nkey\nindex\n"
    )
    owned = run(
        tmp_path,
        """
def check() -> None:
    data: list[list[list[int]]] = [[[1]]]
    copied: list[int] = data[0][0]
    copied.append(2)
    assert data[0][0] == [1]
    mapping: dict[str, list[list[int]]] = {"a": [[3]]}
    item: list[int] = mapping["a"][0]
    item[0] = 4
    assert mapping["a"][0][0] == 3
    return
if __name__ == "__main__":
    check()
""",
        "rust",
        "nested_owned",
    )
    assert owned.returncode == 0, owned.stderr
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def test_membership_evaluates_needle_before_container(tmp_path: Path) -> None:
    output = parity(
        tmp_path,
        """
from py2rust.stdlib import Json

def needle() -> str:
    print("needle")
    return "a"
def sequence() -> list[str]:
    print("list")
    return ["a", "b"]
def text() -> str:
    print("str")
    return "abc"
def mapping() -> dict[str, int]:
    print("dict")
    return {"a": 1}
def json_value() -> Json:
    print("json")
    return {"a": 1}
def check() -> None:
    assert needle() in sequence()
    assert not (needle() not in text())
    assert needle() in mapping()
    assert needle() in json_value()
    values: list[int] = [1, 2]
    assert values.pop() not in values
    assert values == [1]
    groups: list[list[str]] = [["a"]]
    assert needle() in groups[0]
    return
if __name__ == "__main__":
    check()
""",
    )
    assert output == "needle\nlist\nneedle\nstr\nneedle\ndict\nneedle\njson\nneedle\n"
    return  # noqa: PLR1711 - explicit return required by repository guidelines


@pytest.mark.parametrize("kind", ["list", "dict"])
def test_nested_operations_do_not_clone_large_members(tmp_path: Path, kind: str) -> None:
    limiter = shutil.which("prlimit")
    assert limiter, "nested collection memory regression requires Linux prlimit"
    (tmp_path / "block.txt").write_text("x" * 1024)
    declaration = "items: list[list[str]] = [[]]" if kind == "list" else 'items: dict[str, list[str]] = {"data": []}'
    member = "items[0]" if kind == "list" else 'items["data"]'
    source = f"""
from py2rust.stdlib import read_text

def check() -> None:
    block: str = read_text("block.txt")
    {declaration}
    for index in range(80000):
        {member}.append(block)
    assert len({member}) == 80000
    assert len({member}[79999]) == 1024
    assert "absent" not in {member}
    {member}.append({member}[0])
    {member}.extend(["last"])
    assert len({member}) == 80002 and {member}[-1] == "last"
    print("nested memory bound passed")
    return
if __name__ == "__main__":
    check()
"""
    command = program(tmp_path, source, "rust", "nested_memory")
    result = subprocess.run(
        [limiter, "--as=134217728", "--", *command],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    assert result.returncode == 0 and result.stdout == "nested memory bound passed\n", result.stderr
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def test_indexed_mutation_rejects_structural_argument_aliasing() -> None:
    for expression in ["items[0].append(items.pop()[0])", "items[0].extend(items.pop())"]:
        source = f"def check() -> None:\n    items: list[list[int]] = [[1], [2]]\n    {expression}\nif __name__ == '__main__':\n    check()\n"
        with pytest.raises(ServiceError, match="cannot mutate its parent collection"):
            ServiceCompiler().compile(source)
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def test_borrowed_json_string_bytes_and_tuple_receivers(tmp_path: Path) -> None:
    output = parity(
        tmp_path,
        """
from py2rust.stdlib import Json, json_int

def index() -> int:
    print("index")
    return 0
def check() -> None:
    objects: list[Json] = [{"nested": {"value": 3}, "values": [4, 5]}]
    assert json_int(objects[index()]["nested"]["value"]) == 3
    assert json_int(objects[0]["values"][-1]) == 5
    assert "nested" in objects[0]
    dictionary: dict[str, Json] = {"a": {"value": 6}}
    assert json_int(dictionary["a"]["value"]) == 6
    strings: list[str] = ["世界😀"]
    assert strings[index()][-1] == "😀" and strings[0][1:] == "界😀"
    data: dict[str, bytes] = {"a": b"abc"}
    assert data["a"][index()] == 97 and data["a"][1:] == b"bc"
    pairs: list[tuple[int, str]] = [(7, "seven")]
    assert pairs[index()][1] == "seven" and len(pairs[0]) == 2
    return
if __name__ == "__main__":
    check()
""",
    )
    assert output == "index\nindex\nindex\nindex\n"
    return  # noqa: PLR1711 - explicit return required by repository guidelines


@pytest.mark.parametrize("engine", ["python", "rust"])
def test_signed_range_steps_are_lazy_and_ordered(tmp_path: Path, engine: str) -> None:
    result = run(
        tmp_path,
        """
from py2rust.stdlib import pretty

def argument(label: str, value: int) -> int:
    print(label)
    return value

def check() -> None:
    values: list[int] = []
    for value in range(argument("start", 7), argument("stop", -8), argument("step", -3)):
        if value == 1:
            continue
        values.append(value)
    for value in range(-7, 8, 3):
        values.append(value)
    for value in range(0, 10, -1):
        assert False
    for value in range(10, 0, 1):
        assert False
    for value in range(9223372036854775806, 9223372036854775807, 9):
        values.append(value)
    for value in range(-9223372036854775807, -9223372036854775808, -9):
        values.append(value)
    for value in range(0, -9223372036854775808, -9223372036854775808):
        values.append(value)
    for value in range(-9223372036854775808, 9223372036854775807, 1):
        values.append(value)
        break
    failed: bool = False
    try:
        for value in range(argument("zero-start", 1), argument("zero-stop", 1), argument("zero-step", 0)):
            assert False
    except Exception:
        failed = True
    assert failed
    print(pretty(values))
    return
if __name__ == "__main__":
    check()
""",
        engine,
    )
    assert result.returncode == 0, result.stderr
    lines = result.stdout.splitlines()
    assert lines[:6] == ["start", "stop", "step", "zero-start", "zero-stop", "zero-step"]
    assert json.loads("\n".join(lines[6:])) == [
        7,
        4,
        -2,
        -5,
        -7,
        -4,
        -1,
        2,
        5,
        9223372036854775806,
        -9223372036854775807,
        0,
        -9223372036854775808,
    ]
    return  # noqa: PLR1711 - explicit return required by repository guidelines


@pytest.mark.parametrize("engine", ["python", "rust"])
def test_dictionary_get_arguments_precede_lookup_and_null_identity(tmp_path: Path, engine: str) -> None:
    result = run(
        tmp_path,
        """
from py2rust.stdlib import Json, json_array, json_loads

def mapping() -> dict[str, int]:
    print("receiver")
    return {"key": 1}

def key() -> str:
    print("key")
    return "key"

def fallback() -> int:
    print("default")
    return 7

def returned_null() -> Json:
    print("null")
    return None

def check() -> None:
    assert mapping().get(key(), fallback()) == 1
    values: dict[str, Json] = {"key": 10}
    # Clearing during default evaluation removes the key before the lookup.
    assert values.get("key", values.clear()) is None
    assert None is returned_null()
    for value in json_array(json_loads('[false,0,1,"",[],{}]')):
        assert value is not None and not (None is value)
    assert values.clear() is None
    assert not (returned_null() is not None)
    return
if __name__ == "__main__":
    check()
""",
        engine,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines() == ["receiver", "key", "default", "null", "null"]
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def test_named_dictionary_get_does_not_copy_the_mapping(tmp_path: Path) -> None:
    (tmp_path / "block").write_text("x" * 1024)
    command = program(
        tmp_path,
        """
from py2rust.stdlib import read_text

def check() -> None:
    block: str = read_text("block")
    values: dict[int, str] = {}
    for index in range(80000):
        values[index] = block
    assert values.get(79999, "missing") == block
    assert values.get(-1, "missing") == "missing"
    print("bounded get")
    return
if __name__ == "__main__":
    check()
""",
        "rust",
        "dictionary_get_memory",
    )
    result = subprocess.run(
        ["/usr/bin/prlimit", "--as=134217728", "--", *command],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    assert result.returncode == 0 and result.stdout == "bounded get\n", result.stderr
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def test_other_identity_comparisons_are_rejected() -> None:
    for expression in ["left is right", "1 is None", "None is not 1"]:
        source = f"""
from py2rust.stdlib import Json

def check() -> None:
    left: Json = None
    right: Json = None
    assert {expression}
    return
if __name__ == "__main__":
    check()
"""
        with pytest.raises(ServiceError, match="identity comparison requires"):
            ServiceCompiler().compile(source)
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def test_dictionary_get_result_keeps_native_owned_semantics(tmp_path: Path) -> None:
    result = run(
        tmp_path,
        """
def check() -> None:
    groups: dict[str, list[int]] = {"x": [1]}
    selected: list[int] = groups.get("x", [])
    selected.append(2)
    assert groups["x"] == [1]
    fallback: list[int] = [3]
    selected = groups.get("missing", fallback)
    selected.append(4)
    assert fallback == [3]
    return
if __name__ == "__main__":
    check()
""",
        "rust",
    )
    assert result.returncode == 0, result.stderr
    return  # noqa: PLR1711 - explicit return required by repository guidelines


@pytest.mark.parametrize("engine", ["python", "rust"])
def test_typed_list_conversions_evaluate_once_and_copy_containers(tmp_path: Path, engine: str) -> None:
    result = run(
        tmp_path,
        """
from py2rust.stdlib import pretty

def mapping() -> dict[str, int]:
    print("dictionary")
    return {"z": 7, "a": 8}

def unique() -> set[int]:
    print("set")
    return {9, -1, 3}

def sequence() -> list[int]:
    print("list")
    return [4, 4, 1]

def check() -> None:
    assert list(mapping()) == ["z", "a"]
    assert sorted(list(unique())) == [-1, 3, 9]
    assert list(sequence()) == [4, 4, 1]
    values: list[int] = [1, 2]
    copied: list[int] = list(values)
    copied.append(3)
    assert values == [1, 2]
    groups: dict[str, set[str]] = {"names": {"😀", "a"}}
    assert sorted(list(groups["names"])) == ["a", "😀"]
    empty_list: list[int] = []
    empty_set: set[int] = set()
    empty_dict: dict[int, str] = {}
    assert len(list(empty_list)) == 0 and len(list(empty_set)) == 0 and len(list(empty_dict)) == 0
    return
if __name__ == "__main__":
    check()
""",
        engine,
    )
    assert result.returncode == 0 and result.stdout == "dictionary\nset\nlist\n", result.stderr
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def test_key_snapshot_does_not_copy_large_dictionary_values(tmp_path: Path) -> None:
    (tmp_path / "block").write_text("x" * 1024)
    command = program(
        tmp_path,
        """
from py2rust.stdlib import read_text

def check() -> None:
    data: str = read_text("block")
    values: dict[int, str] = {}
    for index in range(80000):
        values[index] = data
    keys: list[int] = list(values)
    assert len(keys) == 80000 and keys[79999] == 79999
    values.clear()
    assert keys[0] == 0 and len(keys) == 80000
    print("bounded key snapshot")
    return
if __name__ == "__main__":
    check()
""",
        "rust",
        "dictionary_keys_memory",
    )
    result = subprocess.run(
        ["/usr/bin/prlimit", "--as=134217728", "--", *command],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    assert result.returncode == 0 and result.stdout == "bounded key snapshot\n", result.stderr
    return  # noqa: PLR1711 - explicit return required by repository guidelines
