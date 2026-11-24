"""Hand-labeled byte-level header fixtures; no application imports."""

from __future__ import annotations

POLICY = {"year": 2026, "owners": ["Example Team", "Équipe 世界"], "licenses": ["MIT", "Apache-2.0"]}


def canonical(
    style: str = "hash",
    years: str = "2026",
    owner: str = "Example Team",
    license_name: str = "MIT",
    newline: bytes = b"\n",
) -> bytes:
    marker = "#" if style == "hash" else "//"
    return (
        (marker + " Copyright (c) " + years + " " + owner).encode()
        + newline
        + (marker + " SPDX-License-Identifier: " + license_name).encode()
        + newline
    )


def cases() -> dict[str, tuple[bytes, str, list[tuple[str, int]], bytes, bool]]:
    header = canonical()
    code = b'answer = "\xf0\x9f\x98\x80"\n# Copyright belongs to a later comment\n'
    data = {
        "valid.py": (header + code, "hash", [], header + code, False),
        "empty.py": (b"", "hash", [("missing_copyright", 1), ("missing_license", 1)], header, False),
        "missing.py": (code, "hash", [("missing_copyright", 1), ("missing_license", 1)], header + code, False),
        "expired.py": (
            canonical(years="2020-2025") + code,
            "hash",
            [("outdated_year", 1)],
            canonical(years="2020-2026") + code,
            False,
        ),
        "owner.py": (canonical(owner="Unknown") + code, "hash", [("owner", 1)], header + code, False),
        "license.py": (canonical(license_name="Unlisted") + code, "hash", [("license", 2)], header + code, False),
        "future.py": (canonical(years="2027") + code, "hash", [("year_range", 1)], header + code, False),
        "reversed.py": (canonical(years="2025-2020") + code, "hash", [("year_range", 1)], header + code, False),
        "ancient.py": (canonical(years="1899-2026") + code, "hash", [("year_range", 1)], header + code, False),
        "same-year.py": (canonical(years="2026-2026"), "hash", [], canonical(years="2026-2026"), False),
        "comment.py": (
            b"# Description without newline",
            "hash",
            [("missing_copyright", 1), ("missing_license", 1)],
            header + b"# Description without newline",
            False,
        ),
        "shebang.py": (
            b"#!/usr/bin/python3",
            "hash",
            [("missing_copyright", 2), ("missing_license", 2)],
            b"#!/usr/bin/python3\n" + header,
            False,
        ),
        "bom.py": (
            b"\xef\xbb\xbf",
            "hash",
            [("missing_copyright", 1), ("missing_license", 1)],
            b"\xef\xbb\xbf" + header,
            False,
        ),
        "encoding.py": (
            b"\n# coding: utf-8\n" + code,
            "hash",
            [("missing_copyright", 3), ("missing_license", 3)],
            b"\n# coding: utf-8\n" + header + code,
            False,
        ),
        "manual.py": (
            b"# Copyright (c) 2020 Example Team\n# coding: utf-8\n" + code,
            "hash",
            [("header_in_preamble", 1)],
            b"# Copyright (c) 2020 Example Team\n# coding: utf-8\n" + code,
            True,
        ),
        "malformed.py": (
            b"# COPYRIGHT 2020 Example Team\n# spdx-license-identifier: MIT\n" + code,
            "hash",
            [("copyright_format", 1), ("license_format", 2)],
            header + code,
            False,
        ),
        "indented.py": (b"  " + header + code, "hash", [("copyright_format", 1)], header + code, False),
        "copyright-only.py": (b"# Copyright (c) 2026 Example Team", "hash", [("missing_license", 1)], header, False),
        "license-only.py": (
            b"# SPDX-License-Identifier: MIT\n" + code,
            "hash",
            [("missing_copyright", 1), ("license_position", 1)],
            header + code,
            False,
        ),
        "header-at-eof.py": (header[:-1], "hash", [], header[:-1], False),
        "unicode.py": (
            canonical(owner="Équipe 世界", license_name="Apache-2.0") + code,
            "hash",
            [],
            canonical(owner="Équipe 世界", license_name="Apache-2.0") + code,
            False,
        ),
        "slash.rs": (
            canonical("slash", "2024") + b"fn main() {}",
            "slash",
            [("outdated_year", 1)],
            canonical("slash", "2024-2026") + b"fn main() {}",
            False,
        ),
        "wrong-year.py": (canonical(years="20xx") + code, "hash", [("copyright_format", 1)], header + code, False),
    }
    prefix = b"\xef\xbb\xbf#!/usr/bin/python3\r\n# -*- coding: utf-8 -*-\r\n"
    data["bom-crlf.py"] = (
        prefix + canonical(years="2020", newline=b"\r\n") + b"print('x')\r\n",
        "hash",
        [("outdated_year", 3)],
        prefix + canonical(years="2020-2026", newline=b"\r\n") + b"print('x')\r\n",
        False,
    )
    prefix = b"#!/usr/bin/python3\n"
    data["mixed.py"] = (
        prefix + canonical(years="2020", newline=b"\r\n") + b"print('x')\r\n",
        "hash",
        [("outdated_year", 2)],
        prefix + canonical(years="2020-2026") + b"print('x')\r\n",
        False,
    )
    original = b"# Description\n# SPDX-License-Identifier: MIT\n\n# Copyright (c) 2026 Example Team\n" + code
    data["misplaced.py"] = (original, "hash", [("copyright_position", 4)], header + b"# Description\n\n" + code, False)
    original = header + b"# Description\n" + header + code
    data["duplicates.py"] = (
        original,
        "hash",
        [("duplicate_copyright", 4), ("duplicate_license", 5)],
        header + b"# Description\n" + code,
        False,
    )
    return data
