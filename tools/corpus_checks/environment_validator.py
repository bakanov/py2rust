"""Whole-project validation, independent scalar/dependency expectations and secret-output auditing."""

from __future__ import annotations

import copy
import hashlib
import itertools
import json
import os
import random
import select
import subprocess
from pathlib import Path

from .common import Application
from .environment_fixture import (
    CANARY,
    OTHER,
    canonical,
    chain,
    changed,
    description,
    expected,
    field,
    schema,
)


def save(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2) + "\n")
    return  # noqa: PLR1711


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def fixture(root: Path, document: dict | None = None) -> dict:
    root.mkdir(parents=True, exist_ok=True)
    save(root / "schema.json", schema() if document is None else document)
    config = {"version": 1, "schema": "schema.json", "output": "output"}
    save(root / "settings-job.json", config)
    return config


def environment(app: Application, variables: dict[str, str], settings: dict[str, str] | None = None) -> dict[str, str]:
    env = {name: value for name, value in app.environment({}).items() if not name.startswith(("EV_", "SETTINGS_"))}
    env.update(variables)
    env.update(settings or {})
    return env


def execute(
    app: Application, root: Path, variables: dict[str, str], settings: dict[str, str] | None = None, timeout: int = 15
) -> subprocess.CompletedProcess:
    return subprocess.run(
        app.command,
        cwd=root,
        env=environment(app, variables, settings),
        capture_output=True,
        text=True,
        check=False,
        timeout=timeout,
    )


def secret_free(data: str | bytes, canaries: list[str] | None = None) -> None:
    raw = data.encode() if isinstance(data, str) else data
    for value in [CANARY, OTHER, *(canaries or [])]:
        for encoded in [
            value.encode(),
            json.dumps(value).encode()[1:-1],
            json.dumps(value, ensure_ascii=False).encode()[1:-1],
        ]:
            assert encoded not in raw, ("secret leaked", value)
    return  # noqa: PLR1711


def inspect(root: Path, config: dict, document: dict, variables: dict[str, str]) -> dict:
    output = root / config["output"]
    expected_report = expected(document, variables)
    raw = (output / "report.json").read_bytes()
    assert raw == canonical(expected_report) + b"\n", (root, json.loads(raw), expected_report)
    assert (output / "schema-summary.json").read_bytes() == canonical(description(document)) + b"\n"
    recheck = json.loads((output / "recheck.json").read_bytes())
    schema_path = root / config["schema"]
    assert recheck == {
        "version": 1,
        "schema": str(schema_path.parent.resolve() / schema_path.name),
        "output": "rechecked",
    }
    lines = ["Environment configuration: " + ("valid" if expected_report["valid"] else "invalid")]
    for row in expected_report["fields"]:
        lines.append(
            f"{row['name']} ({row['env']}): {row['status']}, {row['origin']}, " + canonical(row["value"]).decode()
        )
    for diagnostic in expected_report["diagnostics"]:
        lines.append(
            diagnostic["field"]
            + ": "
            + diagnostic["code"]
            + (" (" + diagnostic["dependency"] + ")" if diagnostic["dependency"] is not None else "")
        )
    assert (output / "report.txt").read_text() == "\n".join(lines) + "\n"
    names = {"report.json", "report.txt", "schema-summary.json", "recheck.json"}
    manifest = json.loads((output / "manifest.json").read_bytes())
    assert set(manifest) == names and {p.name for p in output.iterdir()} == names | {"manifest.json"}
    for name, row in manifest.items():
        data = (output / name).read_bytes()
        assert row == {"bytes": len(data), "sha256": digest(data)}
    for path in output.iterdir():
        secret_free(path.read_bytes())
    return expected_report


def run(app: Application, root: Path, config: dict, document: dict, variables: dict[str, str]) -> dict:
    result = execute(app, root, variables)
    wanted = expected(document, variables)
    assert result.returncode == (0 if wanted["valid"] else 1) and not result.stderr, (root, result)
    assert result.stdout == canonical(wanted["summary"]).decode() + "\n"
    secret_free(result.stdout + result.stderr)
    return inspect(root, config, document, variables)


def consume(app: Application, bundle: Path, document: dict, variables: dict[str, str]) -> tuple[dict, Path]:
    request = json.loads((bundle / "recheck.json").read_bytes())
    save(bundle / "settings-job.json", request)
    return run(app, bundle, request, document, variables), bundle / request["output"]


def reject(app: Application, root: Path, variables: dict[str, str] | None = None) -> None:
    result = execute(app, root, variables or {})
    assert result.returncode == 2 and not result.stdout and "configuration request rejected" in result.stderr, (
        root,
        result,
    )
    secret_free(result.stdout + result.stderr)
    assert not (root / "output").exists() and not list(root.glob(".settings-*"))
    return  # noqa: PLR1711


def semantics(app: Application, root: Path) -> dict:
    hand = schema()
    scenarios = [
        {},
        {"EV_REQUIRED": '"configured"'},
        {"EV_REQUIRED": '"configured"', "EV_TLS": "false"},
        {"EV_REQUIRED": '"configured"', "EV_TLS": '"not boolean"'},
        {"EV_REQUIRED": '"configured"', "EV_TOKEN": json.dumps(OTHER)},
        {"EV_REQUIRED": '"configured"', "EV_TOKEN": json.dumps(CANARY), "EV_CONTACT": "null"},
        {"EV_REQUIRED": '"configured"', "EV_OPTIONAL_SECRET": json.dumps(OTHER)},
        {"EV_REQUIRED": '"configured"', "EV_HOST": '"世界😀"', "EV_PORT": "65535", "EV_RATIO": "1e-3"},
        {"EV_REQUIRED": '"configured"', "EV_TOKEN": "", "EV_PORT": "0", "EV_RATIO": "2", "EV_LEVEL": '"other"'},
    ]
    for index, variables in enumerate(scenarios):
        work = root / f"hand-{index}"
        config = fixture(work, hand)
        report = run(app, work, config, hand, variables)
        if index == 0:
            assert report["summary"] == {
                "fields": 11,
                "valid": 8,
                "missing": 3,
                "invalid": 0,
                "defaulted": 8,
                "errors": 1,
            }
        if index == 2:
            assert [(row["field"], row["code"]) for row in report["diagnostics"]] == [
                ("feature", "dependency"),
                ("token", "dependency"),
            ]
    work = root / "recheck"
    config = fixture(work, hand)
    first = run(app, work, config, hand, scenarios[1])
    second, output = consume(app, work / "output", hand, scenarios[2])
    third, _ = consume(app, output, hand, scenarios[1])
    assert first == third and second != first
    shuffled = copy.deepcopy(hand)
    shuffled["fields"].reverse()
    work = root / "schema-order"
    assert run(app, work, fixture(work, shuffled), shuffled, scenarios[1]) == first
    deep = chain(32)
    work = root / "dependency-chain"
    report = run(app, work, fixture(work, deep), deep, {"EV_F0": "99"})
    assert report["summary"]["invalid"] == 31 and report["summary"]["valid"] == 1
    fan = {
        "version": 1,
        "fields": [field("base" + str(i), "bool", default=True) for i in range(8)]
        + [
            field("leaf", "bool", default=True, requires=[{"field": "base" + str(i), "equals": True} for i in range(8)])
        ],
    }
    work = root / "fan-in"
    variables = {"EV_BASE" + str(i): "false" for i in range(8)}
    report = run(app, work, fixture(work, fan), fan, variables)
    assert report["summary"]["errors"] == 8 and report["summary"]["invalid"] == 1
    combinations = 0
    for required, has_default, nullable in itertools.product([False, True], repeat=3):
        rule = field("value", required=required, nullable=nullable)
        if has_default:
            rule["default"] = None if nullable else "fallback"
        document = {"version": 1, "fields": [rule]}
        for variables in [{}, {"EV_VALUE": "null"}, {"EV_VALUE": '""'}]:
            work = root / f"presence-{combinations}"
            run(app, work, fixture(work, document), document, variables)
            combinations += 1
    return {
        "hand_scenarios": len(scenarios),
        "presence_default_nullable_cases": combinations,
        "external_schema_recheck": True,
        "schema_order_independent": True,
        "dependency_chain_fields": 32,
        "fan_in_prerequisites": 8,
        "cascade_and_diagnostic_order": True,
    }


def scalars(app: Application, root: Path) -> dict:
    raw_values = [
        "null",
        "true",
        "false",
        "0",
        "-1",
        "1",
        "1.0",
        "1e0",
        "-0.0",
        "0.1",
        '""',
        '"abc"',
        '"世界😀"',
        '"a\\u0000b"',
        "[]",
        "{}",
        '"\\ud800"',
        "[1,2]",
        "9223372036854775807",
        "-9223372036854775808",
        "9223372036854775808",
        "NaN",
        "Infinity",
        "-Infinity",
        "1e999",
        "",
        " ",
        "01",
        "true false",
        '{"a":1,"a":1}',
    ]
    rules = [
        field("string", "string"),
        field("integer", "integer"),
        field("number", "number"),
        field("boolean", "bool"),
        field("nullable", "string", nullable=True),
        field("enum", "number", nullable=True, choices=[None, 1, 2.5]),
        field("bounded", "number", minimum=-1, maximum=1),
        field("length", "string", min_length=1, max_length=3),
    ]
    document = {"version": 1, "fields": rules}
    count = 0
    for index, value in enumerate(raw_values):
        variables = {row["env"]: value for row in rules}
        work = root / str(index)
        run(app, work, fixture(work, document), document, variables)
        count += len(rules)
    rng = random.Random(990099)
    generated = 0
    for index in range(12):
        rows = []
        variables = {}
        for number in range(24):
            kind = rng.choice(["string", "integer", "number", "bool"])
            row = field("f" + str(number), kind, nullable=rng.choice([True, False]))
            if kind == "string":
                row.update(min_length=1, max_length=8)
            elif kind in ["integer", "number"]:
                row.update(minimum=-8, maximum=8)
            rows.append(row)
            values = [
                None,
                True,
                False,
                rng.randint(-20, 20),
                rng.uniform(-20, 20),
                "世界" * rng.randrange(10),
                [1],
                {"a": 1},
            ]
            variables[row["env"]] = json.dumps(rng.choice(values), ensure_ascii=False)
        document = {"version": 1, "fields": rows}
        work = root / f"generated-{index}"
        run(app, work, fixture(work, document), document, variables)
        generated += len(rows)
    # Integer/float boundary comparison must not round large integers to binary64.
    document = {
        "version": 1,
        "fields": [field("x", "number", maximum=9007199254740992.0), field("y", "integer", minimum=9007199254740993)],
    }
    work = root / "exact-mixed-numbers"
    variables = {"EV_X": "9007199254740993", "EV_Y": "9007199254740992"}
    report = run(app, work, fixture(work, document), document, variables)
    assert [row["code"] for row in report["diagnostics"]] == ["range", "range"]
    return {
        "scalar_type_and_encoding_cases": count,
        "generated_fields": generated,
        "exact_large_integer_and_float_bounds": True,
    }


def secrets(app: Application, root: Path) -> dict:
    cases = [
        (field("secret", secret=True), json.dumps(CANARY)),
        (field("secret", secret=True), '"' + CANARY),
        (field("secret", "integer", secret=True), json.dumps(CANARY)),
        (field("secret", secret=True, max_length=2), json.dumps(CANARY)),
        (field("secret", secret=True, choices=[OTHER]), json.dumps(CANARY)),
        (field("secret", secret=True), json.dumps(CANARY * 200)),
        (field("secret", secret=True, nullable=True), "null"),
        (field("secret", secret=True, required=True), None),
        (field("secret", secret=True, default=CANARY), None),
        (field("secret", "integer", secret=True, minimum=900000000, maximum=999999999), "123456789"),
        (field("secret", "number", secret=True, default=0.3125), None),
        (field("secret", "bool", secret=True, default=True), None),
    ]
    for index, (row, raw) in enumerate(cases):
        document = {"version": 1, "fields": [row]}
        variables = {} if raw is None else {row["env"]: raw}
        work = root / str(index)
        report = run(app, work, fixture(work, document), document, variables)
        assert report["fields"][0]["value"] == "<redacted>"
        for path in (work / "output").iterdir():
            secret_free(path.read_bytes(), ["123456789"] if index == 9 else [])
    # Malformed schemas containing secret defaults, choices and predicates must only emit a static fatal message.
    malformed = [
        changed(schema(), "token", default={"canary": CANARY}),
        changed(schema(), "token", choices=[CANARY, CANARY]),
        changed(schema(), "feature", requires=[{"field": "token", "equals": CANARY + "wrong"}]),
    ]
    for index, document in enumerate(malformed):
        work = root / f"fatal-{index}"
        fixture(work, document)
        reject(app, work)
    return {
        "secret_value_and_error_paths": len(cases),
        "secret_schema_failures": len(malformed),
        "all_exported_bytes_stdout_and_stderr_scanned": True,
        "defaults_choices_and_dependency_values_omitted_from_summary": True,
    }


def invalid(app: Application, root: Path) -> dict:
    schemas = [
        [],
        {},
        {"version": 2, "fields": []},
        {"version": True, "fields": []},
        {"version": 1, "fields": []},
        {"version": 1, "fields": [field("f" + str(i)) for i in range(33)]},
        {"version": 1, "fields": [field("x"), field("x")]},
        {"version": 1, "fields": [field("x"), field("y", env="EV_X")]},
        {"version": 1, "fields": [field("x")], "extra": 1},
    ]
    mutations = [
        ("name", ""),
        ("name", "1bad"),
        ("name", "世界"),
        ("name", "a" * 33),
        ("env", "lowercase"),
        ("env", "A=B"),
        ("env", ""),
        ("env", "A" * 65),
        ("env", "SETTINGS_CONFIG"),
        ("type", "object"),
        ("type", True),
        ("required", 1),
        ("secret", "yes"),
        ("nullable", None),
        ("min_length", -1),
        ("max_length", 1025),
        ("min_length", True),
        ("max_length", 0.5),
        ("choices", []),
        ("choices", ["a", "a"]),
        ("choices", ["a"] * 17),
        ("choices", [True]),
        ("default", None),
        ("default", []),
        ("default", CANARY * 100),
        ("minimum", 1),
        ("maximum", 2),
        ("requires", {}),
        ("requires", [{}]),
        ("extra", CANARY),
    ]
    for key, value in mutations:
        schemas.append({"version": 1, "fields": [dict(field("x"), **{key: value})]})
    for kind, options in [
        ("integer", {"minimum": 1.0}),
        ("integer", {"maximum": True}),
        ("number", {"minimum": None}),
        ("number", {"minimum": "zero"}),
        ("number", {"minimum": 2, "maximum": 1}),
        ("bool", {"min_length": 0}),
        ("string", {"min_length": 2, "max_length": 1}),
        ("number", {"choices": [1, 1.0]}),
        ("integer", {"default": 1.0}),
        ("integer", {"minimum": 2, "default": 1}),
        ("string", {"choices": ["a"], "default": "b"}),
        ("string", {"nullable": True, "choices": ["a"], "default": None}),
    ]:
        schemas.append({"version": 1, "fields": [field("x", kind, **options)]})
    for rules in [
        [{"field": "missing", "equals": "x"}],
        [{"field": "x", "equals": "x"}],
        [{"field": "y", "equals": 1}],
        [{"field": "y", "equals": "x"}] * 2,
        [{"field": "y", "equals": "x", "extra": CANARY}],
        [{"field": "y"}],
        [{"field": "y", "equals": "x"}] * 9,
    ]:
        schemas.append({"version": 1, "fields": [field("x", requires=rules), field("y")]})
    cyclic = chain(4)
    next(row for row in cyclic["fields"] if row["name"] == "f0")["requires"] = [{"field": "f3", "equals": 3}]
    schemas.append(cyclic)
    for index, document in enumerate(schemas):
        work = root / f"schema-{index}"
        fixture(work, document)
        reject(app, work)
    requests = [
        ("version", True),
        ("version", 2),
        ("schema", ""),
        ("schema", "\0"),
        ("output", ""),
        ("output", "\0"),
        ("extra", CANARY),
    ]
    for index, (name, value) in enumerate(requests):
        work = root / f"request-{index}"
        config = fixture(work)
        config[name] = value
        save(work / "settings-job.json", config)
        reject(app, work)
    encodings = [
        b"{",
        b'{"version":1,"version":1}',
        b'{"x":NaN}',
        b"\xff",
        b'"\\ud800"',
        b'{"x":9223372036854775808}',
        b'{"x":1e999}',
    ]
    for index, (name, raw) in enumerate(itertools.product(["settings-job.json", "schema.json"], encodings)):
        work = root / f"encoding-{index}"
        fixture(work)
        (work / name).write_bytes(raw)
        reject(app, work)
    return {"invalid_schemas": len(schemas), "invalid_requests": len(requests), "invalid_document_encodings": 14}


def limits(app: Application, root: Path) -> dict:
    rows = [field("f" + str(i), "string", default="x" * 1024) for i in range(32)]
    rows[0].update(name="A" * 32, env="Z" * 64)
    document = {"version": 1, "fields": rows}
    work = root / "field-and-string-capacity"
    result = run(app, work, fixture(work, document), document, {})
    assert result["summary"]["valid"] == 32
    document = {"version": 1, "fields": [field("value", "integer", choices=list(range(16)), default=15)]}
    work = root / "choice-capacity"
    run(app, work, fixture(work, document), document, {})
    document = {"version": 1, "fields": [field("value")]}
    work = root / "raw-4096"
    variables = {"EV_VALUE": json.dumps("x" * 1024).ljust(4096)}
    run(app, work, fixture(work, document), document, variables)
    work = root / "raw-4097"
    variables["EV_VALUE"] += " "
    report = run(app, work, fixture(work, document), document, variables)
    assert report["diagnostics"][0]["code"] == "size"
    document = {"version": 1, "fields": [field("f" + str(i), "integer") for i in range(32)]}
    variables = {row["env"]: "1".ljust(2048) for row in document["fields"]}
    work = root / "aggregate-65536"
    run(app, work, fixture(work, document), document, variables)
    work = root / "aggregate-with-absent-fields"
    partial = {row["env"]: "1".ljust(4096) for row in document["fields"][:16]}
    report = run(app, work, fixture(work, document), document, partial)
    assert report["summary"]["valid"] == report["summary"]["missing"] == 16
    work = root / "aggregate-65537"
    fixture(work, document)
    variables["EV_F0"] += " "
    reject(app, work, variables)
    work = root / "document-exact-bytes"
    document = schema()
    config = fixture(work, document)
    for name, limit in [("settings-job.json", 65536), ("schema.json", 262144)]:
        path = work / name
        path.write_bytes(path.read_bytes().ljust(limit, b" "))
    run(app, work, config, document, {})
    for name, limit in [("settings-job.json", 65536), ("schema.json", 262144)]:
        work = root / ("oversize-" + name)
        fixture(work)
        path = work / name
        path.write_bytes(path.read_bytes().ljust(limit + 1, b" "))
        reject(app, work)
    return {
        "fields": 32,
        "name_characters": 32,
        "environment_name_characters": 64,
        "string_characters": 1024,
        "choices": 16,
        "environment_value_bytes": 4096,
        "environment_total_bytes": 65536,
        "absent_fields_excluded_from_byte_budget": True,
        "request_bytes": 65536,
        "schema_bytes": 262144,
        "over_boundaries": 4,
    }


def publication(app: Application, root: Path) -> dict:
    document = schema()
    variables = {"EV_REQUIRED": json.dumps("configured"), "EV_TOKEN": json.dumps(CANARY)}
    for stage in ["staged", "published"]:
        work = root / (stage + "-fault")
        config = fixture(work, document)
        result = execute(app, work, variables, {"SETTINGS_FAULT": stage})
        assert result.returncode == 2 and not result.stdout
        secret_free(result.stderr)
        assert not list(work.glob(".settings-*"))
        assert (work / "output").exists() == (stage == "published")
        if stage == "published":
            inspect(work, config, document, variables)
    for mutation in ["request", "schema", "competitor", "kill-staged", "kill-published"]:
        work = root / mutation
        config = fixture(work, document)
        release = work / "release"
        stage = "published" if mutation == "kill-published" else "staged"
        process = subprocess.Popen(
            app.command,
            cwd=work,
            env=environment(
                app, variables, {"SETTINGS_PAUSE": stage, "SETTINGS_RELEASE": str(release), "PYTHONUNBUFFERED": "1"}
            ),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        try:
            assert select.select([process.stdout], [], [], 5)[0]
            assert process.stdout.readline() == "PAUSED " + stage + "\n"
            # Even unpublished staging contains only public/redacted artifacts.
            for directory in [work / "output", *work.glob(".settings-*")]:
                if directory.exists():
                    for path in directory.iterdir():
                        secret_free(path.read_bytes())
            if mutation.startswith("kill"):
                process.kill()
                stdout, stderr = process.communicate(timeout=5)
                secret_free(stdout + stderr)
                assert (work / "output").exists() == (stage == "published")
                if stage == "published":
                    inspect(work, config, document, variables)
                else:
                    assert len(list(work.glob(".settings-*"))) == 1
            else:
                if mutation == "competitor":
                    (work / "output").mkdir()
                    (work / "output/keep").write_text("original")
                else:
                    name = "settings-job.json" if mutation == "request" else "schema.json"
                    with (work / name).open("ab") as stream:
                        stream.write(b" ")
                release.touch()
                stdout, stderr = process.communicate(timeout=5)
                assert process.returncode == 2 and not stdout and "configuration request rejected" in stderr
                secret_free(stderr)
                assert not list(work.glob(".settings-*"))
                if mutation == "competitor":
                    assert (work / "output/keep").read_text() == "original"
                else:
                    assert not (work / "output").exists()
        finally:
            if process.poll() is None:
                process.kill()
                process.wait()
    return {
        "caught_faults": 2,
        "input_and_output_races": 3,
        "hard_kills": 2,
        "unpublished_staging_secret_scan": True,
        "complete_or_absent_final_directory": True,
    }


def filesystem(app: Application, root: Path) -> dict:
    count = 0
    for name, kind in itertools.product(
        ["settings-job.json", "schema.json"], ["symlink", "hardlink", "fifo", "directory", "unreadable"]
    ):
        work = root / str(count)
        fixture(work)
        path = work / name
        raw = path.read_bytes()
        path.unlink()
        target = work / "target"
        target.write_bytes(raw)
        if kind == "symlink":
            path.symlink_to(target)
        elif kind == "hardlink":
            os.link(target, path)
        elif kind == "fifo":
            os.mkfifo(path)
        elif kind == "directory":
            path.mkdir()
        else:
            path.write_bytes(raw)
            path.chmod(0)
        try:
            reject(app, work)
            assert target.read_bytes() == raw
        finally:
            if kind == "unreadable":
                path.chmod(0o600)
        count += 1
    for kind in ["file", "directory", "symlink", "permission"]:
        work = root / str(count)
        fixture(work)
        target = work / "output"
        if kind == "file":
            target.write_text("keep")
        elif kind == "directory":
            target.mkdir()
        elif kind == "symlink":
            target.symlink_to(work / "schema.json")
        else:
            work.chmod(0o500)
        try:
            result = execute(app, work, {})
            assert result.returncode == 2 and not result.stdout
            secret_free(result.stderr)
            if kind == "file":
                assert target.read_text() == "keep"
            elif kind == "directory":
                assert not list(target.iterdir())
            elif kind == "symlink":
                assert target.is_symlink()
            else:
                assert not target.exists()
        finally:
            work.chmod(0o700)
        count += 1
    return {"guarded_paths_and_permissions": count}


def check(app: Application, directory: Path) -> dict:
    observations = {}
    for name, test in [
        ("semantics", semantics),
        ("scalars", scalars),
        ("secrets", secrets),
        ("invalid", invalid),
        ("limits", limits),
        ("publication", publication),
        ("filesystem", filesystem),
    ]:
        observations[name] = test(app, directory / name)
        print(app.engine + " environment " + name + ": passed", flush=True)
    return observations
