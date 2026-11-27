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
    from .values import Type

    def dynamic(typ: Type) -> bool:
        return typ.name == "union" or any(dynamic(item) for item in typ.args)

    traits = ", Eq, PartialOrd, Ord, Hash" if compiler.hashable(Type(name)) else ""
    if any(dynamic(typ) for typ, _ in fields.values()):
        from .union_emission import clone_union
        from .values import Expr

        def cloned(typ: Type, value: str) -> str:
            if typ.name == "union":
                return clone_union(Expr(value, typ)).code.replace(
                    'return Err("unsupported union value".into())', 'panic!("unsupported union value")'
                )
            if typ.name == "optional" and dynamic(typ.args[0]):
                inner = cloned(typ.args[0], "__value")
                return f"({value}).as_ref().map(|__value| {inner})"
            if typ.name in {"list", "tuple_var"} and dynamic(typ.args[0]):
                inner = cloned(typ.args[0], "__value")
                return f"({value}).iter().map(|__value| {inner}).collect::<Vec<_>>()"
            if typ.name == "dict" and dynamic(typ.args[1]):
                inner = cloned(typ.args[1], "__value")
                return (
                    f"({value}).iter().map(|(__key, __value)| (__key.clone(), {inner}))"
                    ".collect::<indexmap::IndexMap<_, _>>()"
                )
            return f"({value}).clone()"

        initializers = ",\n".join(f"{field}: {cloned(typ, 'self.' + field)}" for field, (typ, _) in fields.items())
        definition = (
            f"#[derive(Clone)]\nstruct {storage} {{\n{body}\n}}\n"
            if storage != name
            else f"struct {storage} {{\n{body}\n}}\n"
        )
        definition += f"impl Clone for {storage} {{ fn clone(&self) -> Self {{ Self {{ {initializers} }} }} }}"

        def equal(typ: Type, left: str, right: str) -> str:
            if typ.name == "union":
                from .union_emission import nullable, variants

                left_value, right_value = "__left", "__right"
                if nullable(typ):
                    comparison = equal(Type("union", variants(typ)), left_value, right_value)
                    return (
                        f"match (({left}).as_ref(), ({right}).as_ref()) {{ "
                        f"(Some(__left), Some(__right)) => {comparison}, (None, None) => true, _ => false }}"
                    )
                result = "false"
                for item in reversed(variants(typ)):
                    result = (
                        f"if let Some(__left) = ({left}).downcast_ref::<{item.rust()}>() {{ "
                        f"({right}).downcast_ref::<{item.rust()}>() == Some(__left) }} else {{ {result} }}"
                    )
                return result
            if typ.name == "optional" and dynamic(typ.args[0]):
                comparison = equal(typ.args[0], "__left", "__right")
                return (
                    f"match (({left}).as_ref(), ({right}).as_ref()) {{ "
                    f"(Some(__left), Some(__right)) => {comparison}, (None, None) => true, _ => false }}"
                )
            if typ.name in {"list", "tuple_var"} and dynamic(typ.args[0]):
                comparison = equal(typ.args[0], "__left", "__right")
                return (
                    f"({left}).len() == ({right}).len() && ({left}).iter().zip(({right}).iter())"
                    f".all(|(__left, __right)| {comparison})"
                )
            if typ.name == "dict" and dynamic(typ.args[1]):
                comparison = equal(typ.args[1], "__left", "__right")
                return (
                    f"({left}).len() == ({right}).len() && ({left}).iter().all(|(__key, __left)| "
                    f"({right}).get(__key).map(|__right| {comparison}).unwrap_or(false))"
                )
            return f"({left}) == ({right})"

        comparisons = " && ".join(equal(typ, "self." + field, "other." + field) for field, (typ, _) in fields.items())
        definition += f"impl PartialEq for {storage} {{ fn eq(&self, other: &Self) -> bool {{ {comparisons} }} }}"
        if storage == name:
            return definition
    else:
        definition = f"#[derive(Clone, PartialEq{traits})]\nstruct {storage} {{\n{body}\n}}"
    if storage == name:
        return definition
    # Arc preserves Send/Sync for records passed to native parallel consumers.
    # make_mut detaches only this node; recursive children retain shared storage.
    return definition + f"""
#[derive(Clone, PartialEq{traits})]
struct {name}(std::sync::Arc<{storage}>);
impl std::ops::Deref for {name} {{
    type Target = {storage};
    fn deref(&self) -> &Self::Target {{ &self.0 }}
}}
impl std::ops::DerefMut for {name} {{
    fn deref_mut(&mut self) -> &mut Self::Target {{ std::sync::Arc::make_mut(&mut self.0) }}
}}
"""
