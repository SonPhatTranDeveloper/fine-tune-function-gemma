#!/usr/bin/env bash
set -euo pipefail

# Edit these counts before running. Each value controls one scenario.
# Set a count to 0 to skip that scenario.
GET_ACCOUNT_INFO_RECENT_TRANSACTIONS_TIME_PERIOD=10

INITIATE_TRANSFER_VENDOR_PAYMENT=10
INITIATE_TRANSFER_FULL_BANK_ACCOUNT_NUMBER=10

MULTI_TURN_MISSING_BANK_CODE=10
MULTI_TURN_AMBIGUOUS_BENEFICIARY_ACCOUNT_THEN_TRANSFER=10

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

run_scenario() {
  local sample_type="$1"
  local tool="$2"
  local scenario="$3"
  local count="$4"

  if [[ "$count" -le 0 ]]; then
    echo "skip: $sample_type ${tool:+$tool }$scenario"
    return
  fi

  echo "generate: $sample_type ${tool:+$tool }$scenario count=$count"
  if [[ -n "$tool" ]]; then
    uv run python src/generate.py \
      --type "$sample_type" \
      --tool "$tool" \
      --scenario "$scenario" \
      --limit "$count" \
      --append
  else
    uv run python src/generate.py \
      --type "$sample_type" \
      --scenario "$scenario" \
      --limit "$count" \
      --append
  fi
}

echo "Starting Claude generation. Existing scenario outputs will be appended."

run_scenario "single_turn" "get_account_info" "recent_transactions_time_period" "$GET_ACCOUNT_INFO_RECENT_TRANSACTIONS_TIME_PERIOD"

run_scenario "single_turn" "initiate_transfer" "vendor_payment" "$INITIATE_TRANSFER_VENDOR_PAYMENT"
run_scenario "single_turn" "initiate_transfer" "full_bank_account_number" "$INITIATE_TRANSFER_FULL_BANK_ACCOUNT_NUMBER"

run_scenario "multi_turn" "" "missing_bank_code" "$MULTI_TURN_MISSING_BANK_CODE"
run_scenario "multi_turn" "" "ambiguous_beneficiary_account_then_transfer" "$MULTI_TURN_AMBIGUOUS_BENEFICIARY_ACCOUNT_THEN_TRANSFER"

echo "Combining scenario outputs..."
uv run python src/combine.py --type all

echo "Formatting combined dataset..."
uv run python src/format.py \
  --input data/raw/combined/final_dataset.jsonl \
  --output data/formatted/final_dataset.jsonl

echo "Splitting combined raw dataset..."
uv run python src/split.py \
  --input data/raw/combined/final_dataset.jsonl \
  --output-dir data/splits

echo "Done."
echo "Combined raw: data/raw/combined/final_dataset.jsonl"
echo "Formatted: data/formatted/final_dataset.jsonl"
echo "Splits: data/splits/train.jsonl data/splits/val.jsonl data/splits/test.jsonl"
