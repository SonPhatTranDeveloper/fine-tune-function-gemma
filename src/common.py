"""Shared utilities for scenario-pack generation commands."""

from __future__ import annotations

import hashlib
import json
import os
import random
import re
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

SAMPLE_NAMES = [
    "Nguyen Van An",
    "Tran Thi Bich",
    "Le Minh Duc",
    "Pham Thu Ha",
    "Huynh Van Tam",
    "Nguyen Thi Lan",
    "Vo Minh Tuan",
    "Ly Thi Mai",
]
VN_PREFIXES = ["0912", "0987", "0908", "0971", "0334", "0356", "0776", "0396"]


def project_path(path: str | Path) -> Path:
    """Resolve a project-relative path to an absolute path."""
    candidate = Path(path)
    return candidate if candidate.is_absolute() else ROOT / candidate


def load_config(path: str | Path = "config/settings.yaml") -> dict[str, Any]:
    """Load YAML config."""
    with project_path(path).open("r", encoding="utf-8") as f:
        config = yaml.safe_load(f) or {}
    return config


def grabgpt_api_key() -> str:
    """Return the GrabGPT API key from `.env` or the shell environment."""
    api_key = os.getenv("GRABGPT_API_KEY")
    if not api_key:
        raise RuntimeError("GRABGPT_API_KEY is required for non-dry-run generation")
    return api_key


def read_text(path: str | Path) -> str:
    """Read a UTF-8 text file from the project."""
    return project_path(path).read_text(encoding="utf-8")


def read_yaml(path: str | Path) -> dict[str, Any]:
    """Read a YAML object from the project."""
    with project_path(path).open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def read_jsonl(path: str | Path) -> list[dict[str, Any]]:
    """Read a JSONL file, returning an empty list when it does not exist."""
    resolved = project_path(path)
    if not resolved.exists():
        return []
    rows: list[dict[str, Any]] = []
    with resolved.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def write_jsonl(
    path: str | Path, rows: list[dict[str, Any]], append: bool = False
) -> Path:
    """Write rows to a JSONL file and create parent directories when needed."""
    resolved = project_path(path)
    resolved.parent.mkdir(parents=True, exist_ok=True)
    mode = "a" if append else "w"
    with resolved.open(mode, encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    return resolved


def render_template(template: str, values: dict[str, Any]) -> str:
    """Render a simple `{name}` template using string replacement."""
    rendered = template
    for key, value in values.items():
        rendered = rendered.replace("{" + key + "}", str(value))
    return rendered


def fake_context(config: dict[str, Any]) -> dict[str, str]:
    """Create fake user context with a current date in YYYY-MM-DD format."""
    offset_days = int(
        config.get("generation", {}).get("context", {}).get("date_offset_days", 30)
    )
    prefix = random.choice(VN_PREFIXES)
    suffix = f"{random.randint(100000, 999999)}"
    current_date = (
        date.today() + timedelta(days=random.randint(-offset_days, 0))
    ).isoformat()
    return {
        "user_name": random.choice(SAMPLE_NAMES),
        "user_phone": f"{prefix} {suffix[:3]} {suffix[3:]}",
        "current_date": current_date,
    }


def extract_json_array(text: str) -> list[dict[str, Any]]:
    """Extract a JSON array from raw model text, including fenced responses."""
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json)?", "", stripped).strip()
        stripped = re.sub(r"```$", "", stripped).strip()
    try:
        parsed = json.loads(stripped)
    except json.JSONDecodeError:
        match = re.search(r"\[[\s\S]*\]", stripped)
        if not match:
            raise
        parsed = json.loads(match.group(0))
    if not isinstance(parsed, list):
        raise ValueError("Expected generated output to be a JSON array")
    return parsed


def stable_hash(row: dict[str, Any]) -> str:
    """Return a stable SHA-256 hash for a sample row."""
    payload = json.dumps(row, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
