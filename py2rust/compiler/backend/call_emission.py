"""Explicit call dispatch; specific handlers own validation and rendering."""

from __future__ import annotations

import ast
from typing import TYPE_CHECKING

from ..library_contracts import LIBRARY, LOG_LEVELS, MODULE_CALLS
from ..rust_imports import symbol_name
from ..rust_text import quote
from .values import Expr, Type

if TYPE_CHECKING:
    from ..service import ServiceCompiler

from .callback_emission import (
    emit_function_call,
    emit_http_server,
    emit_parallel_map,
    emit_web_server,
)
from .comprehension_emission import emit_comprehension
from .constructor_emission import (
    emit_bytes_constructor,
    emit_empty_constructor,
    emit_hex_constructor,
    emit_sequence_constructor,
    emit_set_constructor,
)
from .module_call_emission import emit_crc32, emit_heap_operation
from .find_emission import emit_find
from .scalar_call_emission import (
    emit_abs,
    emit_conversion,
    emit_key_extreme,
    emit_key_sorted,
    emit_length,
    emit_ord,
    emit_print,
    emit_scalar_extreme,
    emit_sequence_extreme,
    emit_sum,
    emit_zip,
)


def emit_call(compiler: ServiceCompiler, node: ast.Call, expected: Type | None = None) -> Expr:
    name = ast.unparse(node.func)
    if name == "__comprehend" and hasattr(node, "py2rust_comprehension"):
        return emit_comprehension(compiler, node, expected)
    if name == "__find" and hasattr(node, "py2rust_find"):
        return emit_find(compiler, node, expected)
    if name == "__enum_name":
        value = compiler.expr(node.args[0])
        arms = []
        for variant in node.py2rust_enum_name:
            member, number = variant.rsplit("=", 1)
            arms.append(f"{number} => {quote(member.rsplit('.', 1)[-1])}.to_owned()")
        return Expr(
            f"match ({value.code}) {{ {', '.join(arms)}, _ => String::new() }}",
            Type("str"),
        )
    if name == "__choice":
        random = compiler.expr(node.args[0])
        sequence = compiler.expr(node.args[1])
        if sequence.type.name not in {"list", "tuple_var"} or not sequence.type.args:
            compiler.error("choice requires a typed sequence", node)
        return Expr(
            f"{{ let __random = {random.code}; let __values = {sequence.code}; "
            "let __index = rt::random_randrange(&__random, 0, __values.len() as i64)?; "
            "rt::at(&__values, __index)? }",
            sequence.type.args[0],
        )
    if name == "__accumulate":
        source = compiler.expr(node.args[0])
        if source.type.name not in {"list", "tuple_var"} or source.type.args[0].name not in {"int", "float"}:
            compiler.error("accumulate requires a typed numeric sequence", node)
        item = source.type.args[0]
        initial = compiler.expr(node.args[1], item).code if len(node.args) == 2 else ""
        setup = (
            f"let mut __total = {initial}; let mut __has_total = true;"
            if initial
            else "let mut __total: " + item.rust() + "; let mut __has_total = false;"
        )
        return Expr(
            f"{{ let mut __result: {Type('list', (item,)).rust()} = Vec::new(); {setup} "
            + ("__result.push(__total);" if initial else "")
            + f" for __item in ({source.code}).into_iter() {{ "
            + (
                '__total = __total.checked_add(__item).ok_or("integer overflow")?;'
                if item.name == "int"
                else (
                    "__total = __total + __item;"
                    if initial
                    else "if __has_total { __total = __total + __item; } else { __total = __item; __has_total = true; }"
                )
            )
            + " __result.push(__total); } __result }",
            Type("list", (item,)),
        )
    if name == "__dict_merge":
        sources = [compiler.expr(argument, expected) for argument in node.args]
        if not sources or any(source.type.name != "dict" for source in sources):
            compiler.error("dictionary unpacking requires typed dictionaries", node)
        result = sources[0].type
        setup = " ".join(f"__result.extend({source.code});" for source in sources)
        return Expr(
            f"{{ let mut __result: {result.rust()} = indexmap::IndexMap::new(); {setup} __result }}",
            result,
        )
    if name == "__next_counter":
        target = node.py2rust_counter
        return Expr(
            f"{{ let __value = {target}; {target} += 1; __value }}",
            Type("int"),
        )
    if name == "__defaultdict_list":
        if expected is None or expected.name != "dict" or expected.args[1].name != "list":
            compiler.error("list defaultdict requires a typed dictionary result", node)
        return Expr(f"indexmap::IndexMap::<{expected.args[0].rust()}, {expected.args[1].rust()}>::new()", expected)
    if name == "__defaultdict_set":
        if expected is None or expected.name != "dict" or expected.args[1].name != "set":
            compiler.error("set defaultdict requires a typed dictionary result", node)
        return Expr(f"indexmap::IndexMap::<{expected.args[0].rust()}, {expected.args[1].rust()}>::new()", expected)
    if name == "__format_value":
        spec = node.py2rust_format_value
        value = compiler.expr(node.args[0])
        if spec == "":
            original_optional = value.type.name == "optional"
            if value.type.name == "optional" and value.type.args[0].name in {"str", "int", "float", "bool"}:
                value = compiler.convert(value, value.type.args[0], node)
            if value.type.name in compiler.enums:
                return compiler.expr(ast.Attribute(value=node.args[0], attr="name", ctx=ast.Load()), Type("str"))
            if value.type.name == "bool":
                return Expr(f'if {value.code} {{ "True".to_string() }} else {{ "False".to_string() }}', Type("str"))
            if value.type.name in {"str", "int", "float"} and original_optional:
                if value.type.name == "str":
                    return Expr(f"({value.code}).clone()", Type("str"))
                if value.type.name == "float":
                    return Expr(f"rt::float_to_string({value.code})?", Type("str"))
                return Expr(f"({value.code}).to_string()", Type("str"))
            if value.type.name == "tuple":

                def render(item: Expr) -> str:
                    if item.type.name == "tuple":
                        nested = [
                            render(Expr(f"({item.code}).{index}", field)) for index, field in enumerate(item.type.args)
                        ]
                        code = '{ let mut __text = "(".to_string(); '
                        for part_index, part in enumerate(nested):
                            code += f"__text.push_str(&({part}));"
                            if part_index + 1 < len(nested):
                                code += '__text.push_str(", ");'
                        if len(nested) == 1:
                            code += '__text.push_str(",");'
                        return code + '__text.push_str(")"); __text }'
                    if item.type.name == "str":
                        return f"({item.code}).clone()"
                    if item.type.name == "float":
                        return f"rt::float_to_string({item.code})?"
                    if item.type.name == "bool":
                        return f'if {item.code} {{ "True".to_string() }} else {{ "False".to_string() }}'
                    return f"({item.code}).to_string()"

                parts = [render(Expr(f"({value.code}).{index}", field)) for index, field in enumerate(value.type.args)]
                code = '{ let mut __text = "(".to_string(); '
                for index, part in enumerate(parts):
                    code += f"__text.push_str(&({part}));"
                    if index + 1 < len(parts):
                        code += '__text.push_str(", ");'
                if len(parts) == 1:
                    code += '__text.push_str(",");'
                code += '__text.push_str(")"); __text }'
                return Expr(code, Type("str"))
            conversion = ast.copy_location(
                ast.Call(func=ast.Name(id="str", ctx=ast.Load()), args=[node.args[0]], keywords=[]), node
            )
            return emit_conversion(compiler, conversion, "str")
        if spec.startswith("!r"):
            return Expr(f"rt::repr_text(&({compiler.expr(node.args[0], Type('str')).code}))", Type("str"))
        if spec.endswith("d") and value.type.name == "int":
            return Expr(f"rt::format_int({value.code}, {quote(spec)})", Type("str"))
        if spec.endswith("s") and value.type.name == "str":
            return Expr(f"rt::format_text(&({value.code}), {quote(spec)})", Type("str"))
        if spec.endswith("f") and value.type.name == "float":
            return Expr(f"rt::format_float({value.code}, {quote(spec)})?", Type("str"))
        if spec.endswith("g") and value.type.name == "float":
            return Expr(f"rt::float_to_string({value.code})?", Type("str"))
        compiler.error(f"unsupported format spec {spec}", node)
    if name == "__enum_members":
        enum = node.py2rust_enum_members
        if expected is None or expected.name != "dict":
            compiler.error("enum members requires a typed dictionary result", node)
        entries = ", ".join(f"({quote(member)}.to_owned(), {enum}::{member})" for member in compiler.enums[enum])
        return Expr(f"[{entries}].into_iter().collect::<{expected.rust()}>()", expected)
    if name == "__enum_from_value":
        enum = node.py2rust_enum_from_value
        value = compiler.expr(node.args[0])
        arms = []
        for member, member_value in compiler.enums[enum].items():
            literal = quote(member_value) if isinstance(member_value, str) else f"{member_value}i64"
            arms.append(f"{literal} => {enum}::{member}")
        string_enum = isinstance(next(iter(compiler.enums[enum].values())), str)
        source = f"({value.code}).as_str()" if string_enum else f"({value.code})"
        return Expr(
            f"match {source} {{ {', '.join(arms)}, _ => return Err(\"unknown enum value\".into()) }}",
            Type(enum),
        )
    if name == "__enum_name_exists":
        enum, variants = node.py2rust_enum_name_exists
        value = compiler.expr(node.args[0], Type("str"))
        names = compiler.enums.get(enum, {name: 0 for name in variants[1:]})
        checks = " || ".join(f"({value.code}) == {quote(name)}" for name in names)
        return Expr(f"!({checks})" if variants[0] == "not in" else f"({checks})", Type("bool"))
    if name == "__enum_from_name":
        enum, variants = node.py2rust_enum_from_name
        value = compiler.expr(node.args[0], Type("str"))
        if enum in compiler.enums:
            arms = [f"{quote(member)} => {enum}::{member}" for member in compiler.enums[enum]]
        else:
            arms = []
            for variant in variants:
                member, member_value = variant.split("=", 1)
                arms.append(f"{quote(member.rsplit('.', 1)[-1])} => {member_value}i64")
        return Expr(
            f"match ({value.code}).as_str() {{ {', '.join(arms)}, _ => return Err(\"unknown enum name\".into()) }}",
            Type(enum) if enum in compiler.enums else Type("int"),
        )
    if name == "__sequence_index":
        source = compiler.expr(node.args[0])
        value = compiler.expr(node.args[1], source.type.args[0])
        if source.type.name == "tuple":
            source = Expr(
                f"vec![{', '.join(f'({source.code}).{index}.clone()' for index in range(len(source.type.args)))}]",
                Type("list", source.type.args[:1]),
            )
        return Expr(f"rt::index_of(&({source.code}), &({value.code}))?", Type("int"))
    if name == "__is_type":
        class_name, operation = node.py2rust_is_type
        value = compiler.expr(node.args[0])
        class_names = class_name.split("|")
        if value.type.name == "optional" and value.type.args[0].name == "Json":
            value = compiler.convert(value, Type("Json"), node)
        if value.type.name == "Json":
            kinds = {
                {
                    "builtins.str": "string",
                    "builtins.int": "number",
                    "builtins.float": "number",
                    "builtins.bool": "bool",
                    "builtins.list": "array",
                    "builtins.dict": "object",
                    "builtins.NoneType": "null",
                }[name]
                for name in class_names
            }
            if operation in {"is", "in"}:
                checks = " || ".join(f"rt::json_kind(&({value.code})) == {quote(kind)}" for kind in kinds)
            else:
                checks = " && ".join(f"rt::json_kind(&({value.code})) != {quote(kind)}" for kind in kinds)
            return Expr(checks, Type("bool"))
        if value.type.name == "union":
            source = f"&({value.code})"
            checks = " || ".join(f"({source}).is::<{symbol_name(*name.rsplit('.', 1))}>()" for name in class_names)
            return Expr(checks, Type("bool"))
        matches = any(value.type.name == name or value.type.name == name.rsplit(".", 1)[-1] for name in class_names)
        return Expr(str(matches).lower(), Type("bool"))
    if name == "__set_union":
        source_type = expected if expected is not None and expected.name == "set" else None
        sources = [
            compiler.expr(
                argument,
                (
                    source_type
                    if isinstance(argument, ast.Call)
                    and isinstance(argument.func, ast.Name)
                    and argument.func.id == "__comprehend"
                    else None
                ),
            )
            for argument in node.args
        ]
        sources = [
            (
                compiler.convert(source, source.type.args[0], node)
                if source.type.name == "optional" and source.type.args[0].name in {"list", "set", "tuple", "tuple_var"}
                else source
            )
            for source in sources
        ]
        sources = [
            (
                compiler.convert(source, Type("tuple_var", (source.type.args[0],)), node)
                if source.type.name == "tuple"
                and source.type.args
                and all(item == source.type.args[0] for item in source.type.args)
                else source
            )
            for source in sources
        ]
        if not sources or any(source.type.name not in {"list", "set", "tuple", "tuple_var"} for source in sources):
            compiler.error(f"set union requires typed collections, got {[source.type for source in sources]}", node)
        first = sources[0].type.args[0]
        element_types = sources[0].type.args[:1] if sources[0].type.name == "tuple" else sources[0].type.args
        result = Type(
            "set",
            first.args if first.name in {"list", "set", "tuple_var"} and first.args else element_types,
        )
        setup = " ".join(
            (
                f"for __outer in ({source.code}).into_iter() {{ for __item in __outer.into_iter() "
                "{ __result.insert(__item); } }"
                if source.type.args and source.type.args[0].name in {"list", "set", "tuple_var"}
                else f"for __item in ({source.code}).into_iter() {{ __result.insert(__item); }}"
            )
            for source in sources
        )
        return Expr(
            f"{{ let mut __result: {result.rust()} = std::collections::BTreeSet::new(); {setup} __result }}",
            result,
        )
    if name == "__pack_float":
        return compiler.library_call("struct_pack_float", node.args, node)
    if name == "__pack_ints":
        format_arg = compiler.expr(node.args[0])
        values = [compiler.expr(argument, Type("int")) for argument in node.args[1:]]
        code = ", ".join(value.code for value in values)
        return Expr(f"rt::struct_pack_ints({format_arg.code}, &vec![{code}])?", Type("bytes"))
    if name == "__unpack_ints":
        value = compiler.library_call("struct_unpack_ints", node.args, node)
        fields = ", ".join(f"__struct_values[{index}]" for index in range(node.py2rust_tuple_items))
        return Expr(
            f"{{ let __struct_values = {value.code}; ({fields},) }}",
            Type("tuple", (Type("int"),) * node.py2rust_tuple_items),
        )
    if name == "__unique_sequence":
        source = compiler.expr(node.args[0])
        if source.type.name not in {"list", "tuple_var"} or not source.type.args:
            compiler.error("ordered unique iteration requires a typed sequence", node)
        result = Type("list", source.type.args)
        return Expr(
            f"{{ let mut __seen = std::collections::BTreeSet::new(); "
            f"let mut __result: {result.rust()} = Vec::new(); "
            "for __item in ("
            + source.code
            + ").into_iter() { if __seen.insert(__item.clone()) { __result.push(__item); } } __result }",
            result,
        )
    if name == "__optional_value":
        value = compiler.expr(node.args[0])
        default = compiler.expr(node.args[1], value.type.args[0])
        return Expr(
            f"match ({value.code}) {{ Some(value) => value, None => {default.code} }}",
            value.type.args[0],
        )
    if name == "__counter":
        if not node.args:
            if expected is None or expected.name != "dict" or expected.args[1].name != "int":
                compiler.error("empty Counter requires a typed dictionary result", node)
            return Expr(
                f"indexmap::IndexMap::<{expected.args[0].rust()}, {expected.args[1].rust()}>::new()",
                expected,
            )
        source = compiler.expr(node.args[0])
        if (
            source.type.name == "tuple"
            and source.type.args
            and all(item == source.type.args[0] for item in source.type.args)
        ):
            source = compiler.convert(source, Type("tuple_var", (source.type.args[0],)), node)
        if source.type.name == "dict":
            source = Expr(
                f"({source.code}).keys().cloned().collect::<Vec<_>>()",
                Type("list", (source.type.args[0],)),
            )
        if source.type.name not in {"list", "set", "tuple_var"} or not source.type.args:
            compiler.error(f"Counter requires a typed iterable, got {source.type}", node)
        result = Type("dict", (source.type.args[0], Type("int")))
        return Expr(
            f"{{ let mut __counts: {result.rust()} = indexmap::IndexMap::new(); "
            f"for __item in ({source.code}).into_iter() {{ "
            "*__counts.entry(__item).or_insert(0) += 1; } __counts }",
            result,
        )
    if name == "__unpack_float":
        value = compiler.library_call("struct_unpack_float", node.args, node)
        return Expr(f"({value.code},)", Type("tuple", (Type("float"),)))
    if name == "__map_random":
        kind = node.py2rust_map_random
        receiver = compiler.expr(node.args[0])
        if receiver.type.name != "py__strategy__random__MapRandom":
            compiler.error("MapRandom intrinsic requires its concrete receiver", node)
        original = ast.unparse(node.args[0])
        borrowed = isinstance(node.args[0], ast.Name) and node.args[0].id in compiler.borrowed_parameters
        assignment_target = f"*{original}" if original == "self_" or borrowed else original
        target = "__map_random"
        sample = (
            f"let mut __map_random = {original}.clone(); "
            f"{target}._index = if {target}._index < 55 {{ {target}._index + 1 }} else {{ 1 }}; "
            f"{target}._other = if {target}._other < 55 {{ {target}._other + 1 }} else {{ 1 }}; "
            f"let __sample_index = {target}._index as usize; "
            f"let mut __value = ({target}._values[__sample_index] - {target}._values[{target}._other as usize] "
            "+ 2147483648i64).rem_euclid(4294967296i64) - 2147483648i64; "
            "if __value == 2147483647i64 { __value -= 1; } "
            "if __value < 0 { __value += 2147483647i64; } "
            f"{target}._values[__sample_index] = __value; "
            f"{assignment_target} = __map_random;"
        )
        if kind == "_sample":
            return Expr(f"{{ {sample} __value }}", Type("int"))
        if kind == "next_double":
            return Expr(f"{{ {sample} (__value as f64) * (1.0 / 2147483647.0) }}", Type("float"))
        if kind == "next" and len(node.args) == 1:
            return Expr(f"{{ {sample} __value }}", Type("int"))
        if kind == "next" and len(node.args) == 2 and node.args[1] is not None:
            optional = compiler.expr(node.args[1])
            if optional.type.name == "optional":
                return Expr(
                    f"{{ if ({optional.code}).is_none() {{ {sample} __value }} else {{ "
                    f'let __maximum = ({optional.code}).ok_or("expected a value")?; '
                    'if !(0..=2147483647i64).contains(&__maximum) { return Err("Random upper bound must be a nonnegative Int32".into()); } '
                    f"{sample} ((__value as f64) * (1.0 / 2147483647.0) * (__maximum as f64)) as i64 }} }}",
                    Type("int"),
                )
        if kind == "next" and len(node.args) == 2:
            maximum = compiler.expr(node.args[1], Type("int"))
            return Expr(
                f'{{ if !(0..=2147483647i64).contains(&({maximum.code})) {{ return Err("Random upper bound must be a nonnegative Int32".into()); }} '
                f"{sample} ((__value as f64) * (1.0 / 2147483647.0) * (({maximum.code}) as f64)) as i64 }}",
                Type("int"),
            )
        if kind == "next_range" and len(node.args) == 3:
            minimum = compiler.expr(node.args[1], Type("int"))
            maximum = compiler.expr(node.args[2], Type("int"))
            return Expr(
                f"{{ let __minimum = {minimum.code}; let __maximum = {maximum.code}; "
                "if !(-2147483648i64 <= __minimum && __minimum <= __maximum && __maximum <= 2147483647i64) "
                '{ return Err("Invalid Int32 random range".into()); } '
                "let __span = __maximum - __minimum; "
                f"if __span <= 2147483647i64 {{ {sample} "
                "((__value as f64) * (1.0 / 2147483647.0) * (__span as f64)) as i64 + __minimum } else { "
                f"{sample} let __first = __value; {sample} "
                "let __second = if __value % 2 == 0 { -__first } else { __first }; "
                "let __scaled = ((__second as f64) + 2147483646.0) / 4294967293.0; "
                "((__scaled * (__span as f64)) as i64) + __minimum } }",
                Type("int"),
            )
        compiler.error("unsupported MapRandom intrinsic arguments", node)
    if name == "__shuffle":
        target = node.py2rust_shuffle
        random = compiler.expr(node.args[0])
        sequence = compiler.expr(node.args[1])
        if sequence.type.name != "list":
            compiler.error("shuffle requires a list", node)
        if random.type.name == "py__strategy__random__MapRandom":
            return Expr(
                f"{{ let mut __random = {random.code}; "
                f"for __index in 0..{target}.len().saturating_sub(1) {{ "
                "__random._index = if __random._index < 55 { __random._index + 1 } else { 1 }; "
                "__random._other = if __random._other < 55 { __random._other + 1 } else { 1 }; "
                "let __sample_index = __random._index as usize; "
                "let mut __value = (__random._values[__sample_index] - __random._values[__random._other as usize] "
                "+ 2147483648i64).rem_euclid(4294967296i64) - 2147483648i64; "
                "if __value == 2147483647i64 { __value -= 1; } "
                "if __value < 0 { __value += 2147483647i64; } "
                "__random._values[__sample_index] = __value; "
                f"let __other = __index + ((__value as f64) * (1.0 / 2147483647.0) "
                f"* (({target}.len() - __index) as f64)) as usize; "
                f"{target}.swap(__index, __other); }} () }}",
                Type("None"),
            )
        return Expr(
            f"{{ let __random = {random.code}; "
            f"for __index in (1..{target}.len()).rev() {{ "
            f"let __other = rt::random_randrange(&__random, 0, __index as i64 + 1)? as usize; "
            f"{target}.swap(__index, __other); }} () }}",
            Type("None"),
        )
    if name == "__optional_len":
        value = compiler.expr(node.args[0])
        return Expr(
            f"match ({value.code}).as_ref() {{ Some(value) => value.len() as i64, None => 0 }}",
            Type("int"),
        )
    if name == "__optional_unwrap":
        value = compiler.expr(node.args[0])
        return Expr(f'({value.code}).ok_or("expected a collection")?', value.type.args[0])
    if name == "__zip_pairs":
        return emit_zip(compiler, node)
    if name == "__replace" and hasattr(node, "py2rust_replace"):
        record, labels = node.py2rust_replace
        source = compiler.expr(node.args[0], Type(record))
        setup = [f"let mut __replacement = ({source.code}).clone();"]
        for label, argument in zip(labels, node.args[1:]):
            field = compiler.records.get(record, {}).get(label)
            if field is None:
                compiler.error("unknown dataclass replacement field", node)
            value = compiler.expr(argument, field[0])
            setup.append(f"__replacement.{label} = {value.code};")
        return Expr("{ " + " ".join(setup) + " __replacement }", Type(record))
    if name == "__truthy":
        value = compiler.expr(node.args[0])
        return Expr(f"{{ let _ = {value.code}; true }}", Type("bool"))
    if name == "__key_sorted" and hasattr(node, "py2rust_key_sorted"):
        return emit_key_sorted(compiler, node)
    if name == "__key_extreme" and hasattr(node, "py2rust_key_extreme"):
        return emit_key_extreme(compiler, node)
    if name == "__class_name":
        from .union_emission import class_name

        return class_name(compiler, compiler.expr(node.args[0]), node)
    if name in compiler.records:
        return compiler.record_constructor(name, node)
    if name == "sorted":
        return compiler.sorted_call(node, expected)
    if isinstance(node.func, ast.Name) and compiler.locals.get(name, Type("None")).name == "callable":
        signature = compiler.locals[name]
        if len(node.args) != len(signature.args) - 1 or node.keywords:
            compiler.error("callable argument count does not match its signature", node)
        arguments = [compiler.expr(argument, typ).code for argument, typ in zip(node.args, signature.args)]
        return Expr(f"{name}({', '.join(arguments)})?", signature.args[-1])
    if name in compiler.functions:
        return emit_function_call(compiler, node, name)
    if node.keywords:
        compiler.error("keyword arguments are outside the service profile", node)
    if (name == "crc32" and name in compiler.imports) or (
        name in {"zlib.crc32", "binascii.crc32"} and name.split(".")[0] in compiler.modules
    ):
        return emit_crc32(compiler, node)
    if name.startswith("heapq.") and "heapq" in compiler.modules:
        return emit_heap_operation(compiler, node, name)
    if name == "int.from_bytes":
        return compiler.library_call("int_from_bytes", node.args, node)
    if name == "round" and len(node.args) == 1:
        if not compiler.python_scope:
            compiler.error("unsupported or unimported call: round", node)
        value = compiler.expr(node.args[0])
        if value.type.name == "int":
            return value
        if value.type.name != "float":
            compiler.error("round requires an int or float", node)
        return compiler.library_call("round_float", node.args, node)
    if name == "divmod" and len(node.args) == 2:
        return compiler.library_call("divmod_int", node.args, node)
    if name == "reversed" and len(node.args) == 1:
        value = compiler.expr(node.args[0])
        if (
            value.type.name == "tuple"
            and value.type.args
            and all(item == value.type.args[0] for item in value.type.args)
        ):
            value = compiler.convert(value, Type("tuple_var", (value.type.args[0],)), node)
        if value.type.name not in {"list", "tuple_var"}:
            compiler.error(f"reversed requires a typed sequence, got {value.type}", node)
        return Expr(f"({value.code}).into_iter().rev().collect::<Vec<_>>()", value.type)
    if name == "iter" and len(node.args) == 1:
        value = compiler.expr(node.args[0])
        if value.type.name == "optional" and value.type.args[0].name in {"list", "set", "dict", "tuple", "tuple_var"}:
            value = compiler.convert(value, value.type.args[0], node)
        if value.type.name == "dict":
            return Expr(
                f"({value.code}).keys().cloned().collect::<Vec<_>>()",
                Type("list", (value.type.args[0],)),
            )
        if (
            value.type.name == "tuple"
            and value.type.args
            and all(item == value.type.args[0] for item in value.type.args)
        ):
            value = compiler.convert(value, Type("tuple_var", (value.type.args[0],)), node)
        if value.type.name not in {"list", "set", "tuple_var"}:
            compiler.error(f"iter requires a typed in-memory collection, got {value.type}", node)
        return value
    if name == "range" and len(node.args) == 3:
        return compiler.library_call("range_values", node.args, node)
    if name == "range" and len(node.args) in {1, 2}:
        start = compiler.expr(node.args[0], Type("int")) if len(node.args) == 2 else Expr("0i64", Type("int"))
        stop = compiler.expr(node.args[-1], Type("int"))
        return Expr(
            f"(({start.code}..{stop.code}).collect::<Vec<i64>>())",
            Type("list", (Type("int"),)),
        )
    if name == "enumerate" and len(node.args) in {1, 2}:
        source = compiler.expr(node.args[0])
        if source.type.name == "optional" and source.type.args[0].name in {"list", "set", "tuple", "tuple_var"}:
            source = compiler.convert(source, source.type.args[0], node)
        if (
            source.type.name == "tuple"
            and source.type.args
            and all(item == source.type.args[0] for item in source.type.args)
        ):
            source = compiler.convert(source, Type("tuple_var", (source.type.args[0],)), node)
        if source.type.name not in {"list", "set", "tuple_var", "bytes", "bytearray", "str"}:
            compiler.error(f"enumerate requires a typed in-memory iterable, got {source.type}", node)
        start = compiler.expr(node.args[1], Type("int")) if len(node.args) == 2 else Expr("0i64", Type("int"))
        element_type = (
            Type("int")
            if source.type.name in {"bytes", "bytearray"}
            else Type("str") if source.type.name == "str" else source.type.args[0]
        )
        item_type = Type("tuple", (Type("int"), element_type))
        iterator = ".chars()" if source.type.name == "str" else ".into_iter()"
        return Expr(
            f"({source.code}){iterator}.enumerate().map(|(__index, __value)| "
            f"(__index as i64 + {start.code}, __value{' as i64' if source.type.name in {'bytes', 'bytearray'} else '.to_string()' if source.type.name == 'str' else ''})).collect::<Vec<_>>()",
            Type("list", (item_type,)),
        )
    if name == "next" and len(node.args) in {1, 2}:
        source = compiler.read_value(node.args[0])
        if source.type.name not in {"list", "set", "tuple_var"}:
            compiler.error("next requires a typed in-memory iterable", node)
        item_type = source.type.args[0]
        if len(node.args) == 2:
            default = compiler.expr(node.args[1], item_type)
            return Expr(
                f"match ({compiler.reference(source)}).iter().next() {{ Some(value) => (*value).clone(), None => {default.code} }}",
                item_type,
            )
        return Expr(
            f'({compiler.reference(source)}).iter().next().cloned().ok_or("StopIteration")?',
            item_type,
        )
    if name in {"any", "all"} and len(node.args) == 1:
        source = compiler.expr(node.args[0])
        if (
            source.type.name == "tuple"
            and source.type.args
            and all(item == source.type.args[0] for item in source.type.args)
        ):
            source = compiler.convert(source, Type("tuple_var", (source.type.args[0],)), node)
        if source.type.name not in {"list", "set", "tuple_var"} or source.type.args[0].name not in {"bool", "int"}:
            compiler.error(f"{name} requires a typed Boolean or integer iterable, got {source.type}", node)
        predicate = "__value" if source.type.args[0].name == "bool" else "__value != 0"
        return Expr(f"({source.code}).into_iter().{name}(|__value| {predicate})", Type("bool"))
    if name in {"min", "max"} and len(node.args) == 1:
        return emit_sequence_extreme(compiler, node, name)
    if name == "sum" and len(node.args) == 1:
        return emit_sum(compiler, node)
    if name in {"min", "max"} and len(node.args) >= 2:
        return emit_scalar_extreme(compiler, node, name)
    if name in {"bytes", "bytearray"}:
        return emit_bytes_constructor(compiler, node, name)
    if name in {"bytes.fromhex", "bytearray.fromhex"} and len(node.args) == 1:
        return emit_hex_constructor(compiler, node, name)
    if name in {"list", "tuple"} and len(node.args) == 1:
        return emit_sequence_constructor(compiler, node, name, expected)
    if name == "set" and len(node.args) == 1:
        return emit_set_constructor(compiler, node)
    if name == "dict" and len(node.args) == 1:
        value = compiler.read_value(node.args[0])
        if value.type.name == "dict":
            return Expr(f"({value.code}).clone()", value.type)
        if (
            value.type.name in {"list", "tuple_var"}
            and value.type.args[0].name == "tuple"
            and len(value.type.args[0].args) == 2
        ):
            key_type, item_type = value.type.args[0].args
            result = Type("dict", (key_type, item_type))
            return Expr(
                f"({value.code}).into_iter().map(|__pair| (__pair.0, __pair.1))" f".collect::<{result.rust()}>()",
                result,
            )
        compiler.error(
            f"dict(value) requires another dictionary or key/value pairs, got {value.type} at "
            f"{getattr(node, 'source_path', '<unknown>')}:{node.lineno}",
            node,
        )
    if name in {"set", "frozenset", "list", "dict", "tuple"} and not node.args:
        return emit_empty_constructor(compiler, node, name, expected)
    if (
        name in {"ceil", "floor"}
        and name in compiler.imports
        or name in {"math.ceil", "math.floor"}
        and "math" in compiler.modules
    ) and len(node.args) == 1:
        value = compiler.expr(node.args[0])
        if value.type.name == "int":
            return value  # Preserve large integer arguments without an f64 round trip.
    if name in compiler.imports and name in LIBRARY:
        return compiler.library_call(name, node.args, node)
    if name in MODULE_CALLS and name.split(".")[0] in compiler.modules:
        return compiler.library_call(MODULE_CALLS[name], node.args, node)
    if name == "parallel_map" and name in compiler.imports:
        return emit_parallel_map(compiler, node)
    if name in {"web_serve", "web_serve_stream"} and name in compiler.imports:
        return emit_web_server(compiler, node, name)
    if name.startswith("logging.") and "logging" in compiler.modules and name.split(".")[1].upper() in LOG_LEVELS:
        level = ast.Constant(LOG_LEVELS[name.split(".")[1].upper()])
        return compiler.library_call("log", [level, *node.args], node)
    if name in {"http_serve_json", "http_serve_json_timeout"} and name in compiler.imports:
        return emit_http_server(compiler, node, name)
    if name == "ord":
        return emit_ord(compiler, node)
    if name == "len" and len(node.args) == 1:
        return emit_length(compiler, node)
    if name == "bool" and len(node.args) == 1:
        value = compiler.expr(node.args[0])
        expressions = {
            "bool": value.code,
            "int": f"({value.code}) != 0",
            "float": f"({value.code}) != 0.0",
            "str": f"!({value.code}).is_empty()",
            "bytes": f"!({value.code}).is_empty()",
            "bytearray": f"!({value.code}).is_empty()",
            "list": f"!({value.code}).is_empty()",
            "set": f"!({value.code}).is_empty()",
            "dict": f"!({value.code}).is_empty()",
            "tuple_var": f"!({value.code}).is_empty()",
            "optional": f"({value.code}).is_some()",
        }
        if value.type.name not in expressions:
            compiler.error(f"bool conversion does not support {value.type}", node)
        return Expr(expressions[value.type.name], Type("bool"))
    if name in {"str", "int", "float"} and len(node.args) == 1:
        return emit_conversion(compiler, node, name)
    if name == "abs" and len(node.args) == 1:
        return emit_abs(compiler, node)
    if name == "print":
        return emit_print(compiler, node)
    if isinstance(node.func, ast.Attribute):
        return compiler.method(node)
    compiler.error(f"unsupported or unimported call: {ast.unparse(node)}", node)
