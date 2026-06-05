"""Format combined raw samples for FunctionGemma-style fine-tuning."""

from __future__ import annotations

import argparse
import json
from typing import Any

from common import load_config, project_path, read_jsonl, write_jsonl
from tools.banking import tool_schemas


def developer_message(
    context: dict[str, str], config: dict[str, Any]
) -> dict[str, str]:
    """Build the developer message from sample context."""
    template = config["formatting"]["developer_prompt"]
    return {"role": "developer", "content": template.format(**context)}


def assistant_tool_message(tool_call: dict[str, Any]) -> dict[str, Any]:
    """Convert a raw tool call to a FunctionGemma assistant tool message."""
    return {
        "role": "assistant",
        "content": None,
        "tool_calls": [
            {
                "type": "function",
                "function": {
                    "name": tool_call["name"],
                    "arguments": tool_call.get("parameters", {}),
                },
            }
        ],
    }


def chat_content(value: Any) -> str:
    """Return chat-template-safe text content."""
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False)


def tool_response_message(turn: dict[str, Any]) -> dict[str, Any]:
    """Convert a raw tool turn to a FunctionGemma tool response message."""
    return {
        "role": "tool",
        "content": {
            "name": turn["name"],
            "response": turn["content"],
        },
    }


def format_single_or_null(
    sample: dict[str, Any], config: dict[str, Any]
) -> dict[str, Any]:
    """Format a single-turn, clarification, or no-tool sample."""
    messages = [
        developer_message(sample["context"], config),
        {"role": "user", "content": chat_content(sample["user"])},
    ]
    if sample.get("tool_call") is None:
        messages.append(
            {
                "role": "assistant",
                "content": chat_content(sample.get("assistant_response", "")),
                "tool_calls": None,
            }
        )
    else:
        messages.append(assistant_tool_message(sample["tool_call"]))
    return {"messages": messages, "tools": tool_schemas(), "metadata": metadata(sample)}


def format_multi_turn(sample: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    """Format a multi-turn sample with tool responses."""
    messages: list[dict[str, Any]] = [developer_message(sample["context"], config)]
    for turn in sample["turns"]:
        role = turn["role"]
        if role == "user":
            messages.append({"role": "user", "content": chat_content(turn["content"])})
        elif role == "assistant" and "tool_call" in turn:
            messages.append(assistant_tool_message(turn["tool_call"]))
        elif role == "assistant":
            messages.append(
                {
                    "role": "assistant",
                    "content": chat_content(turn["content"]),
                    "tool_calls": None,
                }
            )
        elif role == "tool":
            messages.append(tool_response_message(turn))
    return {"messages": messages, "tools": tool_schemas(), "metadata": metadata(sample)}


def metadata(sample: dict[str, Any]) -> dict[str, Any]:
    """Extract metadata fields to preserve alongside formatted messages."""
    keys = ["scenario_id", "sample_type", "tool", "style", "dialect", "note"]
    return {key: sample.get(key) for key in keys if key in sample}


def format_sample(sample: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    """Format one raw sample based on its sample type."""
    if "turns" in sample or sample.get("conversation_type") == "multi_turn":
        return format_multi_turn(sample, config)
    return format_single_or_null(sample, config)


def main() -> None:
    """Format a combined JSONL file to model-ready JSONL."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="config/settings.yaml")
    parser.add_argument("--input", default="data/raw/combined/final_dataset.jsonl")
    parser.add_argument("--output", default="data/formatted/final_dataset.jsonl")
    args = parser.parse_args()

    config = load_config(args.config)
    rows = [format_sample(row, config) for row in read_jsonl(args.input)]
    output = write_jsonl(args.output, rows)
    print(f"formatted: {len(rows)} rows -> {project_path(output)}")


if __name__ == "__main__":
    main()
