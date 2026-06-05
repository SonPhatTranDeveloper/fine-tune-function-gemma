"""Split combined raw samples into train, validation, and test JSONL files."""

from __future__ import annotations

import argparse
import random
from collections import defaultdict

from common import read_jsonl, write_jsonl


def stratify_key(sample: dict) -> str:
    """Return the stratification key for a sample."""
    return (
        f"{sample.get('sample_type')}:{sample.get('tool') or sample.get('scenario_id')}"
    )


def split_rows(rows: list[dict], seed: int) -> dict[str, list[dict]]:
    """Split rows into train, validation, and test while preserving rough strata."""
    random.seed(seed)
    groups: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        groups[stratify_key(row)].append(row)
    splits = {"train": [], "val": [], "test": []}
    for group in groups.values():
        random.shuffle(group)
        n = len(group)
        if n < 3:
            splits["train"].extend(group)
            continue
        train_end = int(n * 0.8)
        val_end = max(train_end + 1, int(n * 0.9))
        splits["train"].extend(group[:train_end])
        splits["val"].extend(group[train_end:val_end])
        splits["test"].extend(group[val_end:])
    for rows_for_split in splits.values():
        random.shuffle(rows_for_split)
    return splits


def main() -> None:
    """Run train/val/test splitting from a combined input file."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", default="data/raw/combined/final_dataset.jsonl")
    parser.add_argument("--output-dir", default="data/splits")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    splits = split_rows(read_jsonl(args.input), args.seed)
    for name, rows in splits.items():
        output = f"{args.output_dir}/{name}.jsonl"
        write_jsonl(output, rows)
        print(f"{name}: {len(rows)} rows -> {output}")


if __name__ == "__main__":
    main()
