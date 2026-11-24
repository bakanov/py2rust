"""Read and replace explicit object-key/array-index paths using owned JSON values."""

from py2rust.stdlib import Json, json_array, json_int, json_keys, json_kind, json_string


def select(value: Json, path: list[Json], depth: int) -> tuple[bool, str]:
    if depth == len(path):
        return (True, json_string(value))
    component: Json = path[depth]
    if json_kind(component) == "string":
        key: str = json_string(component)
        assert json_kind(value) == "object", "expected object at target path"
        if key not in json_keys(value):
            return (False, "")
        return select(value[key], path, depth + 1)
    index: int = json_int(component)
    items: list[Json] = json_array(value)
    if index >= len(items):
        return (False, "")
    return select(items[index], path, depth + 1)


def replace(value: Json, path: list[Json], depth: int, text: str) -> Json:
    if depth == len(path):
        return text
    component: Json = path[depth]
    if json_kind(component) == "string":
        key: str = json_string(component)
        value[key] = replace(value[key], path, depth + 1, text)
        return value
    index: int = json_int(component)
    items: list[Json] = json_array(value)
    items[index] = replace(items[index], path, depth + 1, text)
    return items
