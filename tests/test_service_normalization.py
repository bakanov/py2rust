"""Unicode normalization forms, composition order and whole-project module bindings."""

import json
import random
import unicodedata
from pathlib import Path

import pytest
from py2rust.compiler.service import ServiceCompiler, ServiceError

from .test_project import run_project, sources
from .test_services import run


@pytest.mark.parametrize("engine", ["python", "rust"])
def test_normalization_against_unicode_reference(tmp_path: Path, engine: str) -> None:
    # All decomposition-bearing Unicode 15.1 scalars, every algorithmic Hangul
    # syllable, and reordered combining sequences exercise more than Latin accents.
    assert unicodedata.unidata_version == "15.1.0", "update the pinned Rust tables and these vectors together"
    values = [chr(point) for point in range(0x110000) if unicodedata.decomposition(chr(point))]
    values.extend(chr(point) for point in range(0xAC00, 0xD7A4))
    values.extend(["", "plain", "a\0é\n", "Jose\u0301", "\u212b", "\ufb03", "\U0001f600", "\u1100\u1161\u11a8"])
    rng = random.Random(48048)
    for _ in range(500):
        values.append(
            rng.choice(["A", "e", "q", "\u03b1", "\u0f40"]) + "".join(rng.choices("\u0301\u0323\u0315\u0300", k=8))
        )
    (tmp_path / "vectors.json").write_text(json.dumps(values, ensure_ascii=False))
    result = run(
        tmp_path,
        """
import unicodedata
from py2rust.stdlib import Json, json_loads, json_array, json_string, json_dumps, read_text, unicode_normalize
def check() -> None:
    values: list[Json] = json_array(json_loads(read_text("vectors.json")))
    for value in values:
        text: str = json_string(value)
        for form in ["NFC", "NFD", "NFKC", "NFKD"]:
            normalized: str = unicode_normalize(form, text)
            assert normalized == unicodedata.normalize(form, text)
            assert unicode_normalize(form, normalized) == normalized
            print(json_dumps(normalized))
    return
if __name__ == "__main__":
    check()
""",
        engine,
    )
    assert result.returncode == 0, result.stderr
    actual = [json.loads(line) for line in result.stdout.splitlines()]
    expected = [unicodedata.normalize(form, value) for value in values for form in ["NFC", "NFD", "NFKC", "NFKD"]]
    assert actual == expected
    return  # noqa: PLR1711


@pytest.mark.parametrize("engine", ["python", "rust"])
def test_normalization_evaluation_and_invalid_forms(tmp_path: Path, engine: str) -> None:
    result = run(
        tmp_path,
        """
import unicodedata
from py2rust.stdlib import unicode_normalize
def observed(label: str, value: str) -> str:
    print(label)
    return value
def check() -> None:
    assert unicode_normalize(observed("form", "NFC"), observed("text", "e\\u0301")) == "é"
    for bad in ["", "nfc", " NFC", "NFC ", "NFK", "NFC\\0", "ＮＦＣ"]:
        assert unicode_normalize(bad, "") == ""
        assert unicodedata.normalize(bad, "") == ""
        try:
            ignored: str = unicode_normalize(observed("bad form", bad), observed("bad text", "x"))
        except Exception as error:
            print(str(error))
    return
if __name__ == "__main__":
    check()
""",
        engine,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines() == ["form", "text", *(["bad form", "bad text", "invalid normalization form"] * 7)]
    return  # noqa: PLR1711


@pytest.mark.parametrize(
    "call", ['unicode_normalize("NFC", 1)', 'unicode_normalize(1, "x")', 'unicode_normalize("NFC")']
)
def test_normalization_rejects_unsupported_arguments(call: str) -> None:
    with pytest.raises(ServiceError) as error:
        ServiceCompiler().compile(
            "from py2rust.stdlib import unicode_normalize\ndef check() -> None:\n    "
            + call
            + "\n    return\nif __name__ == '__main__':\n    check()\n"
        )
    assert error.value.lineno == 3
    return  # noqa: PLR1711


@pytest.mark.parametrize("extension", ["py", "rs"])
def test_local_unicode_module_precedes_standard_fallback(tmp_path: Path, extension: str) -> None:
    implementation = (
        'def normalize(form: str, text: str) -> str:\n    return "local:" + form + text\n'
        if extension == "py"
        else 'pub fn normalize(form: String, text: String) -> String { format!("local:{}{}", form, text) }\n'
    )
    root = sources(
        tmp_path,
        {
            "main.py": 'import unicodedata\ndef main() -> None:\n    print(unicodedata.normalize("NFC", "x"))\n    return\nif __name__ == "__main__":\n    main()\n',
            "unicodedata." + extension: implementation,
        },
    )
    result = run_project(root, tmp_path / "rust")
    assert result.returncode == 0 and result.stdout == "local:NFCx\n", result.stderr
    return  # noqa: PLR1711
