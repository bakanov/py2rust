"""Explicit categories and conservative choices for a flat download directory."""

from guards import fields, identity, relative

from py2rust.stdlib import (
    Json,
    datetime_format,
    datetime_from_unix,
    json_array,
    json_bool,
    json_int,
    json_keys,
    json_string,
    path_resolve,
    regex_fullmatch,
)


def load(value: Json) -> Json:
    fields(
        value,
        [
            "root",
            "categories",
            "date_format",
            "include_hidden",
            "skip_suffixes",
            "max_entries",
            "max_files",
            "max_bytes",
        ],
    )
    root: str = path_resolve(json_string(value["root"]))
    assert root != "/", "cannot organize filesystem root"
    identity(root)
    value["root"] = root
    for key in ["max_entries", "max_files", "max_bytes"]:
        maximum: int = 10000 if key == "max_entries" else 1000 if key == "max_files" else 1099511627776
        assert 1 <= json_int(value[key]) <= maximum, "invalid budget"
    json_bool(value["include_hidden"])
    pattern: str = json_string(value["date_format"])
    relative(datetime_format(datetime_from_unix(0), pattern))
    categories: Json = value["categories"]
    assert len(json_keys(categories)) <= 32, "too many categories"
    seen: set[str] = set()
    for category in json_keys(categories):
        assert regex_fullmatch("[A-Za-z][A-Za-z0-9_-]{0,31}", category), "invalid category"
        suffixes: list[Json] = json_array(categories[category])
        assert 1 <= len(suffixes) <= 32, "invalid extension list"
        for suffix in suffixes:
            text: str = json_string(suffix)
            assert regex_fullmatch("\\.[a-z0-9][a-z0-9._-]{0,30}", text) and ".." not in text, "invalid extension"
            assert text not in seen, "extension belongs to multiple categories"
            seen.add(text)
    skipped: list[Json] = json_array(value["skip_suffixes"])
    assert len(skipped) <= 32, "too many skipped suffixes"
    for suffix in skipped:
        assert regex_fullmatch("\\.[a-z0-9][a-z0-9._-]{0,30}", json_string(suffix)), "invalid skipped suffix"
    return value


def classify(name: str, categories: Json) -> tuple[str, str]:
    category: str = "other"
    suffix: str = ""
    for candidate in json_keys(categories):
        for item in json_array(categories[candidate]):
            extension: str = json_string(item)
            if len(extension) < len(name) and len(extension) > len(suffix) and name.lower().endswith(extension):
                category = candidate
                suffix = name[-len(extension) :]
    if suffix == "":
        dot: int = name.rfind(".")
        if 0 < dot < len(name) - 1:
            suffix = name[dot:]
    return (category, suffix)
