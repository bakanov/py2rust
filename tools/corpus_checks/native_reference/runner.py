"""Explicit CPython comparison entry point; Rust imports .rs files directly."""

import runpy
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from corpus_checks.native_reference import (
    native_numbers,
    native_text,
    native_values,
)


def main() -> None:
    entry = Path(sys.argv[1]).resolve()
    sys.path.insert(0, str(entry.parent))
    sys.modules.update(native_numbers=native_numbers, native_text=native_text, native_values=native_values)
    sys.argv = sys.argv[1:]
    runpy.run_path(str(entry), run_name="__main__")
    return  # noqa: PLR1711 - explicit repository convention


if __name__ == "__main__":
    main()
