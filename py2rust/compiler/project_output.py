"""Package emitted Rust without importing either compiler frontend."""

import hashlib
import json
from pathlib import Path


def application_source_files(project: Path) -> list[Path]:
    """Return generated application modules, excluding imported native Rust."""
    for marker in [".py2rust-project.json", ".py2rust-modular.json"]:
        if not (project / marker).is_file():
            continue
        metadata = json.loads((project / marker).read_text())
        modules = metadata.get("modules", {})
        if modules:
            names = {"src/main.rs"}
            names.update(item["rust"] if isinstance(item, dict) else item for item in modules.values())
            root = project.resolve()
            return sorted(
                candidate
                for name in names
                if (candidate := (project / name).resolve()).is_relative_to(root) and candidate.is_file()
            )
    return sorted(
        path for path in (project / "src").rglob("*.rs") if "native" not in path.relative_to(project / "src").parts
    )


def application_source_text(project: Path) -> str:
    return "\n".join(path.read_text() for path in application_source_files(project))


def application_source_digest(project: Path) -> str:
    digest = hashlib.sha256()
    for path in application_source_files(project):
        digest.update(path.relative_to(project).as_posix().encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


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


def cargo_module_files(sources: dict[str, str], binary_name: str = "py2rust-service") -> dict[str, bytes]:
    """Prepare a Python-shaped application with its supporting runtime outside src/."""
    files = cargo_files("", binary_name)
    files.pop("src/main.rs")
    for name in list(files):
        if name.startswith("src/"):
            files["runtime/" + name.removeprefix("src/")] = files.pop(name)
    manifest = files["Cargo.toml"].decode()
    manifest += '\n[lib]\nname = "py2rust_service_runtime"\npath = "runtime/lib.rs"\n'
    files["Cargo.toml"] = manifest.encode()
    for name, source in sources.items():
        files[name] = source.encode()
    return files


def write_service_project(code: str, output: Path) -> None:
    """Write a standalone Cargo project with the packaged, locked runtime."""
    for name, content in cargo_files(code).items():
        destination = output / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(content)
    return
