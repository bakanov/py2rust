# OpenCiv3 native console campaign

This generated Cargo project runs a Godot-free OpenCiv3 campaign using the real
rules, city-founding, production, trade-network, AI-turn, and economic-round
engine code. It founds Rome explicitly and then autoplays ten turns. No Python
interpreter is required by the executable.

This is not yet full console parity. Autonomous settler expansion and some map,
production, and economic details still differ from Python. The verified native
result grows Rome to population 2 and discovers Pottery. The command-line parser,
BIQ/save loading, interactive terminal streams, and Godot frontend are outside
this generated entry point.

## Build and run

Install Rust 1.83 or newer. Set `CIV3_ROOT` to the OpenCiv3 `C7` directory, then
build from this directory:

```bash
export CIV3_ROOT="$HOME/experimental/OpenCiv3-Development/OpenCiv3-Development/C7"
cargo build --release --locked
```

Run from `CIV3_ROOT`, because game data is read through relative paths:

```bash
cd "$CIV3_ROOT"
"$OLDPWD/target/release/py2rust-service"
```

The final native statistics are:

```text
Turn: 10
Civilization: Rome
Treasury: 10
Research beakers: 40, turns: 8, science: 10
Known technologies: 1
Units: 7
Cities: 1
Rome: population 2, food 2, shields 3
Food stored: 0, owned tiles: 9
Worked tile: 51,49
Worked tile: 49,51
```

The verified runtime is about 4.7 seconds on the development machine. Before
context-sensitive borrowing of cached module constants, the same campaign took
about 155 seconds.

## Regenerate

From the py2rust repository root with its development environment installed:

```bash
export PYTHONPATH="$PWD"
python - <<'PY'
from pathlib import Path
from py2rust.compiler.pipeline import compile_loaded_project
from py2rust.compiler.project import Project
from py2rust.compiler.project_output import write_service_project

root = Path.home() / "experimental/OpenCiv3-Development/OpenCiv3-Development/C7"
code = compile_loaded_project(
    Project(root, "civ3_console/native_campaign.py"),
    packaged=True,
    python_scope=True,
)
write_service_project(code, Path("examples/projects/openciv3_console_rust"))
PY
```

Do not maintain fixes by editing generated Rust. Change the transpiler or the
small native Python entry point and regenerate this directory.
