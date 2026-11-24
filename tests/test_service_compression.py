"""Independent DEFLATE streams, strict boundaries, corrupt input and ZIP filename codecs."""

import hashlib
import json
import random
import subprocess
import zlib
from pathlib import Path

import pytest
from py2rust.compiler.service import ServiceCompiler, ServiceError

from .test_project import run_project, sources
from .test_services import parity, program

SOURCE = """from py2rust.stdlib import (
    Json, deflate_decompress, json_array, json_bool, json_int, json_loads_unique, json_string,
    read_bytes, read_text, sha256_digest, sha256_new, sha256_update,
)
def run() -> None:
    count: int = 0
    for row in json_array(json_loads_unique(read_text("cases.json"))):
        valid: bool = json_bool(row["valid"])
        succeeded: bool = False
        try:
            output: bytes = deflate_decompress(read_bytes(json_string(row["path"])), json_int(row["maximum"]))
            assert len(output) == json_int(row["length"])
            assert sha256_digest(sha256_update(sha256_new(), output)) == json_string(row["sha256"])
            succeeded = True
        except Exception:
            assert not valid
        assert succeeded == valid
        count = count + 1
    print(count)
    return
if __name__ == "__main__":
    run()
"""


def compressed(data: bytes, level: int = 6, strategy: int = zlib.Z_DEFAULT_STRATEGY) -> bytes:
    encoder = zlib.compressobj(level, zlib.DEFLATED, -15, strategy=strategy)
    return encoder.compress(data) + encoder.flush()


def cases(root: Path, values: list[tuple[bytes, int, bytes | None]]) -> None:
    rows = []
    for index, (data, maximum, expected) in enumerate(values):
        path = str(index) + ".deflate"
        (root / path).write_bytes(data)
        rows.append(
            {
                "path": path,
                "maximum": maximum,
                "valid": expected is not None,
                "length": len(expected) if expected is not None else 0,
                "sha256": hashlib.sha256(expected).hexdigest() if expected is not None else "",
            }
        )
    (root / "cases.json").write_text(json.dumps(rows))
    return  # noqa: PLR1711


def test_deflate_generated_streams_and_strict_boundaries(tmp_path: Path) -> None:
    rng = random.Random(118)
    values = []
    for level in range(10):
        for strategy in [zlib.Z_DEFAULT_STRATEGY, zlib.Z_FILTERED, zlib.Z_HUFFMAN_ONLY, zlib.Z_RLE, zlib.Z_FIXED]:
            data = rng.randbytes(257) + b"network\0" * 1000
            raw = compressed(data, level, strategy)
            values.extend([(raw, len(data), data), (raw, len(data) - 1, None), (raw + b"x", len(data), None)])
    for data in [b"", b"a", b"\x00\xff", bytes(range(256)), b"x" * 65536, b"x" * 65537]:
        raw = compressed(data)
        values.extend([(raw, len(data), data), (raw, len(data) + 1, data), (raw[:-1], len(data), None)])
    for raw in [b"", b"\x07", b"\xff", b"\x01\x00\x00\x00\x00", zlib.compress(b"zlib wrapper")]:
        values.append((raw, 1048576, None))
    small = compressed(b"truncated network payload" * 40)
    values.extend((small[:index], 1000, None) for index in range(len(small)))
    values.append((compressed(b"first") + compressed(b"second"), 100, None))
    cases(tmp_path, values)
    assert parity(tmp_path, SOURCE) == str(len(values)) + "\n"
    return  # noqa: PLR1711


def test_deflate_full_byte_limits_and_bomb_budget(tmp_path: Path) -> None:
    # A complete sequence of stored blocks with exactly 32MiB compressed bytes.
    maximum = 33554432
    blocks = (maximum + 65539) // 65540
    remaining = maximum - 5 * blocks
    plain = b"\0" * remaining
    raw = bytearray()
    for index in range(blocks):
        size = min(remaining, 65535)
        raw.extend(
            bytes([int(index + 1 == blocks)]) + size.to_bytes(2, "little") + (size ^ 65535).to_bytes(2, "little")
        )
        raw.extend(b"\0" * size)
        remaining -= size
    assert not remaining and len(raw) == maximum and zlib.decompress(raw, -15) == plain
    huge = b"x" * 67108864
    encoded = compressed(huge)
    cases(
        tmp_path,
        [
            (bytes(raw), maximum, plain),
            (bytes(raw) + b"x", maximum, None),
            (encoded, len(huge), huge),
            (encoded, len(huge) - 1, None),
            (encoded, 65536, None),
            (compressed(b""), 0, b""),
            (compressed(b"x"), 0, None),
            (compressed(b""), -1, None),
            (compressed(b""), 67108865, None),
        ],
    )
    for engine in ["python", "rust"]:
        result = subprocess.run(
            program(tmp_path, SOURCE, engine, engine),
            cwd=tmp_path,
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        assert result.returncode == 0 and result.stdout == "9\n" and not result.stderr, result
    return  # noqa: PLR1711


def test_cp437_all_bytes_aliases_and_receiver_once(tmp_path: Path) -> None:
    raw = bytes(range(256))
    (tmp_path / "raw.bin").write_bytes(raw)
    (tmp_path / "text.txt").write_text(raw.decode("cp437"), encoding="utf-8")
    assert (
        parity(
            tmp_path,
            """from py2rust.stdlib import read_bytes, read_text

def receiver() -> bytearray:
    print("once")
    return bytearray(read_bytes("raw.bin"))
def run() -> None:
    raw: bytes = read_bytes("raw.bin")
    expected: str = read_text("text.txt")
    assert raw.decode("cp437") == expected
    assert raw.decode("IBM437") == expected
    assert receiver().decode("437") == expected
    assert b"".decode("cp437") == ""
    print("CP437 passed")
    return
if __name__ == "__main__":
    run()
""",
        )
        == "once\nCP437 passed\n"
    )
    return  # noqa: PLR1711


def test_deflate_whole_project_import(tmp_path: Path) -> None:
    root = sources(
        tmp_path,
        {
            "main.py": 'from codec import decode\n\ndef main() -> None:\n    assert decode(b"\\x03\\x00") == b""\n    print("decoded")\n    return\nif __name__ == "__main__":\n    main()\n',
            "codec.py": "from py2rust.stdlib import deflate_decompress\n\ndef decode(data: bytes) -> bytes:\n    return deflate_decompress(data, 100)\n",
        },
    )
    result = run_project(root, tmp_path / "rust")
    assert result.returncode == 0 and result.stdout == "decoded\n" and not result.stderr
    return  # noqa: PLR1711


@pytest.mark.parametrize(
    "expression",
    [
        'deflate_decompress("text", 10)',
        'deflate_decompress(b"", True)',
        'deflate_decompress(b"", 1.0)',
        'deflate_decompress(b"")',
        'deflate_decompress(b"", 1, 2)',
    ],
)
def test_deflate_rejects_wrong_types(expression: str) -> None:
    with pytest.raises(ServiceError):
        ServiceCompiler().compile(
            "from py2rust.stdlib import deflate_decompress\ndef main() -> None:\n    " + expression + "\n    return\n"
        )
    return  # noqa: PLR1711
