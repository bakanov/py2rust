"""Explicit library replacement policies, shared by typing and Rust lowering."""

from dataclasses import dataclass

from ..library_contracts import LIBRARY, LOG_LEVELS, MODULE_CALLS
from .web import CALLBACKS


@dataclass(frozen=True)
class Replacement:
    python_name: str
    runtime_name: str
    result: str
    parameters: tuple[str, ...]
    fallible: bool
    family: str
    leading_integers: tuple[int, ...] = ()
    trailing_defaults: tuple[int, ...] = ()


def _replacement(python_name: str, runtime_name: str, family: str) -> Replacement:
    result, parameters, fallible = LIBRARY[runtime_name]
    return Replacement(python_name, runtime_name, result, parameters, fallible, family)


RUNTIME = {f"py2rust.stdlib.{name}": _replacement(f"py2rust.stdlib.{name}", name, "runtime") for name in LIBRARY}
RUNTIME.update(
    {
        f"py2rust.stdlib.{name}": Replacement(f"py2rust.stdlib.{name}", name, "None", args, True, "runtime")
        for name, args in CALLBACKS.items()
    }
)
RUNTIME["py2rust.stdlib.parallel_map"] = Replacement(
    "py2rust.stdlib.parallel_map",
    "parallel_map",
    "list[Json]",
    ("Callable[[Json], Json]", "list[Json]", "int"),
    True,
    "runtime",
)
STANDARD = {name: _replacement(name, target, "standard") for name, target in MODULE_CALLS.items()}

for module in ("py2rust.stdlib", "zlib", "binascii"):
    name = f"{module}.crc32"
    contract = Replacement(
        name,
        "crc32",
        "int",
        ("bytes | bytearray", "int"),
        False,
        "runtime" if module == "py2rust.stdlib" else "standard",
        trailing_defaults=(0,),
    )
    (RUNTIME if module == "py2rust.stdlib" else STANDARD)[name] = contract

STANDARD["builtins.int.from_bytes"] = _replacement("builtins.int.from_bytes", "int_from_bytes", "standard")

# Instance replacements include the receiver as their first runtime argument.
BUILTIN_STATIC = frozenset({"builtins.bytes.fromhex", "builtins.bytearray.fromhex"})

METHODS = {
    ("builtins.int", "to_bytes"): _replacement("builtins.int.to_bytes", "int_to_bytes", "standard"),
    ("builtins.str", "resolve"): _replacement("pathlib.Path.resolve", "path_resolve", "standard"),
    ("builtins.str", "read_text"): _replacement("pathlib.Path.read_text", "read_text", "standard"),
    ("builtins.str", "read_bytes"): _replacement("pathlib.Path.read_bytes", "read_bytes", "standard"),
    ("builtins.str", "write_text"): _replacement("pathlib.Path.write_text", "write_text", "standard"),
    ("builtins.str", "write_bytes"): _replacement("pathlib.Path.write_bytes", "write_bytes", "standard"),
    ("builtins.str", "exists"): _replacement("pathlib.Path.exists", "path_exists", "standard"),
    ("builtins.str", "is_dir"): _replacement("pathlib.Path.is_dir", "path_is_dir", "standard"),
    ("builtins.str", "is_file"): _replacement("pathlib.Path.is_file", "path_is_file", "standard"),
    ("builtins.str", "iterdir"): _replacement("pathlib.Path.iterdir", "path_iterdir", "standard"),
    ("builtins.int", "write"): _replacement("typing.TextIO.write", "stream_write", "standard"),
    ("builtins.int", "flush"): _replacement("typing.TextIO.flush", "stream_flush", "standard"),
    ("builtins.int", "readline"): _replacement("typing.TextIO.readline", "stream_readline", "standard"),
    ("py2rust.stdlib.Random", "random"): _replacement("random.Random.random", "random_random", "standard"),
    ("py2rust.stdlib.Random", "randrange"): Replacement(
        "random.Random.randrange",
        "random_randrange",
        "int",
        ("Random", "int", "int"),
        True,
        "standard",
        trailing_defaults=(0,),
    ),
}

STANDARD.update(
    {
        f"logging.{name.lower()}": Replacement(
            f"logging.{name.lower()}", "log", "None", ("str",), True, "standard", (level,)
        )
        for name, level in LOG_LEVELS.items()
    }
)


def resolve(name: str) -> Replacement | None:
    from .third_party import REPLACEMENTS

    return RUNTIME.get(name) or STANDARD.get(name) or REPLACEMENTS.get(name)


CONSTANTS = {f"logging.{name}": value for name, value in LOG_LEVELS.items()}
CONSTANTS["math.pi"] = 3.141592653589793
CONSTANTS.update({"sys.stdin": 0, "sys.stdout": 1, "sys.stderr": 2})

# Generic mutation intrinsics keep argument types inferred by mypy. They cannot
# use the fixed scalar runtime signature table (heap elements are polymorphic).
INTRINSICS = {
    f"{module}.{operation}": f"heapq.{operation}"
    for module in ("heapq", "_heapq")
    for operation in ("heapify", "heappush", "heappop", "heapreplace", "heappushpop")
}
