"""Scenario pack discovery and metadata helpers."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from common import project_path, read_jsonl, read_text, read_yaml


@dataclass(frozen=True)
class Scenario:
    """A generation scenario loaded from a scenario pack folder."""

    id: str
    type: str
    path: Path
    prompt_path: Path
    examples_path: Path
    output_file: str
    count: int
    tool: str | None = None
    involved_tools: tuple[str, ...] = ()
    constraints: dict[str, Any] | None = None

    @classmethod
    def from_dir(cls, path: Path) -> "Scenario":
        """Load a scenario from a directory containing `scenario.yaml`."""
        spec = read_yaml(path / "scenario.yaml")
        return cls(
            id=str(spec["id"]),
            type=str(spec["type"]),
            tool=spec.get("tool"),
            involved_tools=tuple(spec.get("involved_tools", [])),
            path=path,
            prompt_path=path / "prompt.txt",
            examples_path=path / "examples.jsonl",
            output_file=str(spec["output_file"]),
            count=int(spec.get("count", 10)),
            constraints=spec.get("constraints", {}),
        )

    def prompt(self) -> str:
        """Read this scenario's prompt template."""
        return read_text(self.prompt_path)

    def examples(self) -> list[dict[str, Any]]:
        """Read this scenario's few-shot examples."""
        return read_jsonl(self.examples_path)


def discover_scenarios(root: str | Path = "scenarios") -> list[Scenario]:
    """Discover all scenario packs under the scenarios directory."""
    scenario_root = project_path(root)
    scenarios: list[Scenario] = []
    for spec_path in sorted(scenario_root.rglob("scenario.yaml")):
        scenarios.append(Scenario.from_dir(spec_path.parent))
    return scenarios


def filter_scenarios(
    scenarios: list[Scenario],
    scenario_type: str | None = None,
    tool: str | None = None,
    scenario_id: str | None = None,
) -> list[Scenario]:
    """Filter scenarios by type, tool, and scenario id."""
    result = scenarios
    if scenario_type and scenario_type != "all":
        result = [s for s in result if s.type == scenario_type]
    if tool:
        result = [s for s in result if s.tool == tool or tool in s.involved_tools]
    if scenario_id:
        result = [s for s in result if s.id == scenario_id]
    return result


def require_one_scenario(
    scenarios: list[Scenario],
    scenario_type: str | None,
    tool: str | None,
    scenario_id: str,
) -> Scenario:
    """Return exactly one matching scenario or raise a helpful error."""
    matches = filter_scenarios(scenarios, scenario_type, tool, scenario_id)
    if not matches:
        raise ValueError(
            f"No scenario found for type={scenario_type}, tool={tool}, scenario={scenario_id}"
        )
    if len(matches) > 1:
        paths = ", ".join(str(s.path) for s in matches)
        raise ValueError(f"Scenario id is ambiguous; matches: {paths}")
    return matches[0]
