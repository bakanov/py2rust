# OpenCiv3 standalone Rust console

This is a generated Cargo project for the reduced OpenCiv3 standalone console.
It contains 104 transpiled Python modules and the py2rust runtime. It does not
contain the Godot interface or the full interactive game. The Python sources and
game data remain in the separate OpenCiv3 checkout.

Do not maintain fixes by editing the generated Rust. Change the Python source or
transpiler and regenerate this directory instead.

## Run

Install Rust 1.83 or newer. Set `CIV3_ROOT` to the `C7` directory of your
OpenCiv3 checkout, then build from this directory:

```bash
export CIV3_ROOT="$HOME/experimental/OpenCiv3-Development/OpenCiv3-Development/C7"
cargo build --release --locked
```

Run the executable **from `CIV3_ROOT`**, because the console reads the checked-out
game data using relative paths:

```bash
cd "$CIV3_ROOT"
"$OLDPWD/target/release/py2rust-service"
```

Alternatively, from any directory, substitute the path to this generated project:

```bash
cd "$CIV3_ROOT"
cargo run --release --locked \
  --manifest-path /path/to/py2rust/examples/projects/openciv3_standalone_rust/Cargo.toml
```

The expected output is:

```text
OpenCiv3 standalone Rust console
Civilizations: 32
Cities: 0
Units: 8
```

At the time this snapshot was verified, native execution took about 155 seconds.
The build uses the locked dependency versions; an offline build additionally
accepts `--offline` if those dependencies are already in the local Cargo cache.

## Regenerate

From the py2rust repository root, with its development environment installed:

```bash
export PYTHONPATH="$PWD"
python - <<'PY'
from pathlib import Path
from py2rust.compiler.pipeline import compile_loaded_project
from py2rust.compiler.project import Project
from py2rust.compiler.project_output import write_service_project

root = Path.home() / "experimental/OpenCiv3-Development/OpenCiv3-Development/C7"
code = compile_loaded_project(
    Project(root, "civ3_console/standalone.py"),
    packaged=True,
    python_scope=True,
)
write_service_project(code, Path("examples/projects/openciv3_standalone_rust"))
PY
```

The source locations embedded in `main.rs` refer to the OpenCiv3 checkout used
during generation; they are diagnostics, not Python runtime dependencies.
