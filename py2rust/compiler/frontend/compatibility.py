"""Check the frontend ABI before importing hooks that subclass mypy visitors."""

from __future__ import annotations

import json
from importlib import import_module
from importlib.machinery import EXTENSION_SUFFIXES
from importlib.resources import files

from .mypy import FrontendError


def ensure_frontend() -> None:
    contract = json.loads(files(__package__).joinpath("mypy-source.json").read_text())
    expected = contract["wheel_version"]
    installation = (
        "Build the reviewed wheel with tools/build_frontend_wheel.py and install "
        "the typed-frontend extra using --find-links; see doc/FRONTEND_MIGRATION.md."
    )
    try:
        version = import_module("mypy.version").__version__
    except ImportError as error:
        raise FrontendError(
            [f"typed frontend requires pure-Python mypy {expected}; mypy could not be loaded", installation]
        ) from error
    if version != expected:
        raise FrontendError([f"typed frontend requires mypy {expected}; found {version}", installation])
    try:
        nodes = import_module("mypy.nodes")
        traverser = import_module("mypy.traverser")
    except ImportError as error:
        raise FrontendError(
            [f"the pinned mypy frontend could not load its visitor modules: {error}", installation]
        ) from error
    for module in (nodes, traverser):
        if str(getattr(module, "__file__", "")).endswith(tuple(EXTENSION_SUFFIXES)):
            raise FrontendError(
                ["typed frontend requires Python visitor classes; compiled mypy modules are unsupported", installation]
            )
    try:
        type("Py2RustVisitorCompatibilityProbe", (traverser.TraverserVisitor,), {})()
    except TypeError as error:
        raise FrontendError(["mypy visitors cannot be subclassed by the typed frontend", installation]) from error
