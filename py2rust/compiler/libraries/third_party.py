"""Reviewed non-standard-library replacements.

A library must have an explicit replacement contract before it can compile.
Importability or a third-party typing stub is not a Rust implementation.
No third-party packages have been migrated to this registry yet.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from . import Replacement

REPLACEMENTS: dict[str, "Replacement"] = {}
