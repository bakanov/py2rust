"""Package emitted Rust without importing either compiler frontend."""

from pathlib import Path


def cargo_files(code: str, binary_name: str = "py2rust-service") -> dict[str, bytes]:
    """Prepare runtime and source files; callers validate destination and binary name."""
    runtime = Path(__file__).with_name("service_runtime")
    files = {"src/main.rs": code.encode(), "Cargo.lock": (runtime / "Cargo.lock").read_bytes()}
    manifest = (runtime / "Cargo.toml").read_text()
    manifest += f'\n[[bin]]\nname = "{binary_name}"\npath = "src/main.rs"\n'
    files["Cargo.toml"] = manifest.encode()
    for source in (runtime / "src").glob("*.rs"):
        files["src/" + source.name] = source.read_bytes()
    return files


def write_service_project(code: str, output: Path) -> None:
    """Write a standalone Cargo project with the packaged, locked runtime."""
    for name, content in cargo_files(code).items():
        destination = output / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(content)
    return
