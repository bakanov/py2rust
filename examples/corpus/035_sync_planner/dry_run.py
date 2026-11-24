"""Execute the plan on values, checking guards and directory dependencies."""

from documents import under

from py2rust.stdlib import Json, json_array, json_equal, json_string, path_parent


def simulate(destination: dict[str, Json], result: Json) -> dict[str, Json]:
    state: dict[str, Json] = {}
    for name in destination:  # noqa: PLC0206 - typed key iteration
        state[name] = destination[name]
    for action in json_array(result["operations"]):
        name: str = json_string(action["path"])
        operation: str = json_string(action["op"])
        assert json_equal(state.get(name, None), action["before"]), "dry run precondition mismatch"
        for conflict in json_array(result["conflicts"]):
            assert not under(name, json_string(conflict["path"])), "operation touches a conflict"
        if operation == "remove":
            assert name != "", "cannot remove root"
            for child in state:
                assert child == name or not under(child, name), "directory removal precedes its children"
            del state[name]
        elif operation == "chmod":
            assert name in state and json_string(state[name]["kind"]) == "directory", "chmod requires a directory"
            state[name] = action["after"]
        else:
            assert name not in state and name != "", "creation collides"
            parent: str = path_parent(name)
            parent = "" if parent == "." else parent
            assert parent in state and json_string(state[parent]["kind"]) == "directory", "missing creation parent"
            state[name] = action["after"]
    return state
