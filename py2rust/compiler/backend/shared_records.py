"""Copy-on-write storage for resource-free recursive value records."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .values import Type

if TYPE_CHECKING:
    from ..service import ServiceCompiler


def prepare_shared_records(compiler: ServiceCompiler) -> None:
    compiler.shared_records = {}
    if not compiler.optimize:
        return

    def references(typ: Type, target: str, seen: set[str]) -> bool:
        if typ.name == target:
            return True
        if typ.name in compiler.records and typ.name not in seen:
            return any(references(field[0], target, seen | {typ.name}) for field in compiler.records[typ.name].values())
        return any(references(argument, target, seen) for argument in typ.args)

    used = set(compiler.records) | set(compiler.functions) | set(compiler.enums) | set(compiler.constants)
    for name, fields in compiler.records.items():
        if not compiler.move_safe_type(Type(name)) or not any(
            references(field[0], name, {name}) for field in fields.values()
        ):
            continue
        storage = name.rsplit("__", 1)[-1] + "Storage"
        while storage in used:
            storage += "_"
        used.add(storage)
        compiler.shared_records[name] = storage
    return


def record_definition(compiler: ServiceCompiler, name: str) -> str:
    fields = compiler.records[name]
    storage = compiler.shared_records.get(name, name)
    body = "\n".join(field + ": " + typ.rust() + "," for field, (typ, _) in fields.items())
    definition = f"#[derive(Clone)]\nstruct {storage} {{\n{body}\n}}"
    if storage == name:
        return definition
    # Arc preserves Send/Sync for records passed to native parallel consumers.
    # make_mut detaches only this node; recursive children retain shared storage.
    return definition + f"""
#[derive(Clone)]
struct {name}(std::sync::Arc<{storage}>);
impl std::ops::Deref for {name} {{
    type Target = {storage};
    fn deref(&self) -> &Self::Target {{ &self.0 }}
}}
impl std::ops::DerefMut for {name} {{
    fn deref_mut(&mut self) -> &mut Self::Target {{ std::sync::Arc::make_mut(&mut self.0) }}
}}
"""
