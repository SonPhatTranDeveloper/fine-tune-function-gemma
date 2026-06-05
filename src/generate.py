"""Generate synthetic samples from scenario packs."""

from __future__ import annotations

import argparse
import json
import random
import sys
from typing import Any

from common import fake_context, load_config, read_text, render_template, write_jsonl
from generator.claude_client import ClaudeJsonGenerator
from generator.scenario import (
    Scenario,
    discover_scenarios,
    filter_scenarios,
    require_one_scenario,
)
from tools.banking import tool_schemas
from validation.rules import validate_sample

AMBIGUOUS_BENEFICIARY_SCENARIO = "ambiguous_beneficiary_account_then_transfer"


def enrich_sample(sample: dict[str, Any], scenario: Scenario) -> dict[str, Any]:
    """Attach consistent scenario metadata to a generated sample."""
    sample.setdefault("scenario_id", scenario.id)
    sample.setdefault("sample_type", scenario.type)
    if scenario.tool:
        sample.setdefault("tool", scenario.tool)
    if scenario.type == "multi_turn":
        sample.setdefault("conversation_type", "multi_turn")
        sample.setdefault("chain_type", scenario.id)
    return sample


def beneficiary_key(beneficiary: dict[str, Any]) -> tuple[str, str, str]:
    """Return a stable key for beneficiary list shuffling."""
    return (
        str(beneficiary.get("contact_name", "")),
        str(beneficiary.get("to_account", "")),
        str(beneficiary.get("bank_name", "")).upper(),
    )


def shuffle_ambiguous_beneficiary_lookup(sample: dict[str, Any]) -> dict[str, Any]:
    """Shuffle saved-beneficiary lookups without putting matches first."""
    if sample.get("scenario_id") != AMBIGUOUS_BENEFICIARY_SCENARIO:
        return sample

    beneficiary_turn: dict[str, Any] | None = None
    matching_keys: set[tuple[str, str, str]] = set()
    for turn in sample.get("turns", []):
        if turn.get("role") == "tool" and turn.get("name") == "get_beneficiary_info":
            beneficiary_turn = turn
        content = turn.get("content")
        if isinstance(content, dict):
            matching_value = content.get("matching_beneficiaries")
            if isinstance(matching_value, list):
                matching_keys = {
                    beneficiary_key(item)
                    for item in matching_value
                    if isinstance(item, dict)
                }

    if not beneficiary_turn:
        return sample
    content = beneficiary_turn.get("content", {})
    beneficiaries = content.get("beneficiaries") if isinstance(content, dict) else None
    if not isinstance(beneficiaries, list) or len(beneficiaries) < 2:
        return sample
    if not all(isinstance(item, dict) for item in beneficiaries):
        return sample

    random.shuffle(beneficiaries)
    if not matching_keys or beneficiary_key(beneficiaries[0]) not in matching_keys:
        return sample

    for index, beneficiary in enumerate(beneficiaries[1:], start=1):
        if beneficiary_key(beneficiary) not in matching_keys:
            beneficiaries[0], beneficiaries[index] = beneficiaries[index], beneficiaries[0]
            break
    return sample


def postprocess_sample(sample: dict[str, Any], scenario: Scenario) -> dict[str, Any]:
    """Apply scenario-specific cleanup before validation and writing."""
    if scenario.id == AMBIGUOUS_BENEFICIARY_SCENARIO:
        return shuffle_ambiguous_beneficiary_lookup(sample)
    return sample


def render_generation_prompt(scenario: Scenario, config: dict[str, Any], n: int) -> str:
    """Render a scenario prompt with schemas, examples, context, and count."""
    context = fake_context(config)
    language_style_path = config.get("generation", {}).get("language_style_guide")
    language_style_guide = read_text(language_style_path) if language_style_path else ""
    values = {
        "N": n,
        "context_json": json.dumps(context, ensure_ascii=False, indent=2),
        "tool_schemas": json.dumps(tool_schemas(), ensure_ascii=False, indent=2),
        "examples": "\n".join(
            json.dumps(row, ensure_ascii=False) for row in scenario.examples()
        ),
        "language_style_guide": language_style_guide,
        "scenario_constraints": json.dumps(
            scenario.constraints or {}, ensure_ascii=False, indent=2
        ),
        "scenario_id": scenario.id,
        "scenario_type": scenario.type,
        "tool_name": scenario.tool or "",
    }
    prompt = render_template(scenario.prompt(), values)
    return (
        prompt
        + "\n\n"
        + "Output contract:\n"
        + f"- Return exactly {n} samples.\n"
        + "- Return only one valid JSON array. No markdown, no explanation, no code fence.\n"
        + "- Use compact JSON: one object per array element, no pretty-printed indentation.\n"
        + "- Ensure every string is closed and every object/array has valid commas.\n"
    )


def dry_run_rows(scenario: Scenario, limit: int | None) -> list[dict[str, Any]]:
    """Return scenario examples as dry-run rows."""
    rows = scenario.examples()
    selected = rows[: limit or 1]
    return [postprocess_sample(enrich_sample(dict(row), scenario), scenario) for row in selected]


def generate_rows(
    scenario: Scenario, config: dict[str, Any], limit: int | None, dry_run: bool
) -> list[dict[str, Any]]:
    """Generate rows for a scenario using either examples or Claude."""
    if dry_run:
        return dry_run_rows(scenario, limit)
    count = limit or scenario.count
    generator = ClaudeJsonGenerator(config)
    prompt = render_generation_prompt(scenario, config, count)
    rows = generator.generate_array(prompt)
    return [postprocess_sample(enrich_sample(row, scenario), scenario) for row in rows]


def validate_rows(
    rows: list[dict[str, Any]], scenario: Scenario
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Split rows into accepted and rejected lists using deterministic validation."""
    accepted: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    for row in rows:
        errors = validate_sample(row, scenario)
        if errors:
            rejected.append({"sample": row, "errors": errors})
        else:
            accepted.append(row)
    return accepted, rejected


def run_generation(args: argparse.Namespace) -> None:
    """Run generation for selected scenarios and write scenario output files."""
    config = load_config(args.config)
    scenarios = discover_scenarios(config["paths"]["scenarios"])
    selected = filter_scenarios(scenarios, args.type, args.tool, args.scenario)
    if not selected:
        raise SystemExit("No matching scenarios found")
    for scenario in selected:
        rows = generate_rows(scenario, config, args.limit, args.dry_run)
        accepted, rejected = validate_rows(rows, scenario)
        write_jsonl(scenario.output_file, accepted, append=args.append)
        if rejected:
            write_jsonl(
                f"{scenario.output_file}.rejected", rejected, append=args.append
            )
        print(f"{scenario.id}: wrote {len(accepted)} rows to {scenario.output_file}")
        if rejected:
            print(f"{scenario.id}: rejected {len(rejected)} rows")


def print_scenario_list(args: argparse.Namespace) -> None:
    """Print available scenarios after applying optional filters."""
    config = load_config(args.config)
    scenarios = filter_scenarios(
        discover_scenarios(config["paths"]["scenarios"]), args.type, args.tool, None
    )
    for scenario in scenarios:
        tool = scenario.tool or ",".join(scenario.involved_tools)
        print(f"{scenario.type}\t{tool}\t{scenario.id}\t{scenario.output_file}")


def print_scenario_description(args: argparse.Namespace) -> None:
    """Print details for one scenario."""
    config = load_config(args.config)
    scenario = require_one_scenario(
        discover_scenarios(config["paths"]["scenarios"]),
        args.type,
        args.tool,
        args.scenario,
    )
    print(
        json.dumps(
            {
                "id": scenario.id,
                "type": scenario.type,
                "tool": scenario.tool,
                "involved_tools": scenario.involved_tools,
                "count": scenario.count,
                "output_file": scenario.output_file,
                "path": str(scenario.path),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI parser for generation and discovery commands."""
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command")

    run = subparsers.add_parser("run", help="Generate scenario samples")
    run.add_argument("--config", default="config/settings.yaml")
    run.add_argument(
        "--type",
        choices=["single_turn", "clarification", "no_tool", "multi_turn", "all"],
        default="all",
    )
    run.add_argument("--tool", default=None)
    run.add_argument("--scenario", default=None)
    run.add_argument("--limit", type=int, default=None)
    run.add_argument("--dry-run", action="store_true")
    run.add_argument("--append", action="store_true")
    run.set_defaults(func=run_generation)

    list_cmd = subparsers.add_parser("list", help="List available scenarios")
    list_cmd.add_argument("--config", default="config/settings.yaml")
    list_cmd.add_argument(
        "--type",
        choices=["single_turn", "clarification", "no_tool", "multi_turn", "all"],
        default="all",
    )
    list_cmd.add_argument("--tool", default=None)
    list_cmd.set_defaults(func=print_scenario_list)

    describe = subparsers.add_parser("describe", help="Describe one scenario")
    describe.add_argument("--config", default="config/settings.yaml")
    describe.add_argument("--type", default=None)
    describe.add_argument("--tool", default=None)
    describe.add_argument("--scenario", required=True)
    describe.set_defaults(func=print_scenario_description)
    return parser


def main() -> None:
    """Parse CLI arguments and dispatch the selected command."""
    parser = build_parser()
    argv = sys.argv[1:]
    if not argv or argv[0] not in {"run", "list", "describe"}:
        argv = ["run", *argv]
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
