from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from generator.scenario import discover_scenarios, require_one_scenario  # noqa: E402
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
                "content": "chuyển 800k cho anh Hùng bên Vietcombank nha",
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
                            "contact_name": "Nguyễn Minh Hùng",
                            "to_account": "0987654321",
                            "bank_name": "ACB",
                        },
                        {
                            "contact_name": "Nguyễn Văn Hùng",
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
                            "contact_name": "Nguyễn Văn Hùng",
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


if __name__ == "__main__":
    unittest.main()
