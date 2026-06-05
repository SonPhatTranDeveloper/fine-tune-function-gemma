# Vietnamese User-Language Style Guide

Use this guide as soft guidance for user utterances only. It should improve
real-world diversity while keeping tool calls, assistant replies, dates,
amounts, account numbers, and bank codes clean and normalized.

## Distribution

Aim for a balanced mix:

- About half of user messages should be clean or lightly casual Vietnamese.
- About half may include one or more real-world noise patterns below.
- Do not force every sample to be noisy.
- Avoid stacking too many noise types in one short utterance unless the scenario
  is explicitly about pasted vendor/payment text.

## Guardrails

- Apply these variations only to the `user` field.
- Keep `tool_call.parameters` normalized and schema-valid.
- Keep `bank_name` in tool parameters as a short bank code such as `ACB`, `VCB`,
  `TCB`, `MBB`, or `BIDV`.
- Keep dates in tool parameters as `YYYY-MM-DD`.
- Keep amounts in tool parameters as integer VND.
- Keep assistant clarification responses clear, polite, and correctly accented.
- Do not create real personal information; use fake names, fake phone numbers,
  and fake account numbers.

## No-Diacritic Vietnamese

Include both full-strip and partial-strip forms.

Full-strip examples:

- `chuyen 500k cho anh minh qua vietcombank`
- `kiem tra giao dich tu hom qua toi nay giup minh`
- `luu so tk 123456789 ngan hang acb cho nguyen van an`

Partial-strip examples:

- `chuyen 2 triệu qua techcombank cho chi Lan`
- `xem giao dich tu hom qua tới nay`
- `lưu stk 99887766 bên Vietcombank cho Nguyen Van Minh`

## Abbreviations

Use common banking abbreviations naturally:

- `stk`, `so tk`, `số tk`: account number
- `tk`: account
- `nh`: bank
- `ck`: transfer
- `nd`: transfer memo/message
- `sdt`, `sđt`: phone number
- `gd`: transaction
- `sd`: balance

Examples:

- `ck 350k qua stk 123456789 nh acb nd tien an trua`
- `xem gd hom qua giup minh`
- `luu sdt 0909123456 nh vietcombank cho Tran Van Binh`

## Typos, Spacing, And Casing

Allow light typing noise:

- Bank names with inconsistent casing: `vietcombank`, `TechComBank`, `ACb`.
- Missing spaces: `chuyenkhoan`, `sotien`, `soTK`.
- Extra spaces: `chuyen   1tr   qua   acb`.
- Minor spelling variants that remain understandable.

Examples:

- `chuyenkhoan 1tr cho Nguyen An soTK 123123123 techcombank`
- `gui 250k qua ACb stk 9988776655`
- `kiem tra sd tk minh voi`

## Vendor Or Payment Paste

For pasted payment requests, vary labels and formatting. Line breaks may be
clean, messy, or partially missing.

Possible labels:

- `Ngan hang`, `NH`, `Bank`, `Bank name`
- `STK`, `So TK`, `TK nhan`, `Account`
- `Noi dung`, `ND`, `memo`, `content`
- `So tien`, `Amount`, `Tong tien`, `Thanh tien`

Examples:

```text
NH: ACB
STK 123456789
ND: DH9988
Amount: 2.350.000
```

```text
bank vietcombank / account 99887766 / memo hoa don 102 / amount 750k
```

```text
Ngan hang Techcombank
So TK: 190012345678
so tien 1tr2
noi dung: thanh toan don hang
```

## Light Code-Switching

Use English only when it sounds like real user input, mostly in pasted or
commerce-related messages:

- `bank`
- `amount`
- `memo`
- `transfer`
- `account`
- `content`

Examples:

- `transfer 500k to account 123456789 bank ACB memo lunch`
- `bank vietcombank account 66889900 amount 2m`

## Bank Name Normalization

User text may contain full, informal, or noisy bank names. Tool parameters must
use short codes.

Examples:

- User `Vietcombank`, `ngân hàng ngoại thương`, `vcb` -> parameter `VCB`
- User `Techcombank`, `tech`, `TCB` -> parameter `TCB`
- User `ngân hàng quân đội`, `mb bank`, `MBBank` -> parameter `MBB`
- User `Á Châu`, `acb` -> parameter `ACB`
- User `BIDV`, `đầu tư phát triển` -> parameter `BIDV`
