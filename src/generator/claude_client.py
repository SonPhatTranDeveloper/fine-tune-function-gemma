"""Claude API wrapper for synthetic generation."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from openai import APIStatusError, OpenAI  # type: ignore[import-not-found]

from common import extract_json_array, grabgpt_api_key, project_path


class ClaudeJsonGenerator:
    """Generate JSON arrays from prompts using Claude."""

    def __init__(self, config: dict[str, Any]) -> None:
        """Create a GrabGPT client using project configuration."""
        grabgpt = config["grabgpt"]
        self.base_url = grabgpt["base_url"]
        self.model = grabgpt["model"]
        self.max_tokens = int(grabgpt.get("max_tokens", 4096))
        self.temperature = float(grabgpt.get("temperature", 0.9))
        self.max_retries = int(grabgpt.get("max_retries", 3))
        if not 0 <= self.temperature <= 1:
            raise ValueError("GrabGPT temperature must be between 0 and 1")
        self.client = OpenAI(api_key=grabgpt_api_key(), base_url=self.base_url)

    def write_debug_response(self, text: str) -> Path:
        """Write the last raw Claude response for malformed JSON debugging."""
        output_path = project_path("reports/last_claude_response.txt")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(text, encoding="utf-8")
        return output_path

    def generate_array(self, prompt: str) -> list[dict[str, Any]]:
        """Call GrabGPT's OpenAI-compatible endpoint and parse a JSON array."""
        last_error: Exception | None = None
        debug_path: Path | None = None
        for attempt in range(1, self.max_retries + 1):
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    max_tokens=self.max_tokens,
                    temperature=self.temperature,
                    messages=[{"role": "user", "content": prompt}],
                )
                text = self.extract_text(response)
                try:
                    return extract_json_array(text)
                except Exception:
                    debug_path = self.write_debug_response(text)
                    raise
            except APIStatusError as exc:
                raise RuntimeError(
                    f"GrabGPT request rejected with status {exc.status_code}: {exc.response.text}"
                ) from exc
            except Exception as exc:  # pragma: no cover - live API behavior.
                last_error = exc
                time.sleep(min(2**attempt, 8))
        debug_hint = f"; raw response saved to {debug_path}" if debug_path else ""
        raise RuntimeError(
            f"GrabGPT generation failed after {self.max_retries} retries{debug_hint}"
        ) from last_error

    def extract_text(self, response: Any) -> str:
        """Extract generated text from an OpenAI-compatible chat response."""
        if not response.choices:
            raise ValueError("GrabGPT response did not contain choices")
        content = response.choices[0].message.content
        if not content:
            raise ValueError("GrabGPT response did not contain message content")
        return str(content)
