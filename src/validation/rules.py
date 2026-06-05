"""Deterministic validation rules for generated samples."""

from __future__ import annotations

import re
from datetime import date, timedelta
from typing import Any

from generator.scenario import Scenario
from tools.banking import BANK_CODES, REQUIRED_PARAMS, TOOL_NAMES

INFO_TYPES = {"balance", "transactions", "both"}
CASUAL_LABELS = (
    "bạn ",
    "chị ",
    "anh ",
    "em ",
    "vợ",
    "chồng",
    "ba ",
    "má ",
    "mẹ ",
    "bố ",
)
PHONE_RE = re.compile(r"^0\d{3}\s\d{3}\s\d{3}$")
NUMERIC_DAY_PERIOD_RE = re.compile(r"\b(\d{1,2})\s*(ngày|ngay|hôm|hom)\b")
NUMERIC_WEEK_PERIOD_RE = re.compile(r"\b(\d{1,2})\s*tuần\b")
WORD_DAY_PERIOD_RE = re.compile(
    r"\b(một|mot|hai|ba|bốn|bon|tư|tu|năm|nam)\s*(ngày|ngay|hôm|hom)\b"
)
WORD_WEEK_PERIOD_RE = re.compile(r"\b(một|mot|hai|ba|bốn|bon)\s*tuần\b")
YESTERDAY_TO_TODAY_RE = re.compile(r"\bhôm qua\b|\bhom qua\b")
TODAY_ONLY_RE = re.compile(r"\bhôm nay\b|\bhom nay\b")
ONE_WEEK_RE = re.compile(r"\btuần\s*(rồi|roi|qua|này|nay)\b")
ONE_MONTH_RE = re.compile(r"\b(một|mot)\s*tháng\b|\btháng\s*(rồi|roi|qua|này|nay)\b")
SMALL_VI_NUMBERS = {
    "một": 1,
    "mot": 1,
    "hai": 2,
    "ba": 3,
    "bốn": 4,
    "bon": 4,
    "tư": 4,
    "tu": 4,
    "năm": 5,
    "nam": 5,
}


def is_valid_date(value: Any) -> bool:
    """Return true when value is a non-future YYYY-MM-DD date."""
    try:
        parsed = date.fromisoformat(str(value))
    except (TypeError, ValueError):
        return False
    return parsed <= date.today()


def is_full_name(value: Any) -> bool:
    """Return true when value looks like a full person name, not a casual label."""
    if not isinstance(value, str):
        return False
    lowered = value.strip().lower()
    if any(
        lowered.startswith(label) or lowered == label.strip() for label in CASUAL_LABELS
    ):
        return False
    return len(value.strip().split()) >= 2


def validate_context(sample: dict[str, Any]) -> list[str]:
    """Validate the shared context block on a sample."""
    context = sample.get("context")
    if not isinstance(context, dict):
        return ["context must be an object"]
    errors: list[str] = []
    for key in ("user_name", "user_phone", "current_date"):
        if not context.get(key):
            errors.append(f"context.{key} is required")
    if context.get("user_phone") and not PHONE_RE.match(str(context["user_phone"])):
        errors.append("context.user_phone must use fake VN format like 0912 345 678")
    if context.get("current_date") and not is_valid_date(context["current_date"]):
        errors.append("context.current_date must be YYYY-MM-DD and not future")
    return errors


def validate_tool_call(tool_call: dict[str, Any] | None, allow_null: bool) -> list[str]:
    """Validate a tool call object against global tool rules."""
    if tool_call is None:
        return [] if allow_null else ["tool_call is required"]
    if not isinstance(tool_call, dict):
        return ["tool_call must be an object or null"]
    name = tool_call.get("name")
    params = tool_call.get("parameters")
    if name not in TOOL_NAMES:
        return [f"unknown tool: {name}"]
    if not isinstance(params, dict):
        return ["tool_call.parameters must be an object"]
    errors: list[str] = []
    missing = REQUIRED_PARAMS[name] - set(params)
    if missing:
        errors.append(f"missing required parameters for {name}: {sorted(missing)}")
    if name == "get_account_info" and params.get("info_type") not in INFO_TYPES:
        errors.append(
            "get_account_info.info_type must be balance, transactions, or both"
        )
    if name == "get_beneficiary_info" and params:
        errors.append("get_beneficiary_info parameters must be empty")
    if name == "add_beneficiary":
        if set(params) - REQUIRED_PARAMS[name]:
            errors.append("add_beneficiary has unexpected parameters")
        if not is_full_name(params.get("contact_name")):
            errors.append("add_beneficiary.contact_name must be a full name")
    if name in {"add_beneficiary", "initiate_transfer"}:
        bank_name = str(params.get("bank_name", "")).upper()
        if bank_name not in BANK_CODES:
            errors.append("bank_name must be a supported short bank code")
    if name == "initiate_transfer":
        amount = params.get("amount")
        if not isinstance(amount, int) or amount < 1000:
            errors.append("initiate_transfer.amount must be integer VND >= 1000")
    for key in ("from_date", "to_date"):
        if key in params and params[key] and not is_valid_date(params[key]):
            errors.append(f"{key} must be YYYY-MM-DD and not future")
    return errors


def validate_transaction_result(
    transaction: Any,
    params: dict[str, Any],
    index: int,
) -> list[str]:
    """Validate one get_account_info transaction result row."""
    if not isinstance(transaction, dict):
        return [f"transaction {index} must be an object"]
    errors: list[str] = []
    for key in ("date", "amount", "account", "description"):
        if key not in transaction:
            errors.append(f"transaction {index}.{key} is required")
    if "date" in transaction and not is_valid_date(transaction["date"]):
        errors.append(f"transaction {index}.date must be YYYY-MM-DD and not future")
    if "amount" in transaction and not isinstance(transaction["amount"], int):
        errors.append(f"transaction {index}.amount must be a signed integer")
    if "account" in transaction and not str(transaction["account"]).strip():
        errors.append(f"transaction {index}.account is required")
    if "description" in transaction and not str(transaction["description"]).strip():
        errors.append(f"transaction {index}.description is required")
    tx_date = transaction.get("date")
    if tx_date and params.get("from_date") and str(tx_date) < str(params["from_date"]):
        errors.append(f"transaction {index}.date is before from_date")
    if tx_date and params.get("to_date") and str(tx_date) > str(params["to_date"]):
        errors.append(f"transaction {index}.date is after to_date")
    return errors


def validate_get_account_info_result(
    params: dict[str, Any],
    content: dict[str, Any],
) -> list[str]:
    """Validate get_account_info result content against requested info_type."""
    errors: list[str] = []
    info_type = params.get("info_type")
    if content.get("account_id") != params.get("account_id"):
        errors.append(
            "get_account_info result.account_id must match request account_id"
        )

    has_balance = "balance" in content
    has_transactions = "transactions" in content
    if info_type == "balance":
        if not has_balance:
            errors.append("balance result must include balance")
        if has_transactions:
            errors.append("balance result must not include transactions")
    elif info_type == "transactions":
        if not has_transactions:
            errors.append("transactions result must include transactions")
        if has_balance:
            errors.append("transactions result must not include balance")
    elif info_type == "both":
        if not has_balance:
            errors.append("both result must include balance")
        if not has_transactions:
            errors.append("both result must include transactions")

    if has_balance and not isinstance(content.get("balance"), int):
        errors.append("balance must be an integer VND amount")
    if has_balance and content.get("currency") != "VND":
        errors.append("balance result currency must be VND")
    if has_transactions:
        transactions = content.get("transactions")
        if not isinstance(transactions, list):
            errors.append("transactions must be a list")
        else:
            limit = params.get("limit")
            if isinstance(limit, int) and len(transactions) > limit:
                errors.append("transactions count must not exceed limit")
            for index, transaction in enumerate(transactions):
                errors.extend(validate_transaction_result(transaction, params, index))
    return errors


def validate_beneficiary_info_result(content: dict[str, Any]) -> list[str]:
    """Validate get_beneficiary_info result content."""
    beneficiaries = content.get("beneficiaries")
    if not isinstance(beneficiaries, list):
        return ["get_beneficiary_info result must include beneficiaries list"]

    errors: list[str] = []
    for index, beneficiary in enumerate(beneficiaries):
        if not isinstance(beneficiary, dict):
            errors.append(f"beneficiary {index} must be an object")
            continue
        if set(beneficiary) - {"contact_name", "to_account", "bank_name"}:
            errors.append(f"beneficiary {index} has unexpected fields")
        for key in ("contact_name", "to_account", "bank_name"):
            if not str(beneficiary.get(key, "")).strip():
                errors.append(f"beneficiary {index}.{key} is required")
        bank_name = str(beneficiary.get("bank_name", "")).upper()
        if bank_name and bank_name not in BANK_CODES:
            errors.append(
                f"beneficiary {index}.bank_name must be a supported short bank code"
            )
    return errors


def validate_ambiguous_beneficiary_selection(sample: dict[str, Any]) -> list[str]:
    """Ensure ambiguous beneficiary samples transfer to the user-selected account."""
    if sample.get("scenario_id") != "ambiguous_beneficiary_account_then_transfer":
        return []

    turns = sample.get("turns", [])
    beneficiary_result: dict[str, Any] | None = None
    assistant_selection_payload: dict[str, Any] | None = None
    user_selection_payload: dict[str, Any] | None = None
    transfer_params: dict[str, Any] | None = None
    for index, turn in enumerate(turns):
        if turn.get("role") == "tool" and turn.get("name") == "get_beneficiary_info":
            beneficiary_result = turn.get("content", {})
            if index + 1 < len(turns) and turns[index + 1].get("role") == "assistant":
                content = turns[index + 1].get("content")
                if isinstance(content, dict):
                    assistant_selection_payload = content
            if index + 2 < len(turns) and turns[index + 2].get("role") == "user":
                content = turns[index + 2].get("content")
                if isinstance(content, dict):
                    user_selection_payload = content
        if (
            turn.get("role") == "assistant"
            and turn.get("tool_call", {}).get("name") == "initiate_transfer"
        ):
            transfer_params = turn["tool_call"].get("parameters", {})

    if not beneficiary_result or not transfer_params:
        return []

    errors: list[str] = []
    beneficiaries = beneficiary_result.get("beneficiaries", [])
    if not isinstance(beneficiaries, list):
        return []
    if not all(isinstance(item, dict) for item in beneficiaries):
        return []
    if not 4 <= len(beneficiaries) <= 6:
        errors.append(
            "ambiguous beneficiary lookup must return 4 to 6 saved beneficiaries"
        )

    transfer_account = str(transfer_params.get("to_account", ""))
    transfer_bank = str(transfer_params.get("bank_name", "")).upper()
    expected_message = (
        "Mình tìm thấy nhiều người thụ hưởng khớp thông tin. "
        "Bạn vui lòng chọn đúng tài khoản muốn chuyển."
    )
    if not assistant_selection_payload:
        errors.append("assistant must return matching beneficiaries as a JSON object")
        matching_beneficiaries: list[dict[str, Any]] = []
    else:
        if set(assistant_selection_payload) != {"message", "matching_beneficiaries"}:
            errors.append("assistant matching beneficiary JSON has invalid fields")
        if assistant_selection_payload.get("message") != expected_message:
            errors.append(
                "assistant matching beneficiary message must match canonical text"
            )
        matching_value = assistant_selection_payload.get("matching_beneficiaries")
        if not isinstance(matching_value, list) or not all(
            isinstance(item, dict) for item in matching_value
        ):
            errors.append("assistant matching beneficiaries must be a list of objects")
            matching_beneficiaries = []
        else:
            matching_beneficiaries = matching_value
            if len(matching_beneficiaries) not in {2, 3}:
                errors.append("assistant must return 2 or 3 matching beneficiaries")
            for item in matching_beneficiaries:
                if item not in beneficiaries:
                    errors.append(
                        "assistant matching beneficiaries must be copied from tool result"
                    )
                    break
            if all(item in matching_beneficiaries for item in beneficiaries):
                errors.append(
                    "assistant must filter a subset, not return the full beneficiary list"
                )
    if not user_selection_payload:
        errors.append("user selection must be a JSON object")
    elif set(user_selection_payload) != {"to_account", "bank_name"}:
        errors.append("user selection JSON has invalid fields")
    if matching_beneficiaries and not all(
        str(item.get("bank_name", "")).upper() == transfer_bank
        for item in matching_beneficiaries
    ):
        errors.append("assistant matching beneficiaries must use the transfer bank")
    if matching_beneficiaries and not any(
        item not in matching_beneficiaries for item in beneficiaries
    ):
        errors.append(
            "beneficiary lookup must include at least one non-matching beneficiary"
        )
    if not any(
        str(item.get("to_account", "")) == transfer_account
        and str(item.get("bank_name", "")).upper() == transfer_bank
        for item in matching_beneficiaries
    ):
        errors.append("transfer account must be selected from matching beneficiaries")
    if user_selection_payload and (
        str(user_selection_payload.get("to_account", "")) != transfer_account
        or str(user_selection_payload.get("bank_name", "")).upper() != transfer_bank
    ):
        errors.append("transfer parameters must match user JSON selection")
    return errors


def validate_single_matching_beneficiary_transfer(sample: dict[str, Any]) -> list[str]:
    """Ensure single-match beneficiary samples transfer immediately after lookup."""
    if sample.get("scenario_id") != "single_matching_beneficiary_then_transfer":
        return []

    turns = sample.get("turns", [])
    beneficiary_result: dict[str, Any] | None = None
    transfer_params: dict[str, Any] | None = None
    lookup_index: int | None = None
    transfer_index: int | None = None
    for index, turn in enumerate(turns):
        if turn.get("role") == "tool" and turn.get("name") == "get_beneficiary_info":
            beneficiary_result = turn.get("content", {})
            lookup_index = index
        if (
            turn.get("role") == "assistant"
            and turn.get("tool_call", {}).get("name") == "initiate_transfer"
        ):
            transfer_params = turn["tool_call"].get("parameters", {})
            transfer_index = index

    if not beneficiary_result or not transfer_params:
        return []

    errors: list[str] = []
    beneficiaries = beneficiary_result.get("beneficiaries", [])
    if not isinstance(beneficiaries, list):
        return []
    if not all(isinstance(item, dict) for item in beneficiaries):
        return []
    if not 4 <= len(beneficiaries) <= 6:
        errors.append(
            "single-match beneficiary lookup must return 4 to 6 saved beneficiaries"
        )

    transfer_account = str(transfer_params.get("to_account", ""))
    transfer_bank = str(transfer_params.get("bank_name", "")).upper()
    matching_transfer_targets = [
        item
        for item in beneficiaries
        if str(item.get("to_account", "")) == transfer_account
        and str(item.get("bank_name", "")).upper() == transfer_bank
    ]
    if len(matching_transfer_targets) != 1:
        errors.append(
            "single-match transfer target must appear exactly once in beneficiaries"
        )
    if not any(item not in matching_transfer_targets for item in beneficiaries):
        errors.append("single-match lookup must include non-matching beneficiaries")
    if (
        lookup_index is None
        or transfer_index is None
        or transfer_index != lookup_index + 1
    ):
        errors.append(
            "single-match flow must call initiate_transfer immediately after lookup result"
        )
    return errors


def requested_recent_transaction_period_days(sample: dict[str, Any]) -> int | None:
    """Infer the requested recent transaction period from the first user message."""
    turns = sample.get("turns", [])
    first_user_content = ""
    for turn in turns:
        if turn.get("role") == "user":
            first_user_content = str(turn.get("content", "")).lower()
            break

    numeric_day_match = NUMERIC_DAY_PERIOD_RE.search(first_user_content)
    if numeric_day_match:
        return int(numeric_day_match.group(1))

    numeric_week_match = NUMERIC_WEEK_PERIOD_RE.search(first_user_content)
    if numeric_week_match:
        return int(numeric_week_match.group(1)) * 7

    word_day_match = WORD_DAY_PERIOD_RE.search(first_user_content)
    if word_day_match:
        return SMALL_VI_NUMBERS.get(word_day_match.group(1))

    word_week_match = WORD_WEEK_PERIOD_RE.search(first_user_content)
    if word_week_match:
        word_value = SMALL_VI_NUMBERS.get(word_week_match.group(1))
        return word_value * 7 if word_value is not None else None

    if YESTERDAY_TO_TODAY_RE.search(first_user_content):
        return 2
    if ONE_WEEK_RE.search(first_user_content):
        return 7
    if ONE_MONTH_RE.search(first_user_content):
        return 30
    if TODAY_ONLY_RE.search(first_user_content):
        return 1
    return None


def first_tool_call_params(
    sample: dict[str, Any], tool_name: str
) -> dict[str, Any] | None:
    """Return parameters from the first assistant call to a tool."""
    for turn in sample.get("turns", []):
        tool_call = turn.get("tool_call", {}) if turn.get("role") == "assistant" else {}
        if tool_call.get("name") == tool_name:
            params = tool_call.get("parameters", {})
            return params if isinstance(params, dict) else None
    return None


def validate_recent_transactions_time_period(sample: dict[str, Any]) -> list[str]:
    """Validate inclusive recent-transaction range requests."""
    if sample.get("scenario_id") != "recent_transactions_time_period":
        return []

    errors: list[str] = []
    context = sample.get("context", {})
    params = first_tool_call_params(sample, "get_account_info") or {}

    if params.get("account_id") != "ACC_USER":
        errors.append("recent_transactions_time_period account_id must be ACC_USER")
    if params.get("info_type") != "transactions":
        errors.append("recent_transactions_time_period info_type must be transactions")
    if not params.get("from_date") or not params.get("to_date"):
        errors.append("recent_transactions_time_period requires from_date and to_date")

    try:
        current_date = date.fromisoformat(str(context.get("current_date")))
        from_date = date.fromisoformat(str(params.get("from_date")))
        to_date = date.fromisoformat(str(params.get("to_date")))
    except (TypeError, ValueError):
        return errors

    if to_date != current_date:
        errors.append("recent_transactions_time_period to_date must equal current_date")

    period_days = requested_recent_transaction_period_days(sample)
    if period_days is None or not 1 <= period_days <= 30:
        errors.append(
            "recent_transactions_time_period user request must specify a recent period from 1 to 30 days"
        )
    else:
        expected_from_date = current_date - timedelta(days=period_days - 1)
        if from_date != expected_from_date:
            errors.append(
                "recent_transactions_time_period from_date must match the requested inclusive period"
            )
    return errors


def validate_turns(sample: dict[str, Any]) -> list[str]:
    """Validate multi-turn records and assistant tool calls inside turns."""
    turns = sample.get("turns")
    if not isinstance(turns, list) or not turns:
        return ["multi_turn sample must include non-empty turns"]
    errors: list[str] = []
    for index, turn in enumerate(turns):
        role = turn.get("role") if isinstance(turn, dict) else None
        if role not in {"user", "assistant", "tool"}:
            errors.append(f"turn {index} has invalid role")
        if role == "assistant" and "tool_call" in turn:
            errors.extend(
                f"turn {index}: {err}"
                for err in validate_tool_call(turn["tool_call"], False)
            )
        if role == "assistant" and "tool_call" not in turn and not turn.get("content"):
            errors.append(f"turn {index} assistant requires content or tool_call")
        if role == "tool" and ("name" not in turn or "content" not in turn):
            errors.append(f"turn {index} tool requires name and content")
    return errors


def validate_successful_tool_results(sample: dict[str, Any]) -> list[str]:
    """Validate that each assistant tool call is followed by a successful tool result."""
    turns = sample.get("turns", [])
    errors: list[str] = []
    saw_tool_call = False
    for index, turn in enumerate(turns):
        if turn.get("role") != "assistant" or "tool_call" not in turn:
            continue
        saw_tool_call = True
        if index + 1 >= len(turns):
            errors.append(f"turn {index} tool_call must be followed by a tool result")
            continue
        next_turn = turns[index + 1]
        tool_name = turn["tool_call"].get("name")
        if next_turn.get("role") != "tool":
            errors.append(
                f"turn {index} tool_call must be followed immediately by a tool result"
            )
            continue
        if next_turn.get("name") != tool_name:
            errors.append(f"turn {index} tool result name must match tool_call name")
        content = next_turn.get("content")
        if not isinstance(content, dict):
            errors.append(f"turn {index + 1} tool result content must be an object")
        elif tool_name == "get_beneficiary_info":
            errors.extend(
                f"turn {index + 1}: {err}"
                for err in validate_beneficiary_info_result(content)
            )
        elif content.get("status") != "success":
            errors.append(
                f"turn {index + 1} tool result content.status must be success"
            )
        elif tool_name == "get_account_info":
            errors.extend(
                f"turn {index + 1}: {err}"
                for err in validate_get_account_info_result(
                    turn["tool_call"].get("parameters", {}),
                    content,
                )
            )
    if saw_tool_call:
        final_turn = turns[-1] if turns else {}
        if final_turn.get("role") != "assistant" or "content" not in final_turn:
            errors.append(
                "tool-call samples must end with a final assistant content turn"
            )
    return errors


def validate_clarification_turns(sample: dict[str, Any]) -> list[str]:
    """Validate a clarification conversation that asks, executes, and answers."""
    errors = validate_turns(sample)
    if errors:
        return errors

    turns = sample["turns"]
    if len(turns) < 4:
        errors.append("clarification sample must include at least 4 turns")
    if turns[0].get("role") != "user":
        errors.append("clarification first turn must be user")
    if not any(
        turn.get("role") == "assistant" and turn.get("content") for turn in turns[:-1]
    ):
        errors.append(
            "clarification requires an assistant clarifying question before the final tool call"
        )
    if not any(
        turn.get("role") == "user" and turn.get("content") for turn in turns[1:-1]
    ):
        errors.append("clarification requires a user answer before the final tool call")

    tool_calls = [
        turn
        for turn in turns
        if turn.get("role") == "assistant" and "tool_call" in turn
    ]
    if not tool_calls:
        errors.append(
            "clarification requires an assistant tool_call after the user answer"
        )
    elif (
        sample.get("tool") and tool_calls[-1]["tool_call"].get("name") != sample["tool"]
    ):
        errors.append("clarification final tool_call must match sample.tool")
    errors.extend(validate_successful_tool_results(sample))
    return errors


def assistant_response_constraints(scenario: Scenario | None) -> dict[str, Any]:
    """Return canonical assistant response constraints for a scenario."""
    if not scenario or not scenario.constraints:
        return {}
    responses = scenario.constraints.get("assistant_responses", {})
    return responses if isinstance(responses, dict) else {}


def assistant_content_turns(sample: dict[str, Any]) -> list[str]:
    """Extract assistant natural-language content turns in order."""
    contents: list[str] = []
    for turn in sample.get("turns", []):
        if turn.get("role") == "assistant" and "content" in turn:
            contents.append(str(turn.get("content", "")))
    return contents


def non_final_assistant_content_turns(sample: dict[str, Any]) -> list[str]:
    """Extract assistant content turns before the final assistant response."""
    contents = assistant_content_turns(sample)
    return contents[:-1] if contents else []


def validate_canonical_assistant_responses(
    sample: dict[str, Any],
    scenario: Scenario | None,
) -> list[str]:
    """Validate exact scenario-level assistant response text when configured."""
    responses = assistant_response_constraints(scenario)
    if not responses:
        return []

    sample_type = sample.get("sample_type")
    errors: list[str] = []
    if sample_type == "no_tool" and "no_tool_response" in responses:
        expected = responses["no_tool_response"]
        if sample.get("assistant_response") != expected:
            errors.append(
                "assistant_response must exactly match scenario canonical no_tool_response"
            )
    if sample_type == "clarification" and "clarification_question" in responses:
        expected = responses["clarification_question"]
        contents = non_final_assistant_content_turns(sample)
        if contents != [expected]:
            errors.append(
                "clarification assistant content must exactly match scenario canonical clarification_question"
            )
    if sample_type == "multi_turn" and "assistant_content_turns" in responses:
        expected_turns = responses["assistant_content_turns"]
        if non_final_assistant_content_turns(sample) != expected_turns:
            errors.append(
                "assistant content turns must exactly match scenario canonical assistant_content_turns"
            )
    if "final_response" in responses and "turns" in sample:
        contents = assistant_content_turns(sample)
        if not contents or contents[-1] != responses["final_response"]:
            errors.append(
                "final assistant response must exactly match scenario canonical final_response"
            )
    return errors


def validate_sample(
    sample: dict[str, Any], scenario: Scenario | None = None
) -> list[str]:
    """Validate a generated sample using global and scenario-level rules."""
    errors = validate_context(sample)
    sample_type = sample.get("sample_type")
    if scenario and sample.get("scenario_id") != scenario.id:
        errors.append("scenario_id does not match scenario")
    if "turns" in sample:
        errors.extend(validate_turns(sample))
        if any(
            turn.get("role") == "assistant" and "tool_call" in turn
            for turn in sample.get("turns", [])
        ):
            errors.extend(validate_successful_tool_results(sample))
    if sample_type == "clarification":
        errors.extend(validate_clarification_turns(sample))
    elif "turns" not in sample and (
        sample_type == "multi_turn" or sample.get("conversation_type") == "multi_turn"
    ):
        errors.extend(validate_turns(sample))
    elif sample_type == "no_tool":
        errors.extend(validate_tool_call(sample.get("tool_call"), allow_null=True))
        if sample.get("tool_call") is not None:
            errors.append(f"{sample_type} samples must have tool_call null")
        if not sample.get("assistant_response"):
            errors.append(f"{sample_type} samples require assistant_response")
    elif "turns" not in sample:
        errors.extend(validate_tool_call(sample.get("tool_call"), allow_null=False))
    errors.extend(validate_canonical_assistant_responses(sample, scenario))
    errors.extend(validate_ambiguous_beneficiary_selection(sample))
    errors.extend(validate_single_matching_beneficiary_transfer(sample))
    errors.extend(validate_recent_transactions_time_period(sample))
    return errors
