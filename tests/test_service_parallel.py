"""Ordered results, value isolation, worker bounds and guaranteed error-path joins."""

from pathlib import Path

import pytest
from py2rust.compiler.service import ServiceCompiler, ServiceError

from .test_services import parity


def test_parallel_order_and_value_isolation(tmp_path: Path) -> None:
    output = parity(
        tmp_path,
        """from py2rust.stdlib import Json, json_int, json_float, json_equal, parallel_map, sleep
def transform(item: Json) -> Json:
    value: int = json_int(item["value"])
    sleep(json_float(4 - value) * 0.01)
    nested: Json = item["nested"]
    nested["value"] = value * value
    item["nested"] = nested
    return item
def run() -> None:
    values: list[Json] = []
    for index in range(4):
        values.append({"value": index, "nested": {"value": -1}})
    results: list[Json] = parallel_map(transform, values, 3)
    for index in range(4):
        assert json_int(results[index]["value"]) == index
        assert json_int(results[index]["nested"]["value"]) == index * index
        assert json_int(values[index]["nested"]["value"]) == -1
    assert json_equal(parallel_map(transform, [], 3), [])
    print("ordered isolated results")
    return
if __name__ == "__main__":
    run()
""",
    )
    assert output == "ordered isolated results\n"
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def test_parallel_errors_join_all_callbacks(tmp_path: Path) -> None:
    output = parity(
        tmp_path,
        """from py2rust.stdlib import Json, json_int, parallel_map, sleep, write_text, path_exists, remove_file
def work(item: Json) -> Json:
    number: int = json_int(item)
    if number == 1:
        sleep(0.06)
    if number == 4:
        sleep(0.10)
    write_text("done-" + str(number), "complete")
    assert number != 1 and number != 3, "failed-" + str(number)
    return number
def run() -> None:
    caught: bool = False
    try:
        parallel_map(work, [0, 1, 2, 3, 4, 5], 3)
    except Exception as error:
        assert str(error) == "failed-1"
        caught = True
    assert caught
    for index in range(6):
        assert path_exists("done-" + str(index))
        remove_file("done-" + str(index))
    print("all workers joined before error")
    return
if __name__ == "__main__":
    run()
""",
    )
    assert output == "all workers joined before error\n"
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def test_parallel_worker_and_item_limits(tmp_path: Path) -> None:
    output = parity(
        tmp_path,
        """from py2rust.stdlib import Json, parallel_map
def identity(item: Json) -> Json:
    return item
def run() -> None:
    errors: int = 0
    for workers in [0, -1, 65]:
        try:
            parallel_map(identity, [], workers)
        except Exception:
            errors = errors + 1
    large: list[Json] = []
    for number in range(10001):
        large.append(number)
    try:
        parallel_map(identity, large, 2)
    except Exception:
        errors = errors + 1
    assert errors == 4
    assert len(parallel_map(identity, [1, 2, 3], 64)) == 3
    print("parallel limits checked")
    return
if __name__ == "__main__":
    run()
""",
    )
    assert output == "parallel limits checked\n"
    return  # noqa: PLR1711 - explicit return required by repository guidelines


@pytest.mark.parametrize("callback", ["wrong", "lambda value: value"])
def test_parallel_callback_signature_is_checked(callback: str) -> None:
    source = f"""from py2rust.stdlib import Json, parallel_map
def wrong(value: int) -> int:
    return value
def run() -> None:
    values: list[Json] = parallel_map({callback}, [1], 2)
    return
if __name__ == "__main__":
    run()
"""
    with pytest.raises(ServiceError, match="parallel"):
        ServiceCompiler().compile(source)
    return  # noqa: PLR1711 - explicit return required by repository guidelines
