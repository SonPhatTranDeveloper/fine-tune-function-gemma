from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from generator.scenario import require_one_scenario, discover_scenarios  # noqa: E402
from validation.rules import validate_sample  # noqa: E402


def valid_sample() -> dict:
    return {
        "scenario_id": "recent_transactions_time_period",
        "sample_type": "single_turn",
        "tool": "get_account_info",
        "context": {
            "user_name": "Nguyen Van An",
            "user_phone": "0912 345 678",
            "current_date": "2026-06-02",
        },
        "style": "clean",
        "dialect": "northern",
        "note": "seven-day inclusive period",
        "turns": [
            {"role": "user", "content": "Cho mình xem giao dịch 7 ngày gần đây"},
            {
                "role": "assistant",
                "tool_call": {
                    "name": "get_account_info",
                    "parameters": {
                        "account_id": "ACC_USER",
                        "info_type": "transactions",
                        "from_date": "2026-05-27",
                        "to_date": "2026-06-02",
                        "limit": 10,
                    },
                },
            },
            {
                "role": "tool",
                "name": "get_account_info",
                "content": {
                    "status": "success",
                    "account_id": "ACC_USER",
                    "transactions": [
                        {
                            "date": "2026-06-02",
                            "amount": -250000,
                            "account": "1023456789",
                            "description": "Chuyen khoan tien cafe",
                        }
                    ],
                },
            },
            {
                "role": "assistant",
                "content": "Đã lấy lịch sử giao dịch theo khoảng thời gian yêu cầu thành công.",
            },
        ],
    }


class RecentTransactionsTimePeriodTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.scenario = require_one_scenario(
            discover_scenarios(ROOT / "scenarios"),
            "single_turn",
            "get_account_info",
            "recent_transactions_time_period",
        )

    def test_accepts_inclusive_seven_day_period(self) -> None:
        self.assertEqual(validate_sample(valid_sample(), self.scenario), [])

    def test_accepts_inclusive_thirty_day_period(self) -> None:
        sample = valid_sample()
        sample["turns"][0]["content"] = "Cho mình xem giao dịch 30 ngày gần đây"
        sample["turns"][1]["tool_call"]["parameters"]["from_date"] = "2026-05-04"

        self.assertEqual(validate_sample(sample, self.scenario), [])

    def test_rejects_two_day_phrase_with_wrong_range(self) -> None:
        sample = valid_sample()
        sample["turns"][0]["content"] = "xem giúp mình giao dịch 2 ngày gần đây"

        errors = validate_sample(sample, self.scenario)

        self.assertIn(
            "recent_transactions_time_period from_date must match the requested inclusive period",
            errors,
        )

    def test_rejects_period_above_thirty_days(self) -> None:
        sample = valid_sample()
        sample["turns"][0]["content"] = "Cho mình xem giao dịch 31 ngày gần đây"
        sample["turns"][1]["tool_call"]["parameters"]["from_date"] = "2026-05-03"

        errors = validate_sample(sample, self.scenario)

        self.assertIn(
            "recent_transactions_time_period user request must specify a recent period from 1 to 30 days",
            errors,
        )

    def test_rejects_transaction_outside_requested_range(self) -> None:
        sample = valid_sample()
        sample["turns"][2]["content"]["transactions"][0]["date"] = "2026-05-26"

        errors = validate_sample(sample, self.scenario)

        self.assertIn("turn 2: transaction 0.date is before from_date", errors)


if __name__ == "__main__":
    unittest.main()
