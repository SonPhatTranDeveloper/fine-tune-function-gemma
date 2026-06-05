"""Banking tool definitions used to derive FunctionGemma schemas."""

from __future__ import annotations

try:
    from transformers.utils import get_json_schema
except Exception:  # pragma: no cover
    get_json_schema = None


BANK_CODES = {
    "ACB",
    "VCB",
    "TCB",
    "MBB",
    "BIDV",
    "VPB",
    "VIB",
    "TPB",
    "STB",
    "HDB",
    "OCB",
    "MSB",
    "SHB",
    "EIB",
    "VAB",
    "BAB",
    "NAB",
    "LPB",
    "SEAB",
    "ABB",
}


def get_account_info(
    account_id: str,
    info_type: str,
    from_date: str | None = None,
    to_date: str | None = None,
    limit: int = 10,
) -> dict:
    """
    Lấy số dư hoặc lịch sử giao dịch của tài khoản hiện tại.

    Args:
        account_id: ID tài khoản người dùng, luôn dùng ACC_USER cho tài khoản hiện tại.
        info_type: Loại thông tin cần lấy: balance, transactions, hoặc both.
        from_date: Ngày bắt đầu theo định dạng YYYY-MM-DD, nếu cần lọc giao dịch.
        to_date: Ngày kết thúc theo định dạng YYYY-MM-DD, nếu cần lọc giao dịch.
        limit: Số lượng giao dịch tối đa cần trả về.
    """
    raise NotImplementedError("Schema only")


def get_beneficiary_info() -> dict:
    """
    Lấy toàn bộ danh sách người thụ hưởng đã lưu của khách hàng.

    Tool này không nhận tham số. Agent phải đọc danh sách trả về và tự chọn
    người thụ hưởng khớp với cách gọi của user.
    """
    raise NotImplementedError("Schema only")


def add_beneficiary(
    contact_name: str,
    to_account: str,
    bank_name: str,
) -> dict:
    """
    Lưu người thụ hưởng mới vào danh sách người nhận.

    Args:
        contact_name: Họ tên đầy đủ của người thụ hưởng, ví dụ Nguyễn Văn Minh.
        to_account: Số tài khoản hoặc số điện thoại người thụ hưởng.
        bank_name: Mã ngân hàng viết tắt như ACB, VCB, TCB, MBB, BIDV.
    """
    raise NotImplementedError("Schema only")


def initiate_transfer(
    from_account: str,
    to_account: str,
    bank_name: str,
    amount: int,
    message: str | None = None,
    beneficiary_name: str | None = None,
) -> dict:
    """
    Khởi tạo lệnh chuyển khoản.

    Args:
        from_account: Tài khoản nguồn, luôn dùng ACC_USER trong dữ liệu huấn luyện.
        to_account: Số tài khoản hoặc số điện thoại người nhận.
        bank_name: Mã ngân hàng viết tắt như ACB, VCB, TCB, MBB, BIDV.
        amount: Số tiền VND đã chuẩn hoá thành số nguyên.
        message: Nội dung chuyển khoản nếu user cung cấp.
        beneficiary_name: Tên người nhận nếu user cung cấp.
    """
    raise NotImplementedError("Schema only")


TOOL_FUNCTIONS = [
    get_account_info,
    get_beneficiary_info,
    add_beneficiary,
    initiate_transfer,
]
TOOL_NAMES = {fn.__name__ for fn in TOOL_FUNCTIONS}
REQUIRED_PARAMS = {
    "get_account_info": {"account_id", "info_type"},
    "get_beneficiary_info": set(),
    "add_beneficiary": {"contact_name", "to_account", "bank_name"},
    "initiate_transfer": {"from_account", "to_account", "bank_name", "amount"},
}


def tool_schemas() -> list[dict]:
    """Build JSON schemas for all registered tool functions."""
    if get_json_schema is None:
        return [
            {
                "type": "function",
                "function": {
                    "name": fn.__name__,
                    "description": (fn.__doc__ or "").strip(),
                    "parameters": {"type": "object", "properties": {}, "required": []},
                },
            }
            for fn in TOOL_FUNCTIONS
        ]
    return [get_json_schema(fn) for fn in TOOL_FUNCTIONS]
