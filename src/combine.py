"""Combine per-scenario JSONL files into aggregate dataset files."""

from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from pathlib import Path

from common import load_config, project_path, read_jsonl, stable_hash, write_jsonl
from generator.scenario import Scenario, discover_scenarios, filter_scenarios


COMBINED_NAMES = {
    "single_turn": "single_turn.jsonl",
    "clarification": "clarification.jsonl",
    "no_tool": "no_tool.jsonl",
    "multi_turn": "multi_turn.jsonl",
}


def read_scenario_rows(scenario: Scenario) -> list[dict]:
    """Read generated rows for a scenario output file."""
    return read_jsonl(scenario.output_file)


def dedupe_rows(rows: list[dict]) -> list[dict]:
    """Remove duplicate rows using a stable hash."""
    seen: set[str] = set()
    unique: list[dict] = []
    for row in rows:
        row_hash = stable_hash(row)
        if row_hash in seen:
            continue
        seen.add(row_hash)
        unique.append(row)
    return unique


def combine_scenarios(
    scenarios: list[Scenario], combined_dir: str | Path
) -> dict[str, Path]:
    """Combine scenario rows by sample type and write aggregate files."""
    grouped: dict[str, list[dict]] = defaultdict(list)
    for scenario in scenarios:
        grouped[scenario.type].extend(read_scenario_rows(scenario))

    outputs: dict[str, Path] = {}
    final_rows: list[dict] = []
    for sample_type, rows in grouped.items():
        unique = dedupe_rows(rows)
        final_rows.extend(unique)
        output_name = COMBINED_NAMES.get(sample_type, f"{sample_type}.jsonl")
        output_path = project_path(combined_dir) / output_name
        write_jsonl(output_path, unique)
        outputs[sample_type] = output_path

    final_path = project_path(combined_dir) / "final_dataset.jsonl"
    write_jsonl(final_path, dedupe_rows(final_rows))
    outputs["final_dataset"] = final_path
    return outputs


def run_combine(args: argparse.Namespace) -> None:
    """Run the combine command for selected scenarios."""
    config = load_config(args.config)
    scenarios = filter_scenarios(
        discover_scenarios(config["paths"]["scenarios"]),
        args.type,
        args.tool,
        args.scenario,
    )
    outputs = combine_scenarios(scenarios, config["paths"]["combined"])
    for sample_type, path in outputs.items():
        print(f"{sample_type}: {path}")


def list_outputs(args: argparse.Namespace) -> None:
    """List known scenario output files."""
    config = load_config(args.config)
    scenarios = discover_scenarios(config["paths"]["scenarios"])
    for scenario in scenarios:
        print(f"{scenario.type}\t{scenario.id}\t{scenario.output_file}")


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI parser for combining scenario outputs."""
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command")

    run = subparsers.add_parser("run", help="Combine scenario outputs")
    run.add_argument("--config", default="config/settings.yaml")
    run.add_argument(
        "--type",
        choices=["single_turn", "clarification", "no_tool", "multi_turn", "all"],
        default="all",
    )
    run.add_argument("--tool", default=None)
    run.add_argument("--scenario", default=None)
    run.set_defaults(func=run_combine)

    list_cmd = subparsers.add_parser("list", help="List scenario output files")
    list_cmd.add_argument("--config", default="config/settings.yaml")
    list_cmd.set_defaults(func=list_outputs)
    return parser


def main() -> None:
    """Parse CLI arguments and dispatch combine commands."""
    parser = build_parser()
    argv = sys.argv[1:]
    if not argv or argv[0] not in {"run", "list"}:
        argv = ["run", *argv]
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
