"""Secret-comparison adapters retain byte equality and standard-library spelling."""

from pathlib import Path

from .test_services import parity


def test_secret_byte_comparison(tmp_path: Path) -> None:
    output = parity(
        tmp_path,
        """
import hmac
from py2rust.stdlib import constant_time_equal, random_token, regex_fullmatch
def run() -> None:
    values: list[bytes] = [b"", b"a", b"ab", bytes.fromhex("00ff807f"), "世界😀".encode()]
    comparisons: int = 0
    for left in values:
        for right in values:
            assert constant_time_equal(left, right) == (left == right)
            assert hmac.compare_digest(left, right) == (left == right)
            comparisons = comparisons + 1
    secret: str = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
    for index in range(len(secret)):
        changed: str = secret[0:index] + "x" + secret[index + 1:]
        assert not constant_time_equal(secret.encode(), changed.encode())
    seen: set[str] = set()
    for index in range(20):
        token: str = random_token()
        assert regex_fullmatch("[0-9a-f]{64}", token)
        assert token not in seen
        seen.add(token)
    print(comparisons)
    return
if __name__ == "__main__":
    run()
""",
    )
    assert output == "25\n"
