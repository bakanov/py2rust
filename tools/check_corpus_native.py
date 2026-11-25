"""Check handwritten baselines on varied jobs beyond their timed workload shapes."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from unittest.mock import patch

from assess_corpus_speed import SELECTED
from corpus_checks import (
    access_log,
    automation_language,
    autocomplete,
    bmp_thumbnails,
    circuit_calculator,
    code_metrics,
    cron_explorer,
    csv_json,
    csv_join,
    huffman,
    json_patch,
    log_redactor,
    lru_cache,
    package_resolver,
    population_simulator,
    ppm_filters,
    png_inspector,
    regex_rewrite,
    route_planner,
    scheduler_simulator,
    source_outline,
    sprite_atlas,
    syntax_highlighter,
    telemetry_analyzer,
    terminal_dashboard,
    terrain_routes,
    text_patch,
    warehouse_simulator,
    wav_analyzer,
    zip_validator,
)
from corpus_checks.common import Application

IDENTIFIERS = [
    "041",
    "044",
    "045",
    "051",
    "055",
    "061",
    "065",
    "068",
    "071",
    "077",
    "078",
    "079",
    "080",
    "082",
    "088",
    "089",
    "095",
    "096",
    "100",
    "104",
    "105",
    "109",
    "110",
    "111",
    "112",
    "113",
    "114",
    "115",
    "117",
    "118",
]


class CountedApplication(Application):
    jobs: int = 0

    def run(self, directory: Path, settings: dict[str, str], timeout: int = 20) -> subprocess.CompletedProcess:
        self.jobs += 1
        return super().run(directory, settings, timeout)


def check(native: Path, output: Path, identifiers: list[str]) -> None:
    output.mkdir(parents=True, exist_ok=False)
    records = []

    def application(identifier: str) -> Application:
        return Application([str(native / identifier / "native-program")], "rust")

    if "068" in identifiers:
        for index, data in enumerate([b"", b"x" * 10000, b"ab" * 2000, bytes(range(37)) * 100]):
            huffman.success(application("068"), huffman.fixture(output / "068", str(index), data))
        records.append({"id": "068", "checked_jobs": 4, "cases": "empty, single symbol, two symbols, 37 symbols"})
    if "096" in identifiers:
        for budget in [1, 1000]:
            root = output / "096" / str(budget)
            config = package_resolver.fixture(root, max_steps=budget)
            package_resolver.run(application("096"), root, config)
        records.append(
            {"id": "096", "checked_jobs": 2, "cases": "default dependency graph, budget exhausted and resolved"}
        )
    if "100" in identifiers:
        for index, (before, after) in enumerate(
            [(b"", b""), (b"A\r\nB\rC", "A\r\n世界\rC".encode()), (b"X\nY\nX\n", b"Y\nX\nY\n")]
        ):
            root = output / "100" / str(index)
            config = text_patch.fixture(root, before, after, context=index)
            text_patch.run(application("100"), root, config, after)
        records.append(
            {"id": "100", "checked_jobs": 3, "cases": "empty, Unicode/mixed line endings, ambiguous LCS ties"}
        )
    if "104" in identifiers:
        root = output / "104"
        config = circuit_calculator.fixture(root)
        circuit_calculator.run(application("104"), root, config)
        records.append(
            {
                "id": "104",
                "checked_jobs": 1,
                "cases": "16 reference circuits including opens, shorts and extreme scales",
            }
        )
    if "105" in identifiers:
        root = output / "105"
        config = telemetry_analyzer.fixture(root)
        telemetry_analyzer.run(application("105"), root, config)
        records.append(
            {
                "id": "105",
                "checked_jobs": 1,
                "cases": "eight reference series including gaps, cancellation and timestamp offsets",
            }
        )
    if "071" in identifiers:
        rejected = [
            b"\xff",
            b"tab\t",
            b"bad format",
            access_log.line(timestamp="31/Feb/2026:10:00:00 +0000"),
            access_log.line(status="600"),
            access_log.line(size="9223372036854775808"),
            access_log.line(size="0" * 4097),
            access_log.line() + b"\r",
        ]
        cases = [
            ({}, {"start": None, "end": None, "top": 0}),
            (access_log.sample(), {}),
            ({"rejected": b"\n".join(rejected)}, {"start": None, "end": None}),
            (
                {
                    "empty": b"",
                    "ties": b"\n".join(
                        access_log.line(target=target, size="-") for target in ["/z", "/a", "/世界", "/a"]
                    ),
                },
                {"top": 1},
            ),
        ]
        for index, (inputs, settings) in enumerate(cases):
            for mode in ["preview", "write"]:
                case = access_log.fixture(output / "071", f"{index}-{mode}", inputs, **settings)
                access_log.success(application("071"), case, mode)
        records.append(
            {
                "id": "071",
                "checked_jobs": 8,
                "cases": "preview/write: empty sources, UTC/Unicode sample, malformed reasons, ranking ties",
            }
        )
    if "078" in identifiers:
        variants = [
            None,
            [{"name": "literal", "pattern": "TODO", "replacement": ""}],
            [{"name": "repeat", "pattern": "[A-Z]{1,4}", "replacement": "世界"}],
        ]
        for index, rules in enumerate(variants):
            case = regex_rewrite.fixture(output / "078" / str(index))
            if rules is not None:
                case.config["rules"] = rules
                regex_rewrite.save(case)
            before = regex_rewrite.snapshot(case.directory)
            expected, _ = regex_rewrite.oracle(case)
            assert regex_rewrite.invoke(application("078"), case, "preview") == expected
            assert regex_rewrite.snapshot(case.directory) == before
        invalid = ["a*", "[a&&b]", "a++", "[", "(" * 33 + ")" * 33]
        for index, pattern in enumerate(invalid):
            case = regex_rewrite.fixture(output / "078" / f"invalid-{index}")
            case.config["rules"] = [{"name": "invalid", "pattern": pattern, "replacement": "x"}]
            regex_rewrite.save(case)
            before = regex_rewrite.snapshot(case.directory)
            regex_rewrite.invoke(application("078"), case, "preview", success=False)
            assert regex_rewrite.snapshot(case.directory) == before
        records.append(
            {
                "id": "078",
                "checked_jobs": 8,
                "cases": "preview anchors, literal replacements, Unicode, empty replacements, five invalid patterns; unchanged files and metadata",
            }
        )
    if "110" in identifiers:
        details = population_simulator.semantics(application("110"), output / "110")
        records.append(
            {
                "id": "110",
                "checked_jobs": 13,
                "cases": "RK4 closed-form comparison, refinement, zero/constant/equilibrium populations, escaped SVG, archive replay",
                "details": details,
            }
        )
    if "112" in identifiers:
        details = wav_analyzer.semantics(application("112"), output / "112")
        records.append(
            {
                "id": "112",
                "checked_jobs": 23,
                "cases": "RIFF layouts, empty audio, exact rounding and clipping, all 65536 signed16 values under five gains, archive replay",
                "details": details,
            }
        )
    if "117" in identifiers:
        static = terminal_dashboard.semantics(application("117"), output / "117" / "static")
        interactive = terminal_dashboard.interactive(application("117"), output / "117" / "interactive")
        records.append(
            {
                "id": "117",
                "checked_jobs": 79,
                "cases": "69 Unicode/static/replay jobs, six live PTY processes and four replay jobs; resize, snapshot recovery, plain terminals and signal cleanup",
                "details": {"static": static, "interactive": interactive},
            }
        )
    if "111" in identifiers:
        valid = png_inspector.semantics(application("111"), output / "111" / "valid")
        malformed = png_inspector.malformed(application("111"), output / "111" / "malformed")
        jobs = (
            3
            + valid["metadata_cases"]
            + 2 * malformed["structural_mutations_replayed"]
            + malformed["metadata_diagnostics"]
            + malformed["all_proper_prefixes"]
        )
        records.append(
            {
                "id": "111",
                "checked_jobs": jobs,
                "cases": "PNG metadata, Latin1/UTF8, exact malformed diagnostics, structural replay, every truncated prefix",
                "details": {"valid": valid, "malformed": malformed},
            }
        )
    if "113" in identifiers:
        app = CountedApplication([str(native / "113" / "native-program")], "rust")
        details = {
            "semantics": bmp_thumbnails.semantics(app, output / "113" / "semantics"),
            "generated": bmp_thumbnails.generated(app, output / "113" / "generated"),
            "malformed": bmp_thumbnails.malformed(app, output / "113" / "malformed"),
            "invalid": bmp_thumbnails.invalid(app, output / "113" / "invalid"),
        }
        records.append(
            {
                "id": "113",
                "checked_jobs": app.jobs,
                "cases": "BMP headers, orientation, stride, profiles, exact pixels and HTML, generated layouts, rebuild/retile/replay, malformed bitmaps and invalid/tampered archives",
                "details": details,
            }
        )
    if "114" in identifiers:

        app = CountedApplication([str(native / "114" / "native-program")], "rust")
        details = {
            "semantics": ppm_filters.semantics(app, output / "114" / "semantics"),
            "generated": ppm_filters.generated(app, output / "114" / "generated"),
            "malformed": ppm_filters.malformed(app, output / "114" / "malformed"),
            "invalid": ppm_filters.invalid(app, output / "114" / "invalid"),
        }
        records.append(
            {
                "id": "114",
                "checked_jobs": app.jobs,
                "cases": "P6 depths, all u16 samples, exact histograms/CSV/SVG, archive replay, generated crop/invert/threshold properties, malformed images and invalid requests/archives",
                "details": details,
            }
        )
    if "118" in identifiers:
        app = CountedApplication([str(native / "118" / "native-program")], "rust")
        details = {
            "semantics": zip_validator.semantics(app, output / "118" / "semantics"),
            "generated": zip_validator.generated(app, output / "118" / "generated"),
            "malformed": zip_validator.malformed(app, output / "118" / "malformed"),
            "invalid": zip_validator.invalid(app, output / "118" / "invalid"),
            "structure": zip_validator.structure(app, output / "118" / "structure"),
        }
        records.append(
            {
                "id": "118",
                "checked_jobs": app.jobs,
                "cases": "ZIP32 payload oracle, stored/deflate/descriptors, Unicode paths, generated edit/replay/restore, malformed inputs, exact forensic diagnostics, overlap and CRC-equals-signature descriptors",
                "details": details,
            }
        )
    if "115" in identifiers:
        app = CountedApplication([str(native / "115" / "native-program")], "rust")
        details = {
            "semantics": sprite_atlas.semantics(app, output / "115" / "semantics"),
            "generated": sprite_atlas.generated(app, output / "115" / "generated"),
            "malformed": sprite_atlas.malformed(app, output / "115" / "malformed"),
            "invalid": sprite_atlas.invalid(app, output / "115" / "invalid"),
        }
        records.append(
            {
                "id": "115",
                "checked_jobs": app.jobs,
                "cases": "P6 sprite depths, shelf order and padding, exact atlas extraction and SVG, generated repacking/replay, malformed images and invalid/tampered archives",
                "details": details,
            }
        )
    if "079" in identifiers:
        app = CountedApplication([str(native / "079" / "native-program")], "rust")
        details = automation_language.check(app, output / "079")
        # Boundary programs use their own prlimit-wrapped Application instance.
        records.append(
            {
                "id": "079",
                "checked_jobs": app.jobs + details["boundary_cases"],
                "cases": "independent interpreter oracle, checked i64 arithmetic, lexical scope, partial error unwinding, AST/source coordinates, 256 MiB boundary runs and no-write invalid jobs",
                "details": details,
            }
        )
    if "080" in identifiers:
        app = CountedApplication([str(native / "080" / "native-program")], "rust")
        details = syntax_highlighter.check(app, output / "080")
        records.append(
            {
                "id": "080",
                "checked_jobs": app.jobs,
                "cases": "independent tokens and Unicode coordinates, safe HTML and links, both themes, byte-identical replay and no-write invalid inputs",
                "details": details,
            }
        )
    if "077" in identifiers:
        app = CountedApplication([str(native / "077" / "native-program")], "rust")
        details = source_outline.check(app, output / "077")
        records.append(
            {
                "id": "077",
                "checked_jobs": app.jobs,
                "cases": "independent CPython AST oracle, nested scopes and cleaned docstrings, import links and ambiguity, complete HTML/replay, invalid sources and preserved existing outputs",
                "details": details,
            }
        )
    if "109" in identifiers:
        app = CountedApplication([str(native / "109" / "native-program")], "rust")
        # Native baselines deliberately omit the application's fault/pause hooks.
        details = {
            "semantics": warehouse_simulator.semantics(app, output / "109" / "semantics"),
            "generated": warehouse_simulator.generated(app, output / "109" / "generated"),
            "invalid": warehouse_simulator.invalid(app, output / "109" / "invalid"),
            "limits": warehouse_simulator.limits(app, output / "109" / "limits"),
            "filesystem": warehouse_simulator.filesystem(app, output / "109" / "filesystem"),
        }
        records.append(
            {
                "id": "109",
                "checked_jobs": app.jobs,
                "cases": "independent warehouse oracle, moves/pushes/undo and blocked reasons, continuation/rewind/restart, Unicode titles, exact trace and tampered archives",
                "details": details,
            }
        )
    if "095" in identifiers:
        app = CountedApplication([str(native / "095" / "native-program")], "rust")
        details = {
            "semantics": code_metrics.semantic_cases(app, output / "095" / "semantics"),
            "invalid": code_metrics.invalid(app, output / "095" / "invalid"),
            "filesystem": code_metrics.filesystem(app, output / "095" / "filesystem"),
            "limits": code_metrics.limits(app, output / "095" / "limits"),
        }
        records.append(
            {
                "id": "095",
                "checked_jobs": app.jobs,
                "cases": "independent AST metrics and HTML oracles, scoped counters, import classification, directory discovery, raw archives, invalid source trees and exact capacity limits",
                "details": details,
            }
        )
    if "061" in identifiers:
        app = CountedApplication([str(native / "061" / "native-program")], "rust")
        directory = output / "061"
        directory.mkdir()
        details = route_planner.check(app, directory)
        records.append(
            {
                "id": "061",
                "checked_jobs": app.jobs,
                "cases": "exhaustive simple-path and cycle oracle, closures, directed finite/cycle witnesses, unreachable sets and invalid graph preservation",
                "details": details,
            }
        )
    if "065" in identifiers:
        app = CountedApplication([str(native / "065" / "native-program")], "rust")
        directory = output / "065"
        details = {
            "scenarios": terrain_routes.scenarios(app, directory / "scenarios"),
            "invalid_inputs": terrain_routes.invalid_inputs(app, directory / "invalid"),
            "limits": terrain_routes.limits(app, directory / "limits"),
            "paths": terrain_routes.paths(app, directory / "paths"),
        }
        records.append(
            {
                "id": "065",
                "checked_jobs": app.jobs,
                "cases": "independent shortest paths, stable search statistics and ASCII overlays, zero costs, exhaustive tiny terrains, export replay, invalid inputs and capacity/path guards",
                "details": details,
            }
        )
    if "082" in identifiers:
        app = CountedApplication([str(native / "082" / "native-program")], "rust")
        details = cron_explorer.check(app, output / "082")
        records.append(
            {
                "id": "082",
                # The maximum-capacity job uses a separate prlimit-wrapped Application.
                "checked_jobs": app.jobs + 1,
                "cases": "independent minute-grid calendar oracle, exact grammar diagnostics, day rules/Sunday alias, century boundaries, truncation proofs, replay and capacity limits",
                "details": details,
            }
        )
    if "088" in identifiers:
        app = CountedApplication([str(native / "088" / "native-program")], "rust")
        directory = output / "088"
        details = {
            "semantics": scheduler_simulator.semantics(app, directory / "semantics"),
            "invalid": scheduler_simulator.invalid(app, directory / "invalid"),
            "capacity": scheduler_simulator.capacity(app, directory / "capacity"),
        }
        records.append(
            {
                "id": "088",
                # Capacity runs one subprocess directly with an address-space limit.
                "checked_jobs": app.jobs + 1,
                "cases": "independent event scanning and trace integrals, phase/worker/FIFO ties, seeded rejection sampling, replay, invalid documents and full capacity",
                "details": details,
            }
        )
    if "089" in identifiers:
        app = CountedApplication([str(native / "089" / "native-program")], "rust")
        directory = output / "089"
        details = {
            "semantics": log_redactor.semantics(app, directory / "semantics"),
            "invalid": log_redactor.invalid(app, directory / "invalid"),
            "capacity": log_redactor.capacity(app, directory / "capacity"),
        }
        records.append(
            {
                "id": "089",
                # Capacity launches one process directly with an address-space limit.
                "checked_jobs": app.jobs + 1,
                "cases": "independent regex/literal oracle, nested paths and counters, phase-only diagnostics, duplicate JSON rejection, expansion bounds and capacity",
                "details": details,
            }
        )
    if "044" in identifiers:
        app = application("044")
        counted_jobs = 0
        original_run = Application.run

        def counted_join_run(
            instance: Application, directory: Path, settings: dict[str, str], timeout: int = 20
        ) -> subprocess.CompletedProcess:
            nonlocal counted_jobs
            counted_jobs += 1
            return original_run(instance, directory, settings, timeout)

        with (
            patch.object(Application, "run", counted_join_run),
            patch.object(csv_join, "check_publication", return_value=0),
        ):
            details = csv_join.check(app, output / "044")
        del details["publication_cases"]
        records.append(
            {
                "id": "044",
                "checked_jobs": counted_jobs,
                "cases": "independent nested-loop oracle, composite keys, stable ordering, duplicate expansion, paths and memory-limited capacities; fault/pause controls excluded",
                "details": details,
            }
        )
    if "041" in identifiers:
        app = application("041")
        counted_jobs = 0
        original_run = Application.run

        def counted_conversion_run(
            instance: Application, directory: Path, settings: dict[str, str], timeout: int = 20
        ) -> subprocess.CompletedProcess:
            nonlocal counted_jobs
            counted_jobs += 1
            return original_run(instance, directory, settings, timeout)

        # Count prlimit-wrapped runs too; fault/pause controls are excluded.
        with (
            patch.object(Application, "run", counted_conversion_run),
            patch.object(csv_json, "check_publication", return_value=0),
        ):
            details = csv_json.check(app, output / "041")
        del details["publication_boundaries"]
        records.append(
            {
                "id": "041",
                "checked_jobs": counted_jobs,
                "cases": "independent CSV/typed-record oracle, both directions, dialects, rejections, paths and memory-limited capacities; fault/pause controls excluded",
                "details": details,
            }
        )
    if "055" in identifiers:
        app = CountedApplication([str(native / "055" / "native-program")], "rust")
        # Native baselines omit injected failure/pause controls.
        with patch.object(autocomplete, "publication", return_value=0):
            details = autocomplete.check(app, output / "055")
        del details["publication_checks"]
        records.append(
            {
                "id": "055",
                "checked_jobs": app.jobs,
                "cases": "independent normalized dictionary oracle, ranking, randomized traces, split replay, invalid states and capacity bounds; fault/pause controls excluded",
                "details": details,
            }
        )
    if "051" in identifiers:
        app = CountedApplication([str(native / "051" / "native-program")], "rust")
        # Native baselines do not implement the application's injected failure/pause controls.
        with patch.object(lru_cache, "publication", return_value=0):
            details = lru_cache.check(app, output / "051")
        del details["publication_checks"]
        records.append(
            {
                "id": "051",
                "checked_jobs": app.jobs,
                "cases": "independent ordered-cache oracle, randomized traces, split replay, numeric values, invalid commands/states and exact capacity bounds; fault/pause controls excluded",
                "details": details,
            }
        )
    if "045" in identifiers:
        app = application("045")
        directory = output / "045"
        counted_jobs = 0
        original_run = Application.run

        def counted_run(
            instance: Application, directory: Path, settings: dict[str, str], timeout: int = 20
        ) -> subprocess.CompletedProcess:
            nonlocal counted_jobs
            counted_jobs += 1
            return original_run(instance, directory, settings, timeout)

        # Includes the suite's separately constructed prlimit-wrapped applications.
        with patch.object(Application, "run", counted_run):
            details = {
                "roundtrips": json_patch.check_roundtrips(app, directory / "roundtrips"),
                "manual": json_patch.check_manual(app, directory / "manual"),
                "rejections": json_patch.check_rejections(app, directory / "rejections"),
                "paths": json_patch.check_paths(app, directory / "paths"),
                "limits": json_patch.check_limits(app, directory / "limits"),
            }
        records.append(
            {
                "id": "045",
                "checked_jobs": counted_jobs,
                "cases": "independent recursive patch oracle, canonical numeric guards, escaped paths, undo and intermediate bounds, invalid/stale patches, path guards and memory-limited capacities",
                "details": details,
            }
        )
    for record in records:
        binary = native / record["id"] / "native-program"
        record["binary_sha256"] = hashlib.sha256(binary.read_bytes()).hexdigest()
    (output / "results.json").write_text(json.dumps(records, indent=2) + "\n")
    print(
        f"Passed {sum(record['checked_jobs'] for record in records)} varied complete jobs against independent corpus oracles."
    )
    return


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--native", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--ids", nargs="+", choices=IDENTIFIERS, default=SELECTED)
    args = parser.parse_args()
    check(args.native.resolve(), args.output.resolve(), args.ids)
    return


if __name__ == "__main__":
    main()
