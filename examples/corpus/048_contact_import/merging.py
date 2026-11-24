"""Connected matching groups with lossless, per-value provenance and explicit ambiguity."""

from dataclasses import dataclass

from schema import field_names, parse

from py2rust.stdlib import (
    Json,
    json_canonical,
    json_string,
    sha256_digest,
    sha256_new,
    sha256_update,
)


@dataclass
class Contact:
    raw: Json
    values: dict[str, str]
    variant: str


def digest(value: Json) -> str:
    return sha256_digest(sha256_update(sha256_new(), json_canonical(value).encode()))


def order(records: dict[str, Json]) -> list[Contact]:
    indexes: list[tuple[str, str, str]] = []
    for variant in records:  # noqa: PLC0206 - subset key iteration
        raw: Json = records[variant]
        indexes.append((json_string(raw["source"]), json_string(raw["id"]), variant))
    result: list[Contact] = []
    for entry in sorted(indexes):
        raw: Json = records[entry[2]]
        result.append(Contact(raw, parse(raw).values, entry[2]))
    return result


def group(records: list[Contact], rules: list[list[str]]) -> dict[int, list[int]]:
    parents: list[int] = []
    for index in range(len(records)):
        parents.append(index)  # noqa: PERF402 - explicit typed range construction
    owners: dict[str, int] = {}
    for index in range(len(records)):
        contact: Contact = records[index]
        identity: Json = ["identity", contact.raw["source"], contact.raw["id"]]
        tokens: list[str] = [json_canonical(identity)]
        for rule in rules:
            values: list[str] = []
            for field in rule:
                values.append(contact.values[field])
            if "" not in values:
                signature: Json = ["match", rule, values]
                tokens.append(json_canonical(signature))
        for token in tokens:
            if token in owners:
                left: int = index
                right: int = owners[token]
                while parents[left] != left:
                    left = parents[left]
                while parents[right] != right:
                    right = parents[right]
                parents[max(left, right)] = min(left, right)
            else:
                owners[token] = index
    groups: dict[int, list[int]] = {}
    for index in range(len(records)):
        root: int = index
        while parents[root] != root:
            root = parents[root]
        if root not in groups:
            groups[root] = []
        groups[root].append(index)
    return groups


def summarize(records: list[Contact]) -> Json:
    variants: list[str] = []
    references: list[Json] = []
    by_value: dict[tuple[str, str], list[str]] = {}
    identities: dict[tuple[str, str], list[str]] = {}
    for contact in records:
        variants.append(contact.variant)
        source: str = json_string(contact.raw["source"])
        identifier: str = json_string(contact.raw["id"])
        references.append({"source": source, "id": identifier, "variant": contact.variant})
        identity: tuple[str, str] = (source, identifier)
        if identity not in identities:
            identities[identity] = []
        identities[identity].append(contact.variant)
        for field in field_names():
            value: str = contact.values[field]
            if value != "":
                key: tuple[str, str] = (field, value)
                if key not in by_value:
                    by_value[key] = []
                by_value[key].append(contact.variant)
    options: Json = {}
    values: Json = {}
    conflicts: list[str] = []
    for field in field_names():
        choices: list[Json] = []
        only: str = ""
        for key in sorted(list(by_value)):  # noqa: C414 - typed key snapshot
            if key[0] == field:
                only = key[1]
                choices.append({"value": only, "variants": by_value[key]})
        options[field] = choices
        if len(choices) > 1:
            conflicts.append(field)
        else:
            values[field] = only
    reused: list[Json] = []
    for identity in identities:  # noqa: PLC0206
        if len(identities[identity]) > 1:
            reused.append({"source": identity[0], "id": identity[1], "variants": identities[identity]})
    return {
        "id": digest(sorted(variants)),
        "members": references,
        "values": values,
        "options": options,
        "conflicting_fields": conflicts,
        "reused_identities": reused,
        "review": len(conflicts) > 0 or len(reused) > 0,
    }
