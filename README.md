# Vietnamese Banking Tool-Call Synthetic Generator

Clean scenario-pack generator for Vietnamese banking function-call fine-tuning data.

## Setup

```bash
uv sync
cp .env.example .env
# Fill GRABGPT_API_KEY in .env
```

Your existing `.env` was preserved during the clean rebuild.

Generation uses the OpenAI Python SDK pointed at GrabGPT's Unified API base URL,
configured in `config/settings.yaml` under `grabgpt.base_url`. The default model is
`openai/gpt-4o`.

```python
from openai import OpenAI

client = OpenAI(
    api_key=os.getenv("GRABGPT_API_KEY"),
    base_url="https://public-api.grabgpt.managed.catwalk-k8s.myteksi.net/unified/v1/",
)
```

## Scenario Packs

Each scenario is a folder with:

```text
scenario.yaml
prompt.txt
examples.jsonl
```

Layout:

```text
scenarios/
  single_turn/<tool>/<scenario>/
  no_tool/<scenario>/
  multi_turn/<scenario>/
```

Each scenario writes to its own JSONL output file. Use `src/combine.py` to build aggregate datasets.

## Vietnamese User-Language Style

Generation injects a reusable soft style guide from:

```text
prompts/language_style/vietnamese_user_style.md
```

The guide affects only generated user utterances. It asks Claude for a balanced
mix of clean Vietnamese and realistic input noise such as no-diacritic text,
abbreviations (`stk`, `nh`, `ck`, `nd`), casing/spacing mistakes, vendor payment
pastes, and light English code-switching. Tool parameters, assistant responses,
amounts, dates, and bank codes must remain normalized.

## Discover Scenarios

```bash
uv run python src/generate.py list
uv run python src/generate.py describe --scenario vendor_payment
uv run python src/combine.py list
```

## One-Command Generation Pipeline

Edit per-scenario counts at the top of:

```text
scripts/generate.sh
```

Then run:

```bash
./scripts/generate.sh
```

The script calls Claude for each scenario, appends to existing scenario output
files, combines all raw outputs, formats the combined dataset, and splits the
combined raw dataset into train/validation/test files.

## Generate Samples

Single-turn:

```bash
uv run python src/generate.py --type single_turn --tool get_account_info --scenario relative_date --limit 10
uv run python src/generate.py --type single_turn --tool get_account_info --scenario current_balance --limit 10
uv run python src/generate.py --type single_turn --tool get_account_info --scenario explicit_date_range --limit 10
uv run python src/generate.py --type single_turn --tool get_account_info --scenario recent_transactions_limit --limit 10
uv run python src/generate.py --type single_turn --tool get_account_info --scenario recent_transactions_time_period --limit 10
uv run python src/generate.py --type single_turn --tool get_account_info --scenario balance_and_recent_transactions --limit 10
uv run python src/generate.py --type single_turn --tool get_beneficiary_info --scenario saved_recipient --limit 10
uv run python src/generate.py --type single_turn --tool add_beneficiary --scenario full_name --limit 10
uv run python src/generate.py --type single_turn --tool initiate_transfer --scenario vendor_payment --limit 10
uv run python src/generate.py --type single_turn --tool initiate_transfer --scenario full_bank_account_number --limit 10
```

Natural-language assistant responses are standardized per scenario. When a
scenario defines `constraints.assistant_responses` in `scenario.yaml`, generation
prompts require that exact text and deterministic validation rejects any
paraphrase. Tool-call-only scenarios do not add assistant text.

Tool-call samples use `turns` in raw data, even when `sample_type` is
`single_turn`. Every assistant `tool_call` must be followed immediately by a
matching `tool` result with `{"status": "success"}`, then a final assistant
response that exactly matches `constraints.assistant_responses.final_response`.
No-tool samples remain top-level `user` plus `assistant_response`.

`get_account_info` tool results are query-specific:

- `info_type: balance` returns `status`, `account_id`, `balance`, and `currency`.
- `info_type: transactions` returns `status`, `account_id`, and `transactions`.
- `info_type: both` returns balance fields plus `transactions`.
- Every transaction includes `date`, signed integer `amount`, `account`, and `description`; positive amounts mean money received and negative amounts mean money sent or paid.

`get_beneficiary_info` tool results return saved beneficiaries:

```json
{
  "beneficiaries": [
    {
      "contact_name": "Tran Thi Lan",
      "to_account": "0987654321",
      "bank_name": "ACB"
    }
  ]
}
```

For `transfer_then_offer_save_beneficiary`, validation rejects samples where the
transferred `to_account` and `bank_name` already exist in the beneficiaries list.

No-tool:

```bash
uv run python src/generate.py --type no_tool --scenario banking_general_question --limit 10
```

Multi-turn:

```bash
uv run python src/generate.py --type multi_turn --scenario ambiguous_beneficiary_account_then_transfer --limit 10
uv run python src/generate.py --type multi_turn --scenario lookup_missing_amount_then_transfer --limit 10
uv run python src/generate.py --type multi_turn --scenario missing_bank_code --limit 10
uv run python src/generate.py --type multi_turn --scenario single_matching_beneficiary_then_transfer --limit 10
uv run python src/generate.py --type multi_turn --scenario transfer_then_offer_save_beneficiary --limit 10
```

Generate everything:

```bash
uv run python src/generate.py --type all
```

Add `--dry-run` to any generation command to use `examples.jsonl` instead of Claude.

## Combine Scenario Outputs

```bash
uv run python src/combine.py --type all
uv run python src/combine.py --type single_turn
uv run python src/combine.py --tool get_account_info
uv run python src/combine.py --tool initiate_transfer
uv run python src/combine.py --scenario vendor_payment
uv run python src/combine.py --scenario full_bank_account_number
```

Combined files are written to `data/raw/combined/`.

## Format And Split

```bash
uv run python src/combine.py --type all
uv run python src/split.py --input data/raw/combined/final_dataset.jsonl
uv run python src/format.py --input data/raw/combined/final_dataset.jsonl --output data/formatted/final_dataset.jsonl
```

## Key Rules

- User text may contain full or informal bank names.
- User text may contain missing Vietnamese diacritics, abbreviations, typos, pasted payment labels, and light English code-switching.
- Tool parameter `bank_name` must be a short bank code like `ACB`, `VCB`, `TCB`, `MBB`, or `BIDV`.
- `get_beneficiary_info` always uses empty parameters `{}`.
- `add_beneficiary.contact_name` must be a full name.
- Dates use `YYYY-MM-DD`.
