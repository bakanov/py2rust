"""CRC-32 vectors, independent C-library comparisons, incremental seeds and project imports."""

import binascii
import json
import random
from pathlib import Path

import pytest
from py2rust.compiler.service import ServiceCompiler, ServiceError

from py2rust.stdlib import crc32

from .test_project import run_project, sources
from .test_services import parity


def test_crc32_vectors_seeds_and_evaluation_order(tmp_path: Path) -> None:
    output = parity(
        tmp_path,
        """
import zlib
import binascii
from py2rust.stdlib import crc32

def data() -> bytes:
    print("data first")
    return b"123456789"

def seed() -> int:
    print("seed second")
    return 0

def check() -> None:
    assert zlib.crc32(b"") == 0
    assert zlib.crc32(b"123456789") == 3421780262
    assert binascii.crc32(b"IEND") == 2923585666
    assert crc32(bytearray(b"123456789")) == 3421780262
    for value in [-9223372036854775808, -4294967297, -4294967296, -1, 0, 1, 4294967295, 4294967296, 9223372036854775807]:
        assert crc32(b"", value) == (value & 4294967295)
        assert zlib.crc32(b"abc", value) == binascii.crc32(b"abc", value & 4294967295)
        assert crc32(b"abc", value) == zlib.crc32(b"abc", value)
    assert zlib.crc32(data(), seed()) == 3421780262
    message: bytes = b"Every split preserves the previous checksum: \\x00\\xff PNG!"
    for index in range(len(message)+1):
        assert crc32(message[index:], crc32(message[:index])) == crc32(message)
    print("CRC vectors and every split passed")
    return
if __name__ == "__main__":
    check()
""",
    )
    assert output == "data first\nseed second\nCRC vectors and every split passed\n"
    return  # noqa: PLR1711


def test_crc32_generated_offsets_chunks_and_large_buffer(tmp_path: Path) -> None:
    rng = random.Random(111)
    data = bytes(range(256)) * 256 + rng.randbytes(65536)
    (tmp_path / "data.bin").write_bytes(data)
    rows = []
    for index in range(512):
        offset = rng.randrange(len(data))
        size = min(rng.randrange(4097), len(data) - offset)
        seed = rng.randrange(-(2**63), 2**63)
        rows.append([offset, size, seed, binascii.crc32(data[offset : offset + size], seed)])
    (tmp_path / "vectors.json").write_text(json.dumps(rows))
    large = bytes(range(256)) * 65536
    (tmp_path / "large.bin").write_bytes(large)
    (tmp_path / "large-crc.json").write_text(json.dumps(binascii.crc32(large)))
    parity(
        tmp_path,
        """
import zlib
from py2rust.stdlib import Json, crc32, json_loads, json_array, json_int, read_bytes, read_text

def check() -> None:
    data: bytes = read_bytes("data.bin")
    rows: list[Json] = json_array(json_loads(read_text("vectors.json")))
    for row in rows:
        offset: int = json_int(row[0])
        size: int = json_int(row[1])
        seed: int = json_int(row[2])
        block: bytes = data[offset:offset+size]
        assert zlib.crc32(block, seed) == json_int(row[3])
        assert crc32(bytearray(block), seed) == json_int(row[3])
    large: bytes = read_bytes("large.bin")
    checksum: int = 0
    for offset in range(0, len(large), 65521):
        checksum = crc32(large[offset:offset+65521], checksum)
    assert checksum == json_int(json_loads(read_text("large-crc.json")))
    assert zlib.crc32(large) == checksum
    print("512 seeded vectors and 16 MiB incremental CRC passed")
    return
if __name__ == "__main__":
    check()
""",
    )
    return  # noqa: PLR1711


def test_crc32_whole_project_imports(tmp_path: Path) -> None:
    root = sources(
        tmp_path,
        {
            "main.py": """from checks import checksum
from py2rust.stdlib import crc32 as library_crc

def main() -> None:
    assert checksum(b"123456789") == library_crc(b"123456789")
    assert checksum(b"123456789") == 3421780262
    print("linked native CRC")
    return
if __name__ == "__main__":
    main()
""",
            "checks.py": """import zlib as compression
import binascii as binary

def checksum(data: bytes) -> int:
    assert compression.crc32(data) == binary.crc32(data, 0)
    return compression.crc32(data)
""",
        },
    )
    result = run_project(root, tmp_path / "rust")
    assert result.returncode == 0 and result.stdout == "linked native CRC\n" and not result.stderr
    return  # noqa: PLR1711


@pytest.mark.parametrize("module", ["zlib", "binascii"])
def test_local_checksum_module_precedes_stdlib(tmp_path: Path, module: str) -> None:
    root = sources(
        tmp_path,
        {
            "main.py": f"""import {module}
def main() -> None:
    assert {module}.crc32(b"local") == 42
    return
if __name__ == "__main__":
    main()
""",
            module + ".py": "def crc32(data: bytes) -> int:\n    return 42\n",
        },
    )
    result = run_project(root, tmp_path / "rust")
    assert result.returncode == 0 and not result.stdout and not result.stderr
    return  # noqa: PLR1711


@pytest.mark.parametrize(
    "call",
    [
        "zlib.crc32()",
        'zlib.crc32(b"", 0, 0)',
        'zlib.crc32("text")',
        "zlib.crc32([1])",
        'zlib.crc32(b"", True)',
        'zlib.crc32(b"", 1.0)',
        'zlib.crc32(b"", "0")',
        'zlib.crc32(data=b"data")',
        'zlib.adler32(b"data")',
        'binascii.crc_hqx(b"data", 0)',
    ],
)
def test_crc32_rejects_unsupported_calls(call: str) -> None:
    with pytest.raises(ServiceError):
        ServiceCompiler().compile("import zlib\nimport binascii\ndef main() -> None:\n    " + call + "\n    return\n")
    return  # noqa: PLR1711


@pytest.mark.parametrize("data,seed", [("x", 0), ([1], 0), (b"", True), (b"", 1.0), (b"", 2**63), (b"", -(2**63) - 1)])
def test_crc32_reference_contract_rejects_bad_values(data: object, seed: object) -> None:
    with pytest.raises(ValueError, match="CRC-32 requires"):
        crc32(data, seed)
    return  # noqa: PLR1711
