from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from generator.scenario import discover_scenarios, require_one_scenario  # noqa: E402
from generate import shuffle_ambiguous_beneficiary_lookup  # noqa: E402
from validation.rules import validate_sample  # noqa: E402


def valid_single_candidate_selection_sample() -> dict:
    return {
        "scenario_id": "ambiguous_beneficiary_account_then_transfer",
        "sample_type": "multi_turn",
        "conversation_type": "multi_turn",
        "chain_type": "ambiguous_beneficiary_account_then_transfer",
        "context": {
            "user_name": "Nguyen Van An",
            "user_phone": "0912 345 678",
            "current_date": "2026-06-02",
        },
        "turns": [
            {
                "role": "user",
                "content": "chuyển 800k cho chị Phương bên Vietcombank nha",
            },
            {
                "role": "assistant",
                "tool_call": {"name": "get_beneficiary_info", "parameters": {}},
            },
            {
                "role": "tool",
                "name": "get_beneficiary_info",
                "content": {
                    "beneficiaries": [
                        {
                            "contact_name": "Trần Thị Lan",
                            "to_account": "0900111222",
                            "bank_name": "VCB",
                        },
                        {
                            "contact_name": "Lê Phương Thảo",
                            "to_account": "0333444555",
                            "bank_name": "VCB",
                        },
                        {
                            "contact_name": "Nguyễn Minh Phương",
                            "to_account": "0987654321",
                            "bank_name": "ACB",
                        },
                        {
                            "contact_name": "Trần Thị Phương",
                            "to_account": "0123456789",
                            "bank_name": "VCB",
                        },
                        {
                            "contact_name": "Phạm Văn Bình",
                            "to_account": "0888777666",
                            "bank_name": "TCB",
                        },
                    ]
                },
            },
            {
                "role": "assistant",
                "content": {
                    "message": "Bạn muốn chuyển đến tài khoản nào?",
                    "matching_beneficiaries": [
                        {
                            "contact_name": "Trần Thị Phương",
                            "to_account": "0123456789",
                            "bank_name": "VCB",
                        }
                    ],
                },
            },
            {
                "role": "user",
                "content": {"to_account": "0123456789", "bank_name": "VCB"},
            },
            {
                "role": "assistant",
                "tool_call": {
                    "name": "initiate_transfer",
                    "parameters": {
                        "from_account": "ACC_USER",
                        "to_account": "0123456789",
                        "bank_name": "VCB",
                        "amount": 800000,
                    },
                },
            },
            {
                "role": "tool",
                "name": "initiate_transfer",
                "content": {"status": "success"},
            },
            {
                "role": "assistant",
                "content": "Giao dịch chuyển khoản đã được khởi tạo thành công.",
            },
        ],
    }


class BeneficiaryAccountSelectionTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.scenario = require_one_scenario(
            discover_scenarios(ROOT / "scenarios"),
            "multi_turn",
            None,
            "ambiguous_beneficiary_account_then_transfer",
        )

    def test_accepts_single_matching_candidate_selection(self) -> None:
        self.assertEqual(
            validate_sample(
                valid_single_candidate_selection_sample(),
                self.scenario,
            ),
            [],
        )

    def test_rejects_old_multiple_match_message(self) -> None:
        sample = valid_single_candidate_selection_sample()
        sample["turns"][3]["content"]["message"] = "Bạn vui lòng chọn tài khoản."

        errors = validate_sample(sample, self.scenario)

        self.assertIn(
            "assistant matching beneficiary message must match canonical text",
            errors,
        )

    def test_rejects_middle_name_match_for_addressed_given_name(self) -> None:
        sample = valid_single_candidate_selection_sample()
        wrong_match = {
            "contact_name": "Lê Phương Thảo",
            "to_account": "0333444555",
            "bank_name": "VCB",
        }
        sample["turns"][3]["content"]["matching_beneficiaries"] = [wrong_match]
        sample["turns"][4]["content"] = {
            "to_account": "0333444555",
            "bank_name": "VCB",
        }
        sample["turns"][5]["tool_call"]["parameters"]["to_account"] = "0333444555"

        errors = validate_sample(sample, self.scenario)

        self.assertIn(
            "assistant matching beneficiaries must equal tool result entries whose given name and bank match the user request",
            errors,
        )

    def test_rejects_matching_beneficiary_at_top(self) -> None:
        sample = valid_single_candidate_selection_sample()
        beneficiaries = sample["turns"][2]["content"]["beneficiaries"]
        beneficiaries.insert(0, beneficiaries.pop(3))

        errors = validate_sample(sample, self.scenario)

        self.assertIn(
            "beneficiary lookup must place a non-matching beneficiary before matching beneficiaries",
            errors,
        )

    def test_shuffle_postprocess_keeps_matching_beneficiary_off_top(self) -> None:
        sample = valid_single_candidate_selection_sample()
        beneficiaries = sample["turns"][2]["content"]["beneficiaries"]
        beneficiaries.insert(0, beneficiaries.pop(3))
        original_keys = {
            (
                item["contact_name"],
                item["to_account"],
                item["bank_name"],
            )
            for item in beneficiaries
        }

        shuffle_ambiguous_beneficiary_lookup(sample)
        shuffled = sample["turns"][2]["content"]["beneficiaries"]

        self.assertNotEqual(shuffled[0]["contact_name"], "Trần Thị Phương")
        self.assertEqual(
            original_keys,
            {
                (
                    item["contact_name"],
                    item["to_account"],
                    item["bank_name"],
                )
                for item in shuffled
            },
        )


if __name__ == "__main__":
    unittest.main()
