# Flutter Gemma Banking FunctionGemma Integration Notes

Last verified: 2026-06-05

This document is context for a future Codex agent building a Flutter app around the banking tool-calling model:

`phattrandeveloper/functiongemma-270m-function-calling`

The Python reference notebook [notebooks/run_functiongemma_model.ipynb](../notebooks/run_functiongemma_model.ipynb) has already loaded this Hugging Face model and run one end-to-end tool-call loop. It generated `get_account_info`, appended a demo tool response, and produced the final Vietnamese assistant response with `pad_count: 0`.

## Current External Assumptions

Use these as current integration assumptions, but re-check docs before app implementation because `flutter_gemma` moves quickly.

- `flutter_gemma` current package page showed version `0.16.4`.
- FunctionGemma uses `ModelType.functionGemma`.
- `createChat(...)` supports `tools`, `supportsFunctionCalls`, `modelType`, `toolChoice`, and `systemInstruction`.
- Function calls are surfaced as `FunctionCallResponse` with `name` and `args`.
- Tool results should be returned with `Message.toolResponse(toolName: ..., response: ...)`.
- For app runtime, `flutter_gemma` expects an on-device model artifact such as `.task` or `.litertlm`, not the raw Python `model.safetensors` file.

Useful references:

- `flutter_gemma` package: https://pub.dev/packages/flutter_gemma
- `Tool` API: https://pub.dev/documentation/flutter_gemma/latest/core_tool/Tool-class.html
- `FlutterGemma` API: https://pub.dev/documentation/flutter_gemma/latest/core_api_flutter_gemma/FlutterGemma-class.html
- `InferenceModel.createChat`: https://pub.dev/documentation/flutter_gemma/latest/flutter_gemma_interface/InferenceModel-class.html
- FunctionGemma full function-calling loop: https://ai.google.dev/gemma/docs/functiongemma/full-function-calling-sequence-with-functiongemma
- HF safetensors to MediaPipe `.task`: https://ai.google.dev/gemma/docs/conversions/hf-to-mediapipe-task

## Model Artifact Requirement

The training/publishing notebook uploads a Transformers model repository. That is good for Python validation, but a Flutter app should install a converted artifact:

- Android/iOS mobile: `.task` is the safer first target.
- Android/iOS/Desktop: `.litertlm` may be preferred when conversion is available for the target runtime.
- Desktop requires `.litertlm`.
- Web function calling is currently not the main target; check the latest `flutter_gemma` limitations before promising web support.

Expected future URL shape after conversion:

```text
https://huggingface.co/phattrandeveloper/functiongemma-270m-function-calling/resolve/main/<converted-file>.task
```

or:

```text
https://huggingface.co/phattrandeveloper/functiongemma-270m-function-calling/resolve/main/<converted-file>.litertlm
```

Do not point `FlutterGemma.installModel(...).fromNetwork(...)` at `model.safetensors`.

## Creator Action Required

As the model creator, the extra thing you need to do is publish a Flutter-ready runtime artifact. You do not need to change the tool schema, prompt, or Flutter function-calling loop.

Current status:

- Python/Hugging Face model: ready.
- Flutter Gemma runtime file: must be created and uploaded.

Conversion notebook:

```text
notebooks/convert_functiongemma_to_flutter_gemma.ipynb
```

Recommended creator flow:

1. Download or use the local HF model folder for `phattrandeveloper/functiongemma-270m-function-calling`.
2. Convert the HF safetensors model into a MediaPipe `.task` file for Android/iOS first.
3. Upload the `.task` file to the same Hugging Face repo.
4. Use that exact `.task` URL in `FlutterGemma.installModel(modelType: ModelType.functionGemma)`.
5. Run the same recent-transaction smoke test in Flutter and confirm the first response is a `FunctionCallResponse(name: get_account_info, ...)`.

Suggested artifact name:

```text
functiongemma-270m-function-calling.task
```

After upload, the app URL should become:

```text
https://huggingface.co/phattrandeveloper/functiongemma-270m-function-calling/resolve/main/functiongemma-270m-function-calling.task
```

Upload command shape:

```bash
huggingface-cli upload \
  phattrandeveloper/functiongemma-270m-function-calling \
  path/to/functiongemma-270m-function-calling.task \
  functiongemma-270m-function-calling.task
```

If targeting desktop too, also publish a `.litertlm` artifact and use that URL on desktop builds.

Once the `.task` or `.litertlm` artifact exists, the Flutter app should not need manual FunctionGemma prompt formatting. Keep `modelType: ModelType.functionGemma`, pass `tools`, and return tool results through `Message.toolResponse(...)`.

### Conversion Outline

Follow Google's conversion guide for HF safetensors to MediaPipe task. The guide's core steps are:

1. Install `litert-torch`.
2. Build the 270M Gemma model from the HF folder.
3. Convert to `.tflite` with a suitable KV cache size and quantization.
4. Bundle the `.tflite` model and tokenizer into `.task` using `mediapipe.tasks.python.genai.bundler`.

Command/script outline adapted to this model:

```bash
python -m venv litert-torch
source litert-torch/bin/activate
pip install "litert-torch>=0.8.0" huggingface_hub[cli]
hf download phattrandeveloper/functiongemma-270m-function-calling \
  --local-dir hf-functiongemma-banking
```

```python
from litert_torch.generative.examples.gemma3 import gemma3
from litert_torch.generative.layers import kv_cache
from litert_torch.generative.utilities import converter
from litert_torch.generative.utilities.export_config import ExportConfig

pytorch_model = gemma3.build_model_270m("hf-functiongemma-banking")

export_config = ExportConfig()
export_config.kvcache_layout = kv_cache.KV_LAYOUT_TRANSPOSED
export_config.mask_as_input = True

converter.convert_to_tflite(
    pytorch_model,
    output_path="converted",
    output_name_prefix="functiongemma-banking",
    prefill_seq_len=2048,
    kv_cache_max_len=4096,
    quantize="dynamic_int8",
    export_config=export_config,
)
```

Then bundle:

```bash
python -m venv mediapipe-bundler
source mediapipe-bundler/bin/activate
pip install mediapipe
```

```python
from mediapipe.tasks.python.genai import bundler

config = bundler.BundleConfig(
    tflite_model="converted/functiongemma-banking.tflite",
    tokenizer_model="hf-functiongemma-banking/tokenizer.model",
    start_token="<bos>",
    stop_tokens=["<eos>", "<end_of_turn>"],
    output_filename="functiongemma-270m-function-calling.task",
    prompt_prefix="<start_of_turn>user\n",
    prompt_suffix="<end_of_turn>\n<start_of_turn>model\n",
)
bundler.create_bundle(config)
```

Important: verify the actual `.tflite` filename emitted by the converter before bundling. If the HF tokenizer folder does not contain `tokenizer.model`, inspect the converted FunctionGemma examples from `flutter_gemma` or MediaPipe because the bundle needs the tokenizer asset expected by the target runtime.

### Definition of Ready

The model is ready for app development when all of these are true:

- The Hugging Face repo contains `functiongemma-270m-function-calling.task` or a target-specific `.litertlm`.
- The app installs that file with `ModelType.functionGemma`.
- A Flutter smoke test sends `Cho mình xem lịch sử giao dịch 7 ngày gần đây`.
- The first model event is a structured `FunctionCallResponse` for `get_account_info`.
- The tool args include `account_id=ACC_USER`, `info_type=transactions`, `from_date`, `to_date`, and `limit`.
- After `Message.toolResponse(...)`, the final text is `Đã lấy lịch sử giao dịch theo khoảng thời gian yêu cầu thành công.` or close equivalent.

## Banking System Instruction

Use the same developer/system context shape that the model saw in training. In Flutter, pass this as `systemInstruction` when creating the chat.

Template source: [config/settings.yaml](../config/settings.yaml)

```text
Bạn là trợ lý ngân hàng thông minh, hỗ trợ khách hàng bán lẻ tại Việt Nam.
Thông tin khách hàng hiện tại:
- Họ tên: {user_name}
- Số điện thoại: {user_phone}
- Ngày hôm nay: {current_date}
Bạn có thể gọi các công cụ sau để thực hiện yêu cầu của khách hàng.
```

Runtime values must be set per customer/session. `current_date` matters for recent-transaction windows. Use Vietnamese diacritics for customer names when the profile has them.

Concrete example:

```text
Bạn là trợ lý ngân hàng thông minh, hỗ trợ khách hàng bán lẻ tại Việt Nam.
Thông tin khách hàng hiện tại:
- Họ tên: Nguyễn Thị Lan
- Số điện thoại: 0334 424 299
- Ngày hôm nay: 2026-05-16
Bạn có thể gọi các công cụ sau để thực hiện yêu cầu của khách hàng.
```

## Tool Contract

Source of truth: [src/tools/banking.py](../src/tools/banking.py)

Keep names and argument keys exact. The model was trained on these names.

### `get_account_info`

Purpose: get balance or transactions for the current user account.

Required:

- `account_id`: always `ACC_USER`
- `info_type`: `balance`, `transactions`, or `both`

Optional:

- `from_date`: `YYYY-MM-DD`
- `to_date`: `YYYY-MM-DD`
- `limit`: integer, default training pattern is `10`

### `get_beneficiary_info`

Purpose: return all saved beneficiaries. No arguments.

The model expects to inspect/filter the returned beneficiaries itself.
For ambiguous saved-recipient transfers, return the full saved-beneficiary list
in natural shuffled order, not with matching recipients at the top. The trained
behavior treats phrases such as `chị Phương` as a given-name match: `Trần Thị
Phương` is a match, while `Lê Phương Thảo` is not because `Phương` is a middle
name there.

### `add_beneficiary`

Purpose: save a new beneficiary.

Required:

- `contact_name`
- `to_account`
- `bank_name`

### `initiate_transfer`

Purpose: create a transfer.

Required:

- `from_account`: always `ACC_USER`
- `to_account`
- `bank_name`
- `amount`: integer VND

Optional:

- `message`
- `beneficiary_name`

Known bank codes from training: `ACB`, `VCB`, `TCB`, `MBB`, `BIDV`, `VPB`, `VIB`, `TPB`, `STB`, `HDB`, `OCB`, `MSB`, `SHB`, `EIB`, `VAB`, `BAB`, `NAB`, `LPB`, `SEAB`, `ABB`.

## Dart Tool Declarations

Sketch only. Confirm imports against the app's installed `flutter_gemma` version.

```dart
final bankingTools = <Tool>[
  Tool(
    name: 'get_account_info',
    description: 'Lay so du hoac lich su giao dich cua tai khoan hien tai.',
    parameters: {
      'type': 'object',
      'properties': {
        'account_id': {
          'type': 'string',
          'description': 'ID tai khoan nguoi dung, luon dung ACC_USER.',
        },
        'info_type': {
          'type': 'string',
          'description': 'balance, transactions, hoac both.',
        },
        'from_date': {
          'type': 'string',
          'description': 'YYYY-MM-DD neu can loc giao dich.',
        },
        'to_date': {
          'type': 'string',
          'description': 'YYYY-MM-DD neu can loc giao dich.',
        },
        'limit': {
          'type': 'integer',
          'description': 'So giao dich toi da.',
        },
      },
      'required': ['account_id', 'info_type'],
    },
  ),
  Tool(
    name: 'get_beneficiary_info',
    description: 'Lay toan bo danh sach nguoi thu huong da luu.',
    parameters: {
      'type': 'object',
      'properties': {},
      'required': [],
    },
  ),
  Tool(
    name: 'add_beneficiary',
    description: 'Luu nguoi thu huong moi vao danh sach nguoi nhan.',
    parameters: {
      'type': 'object',
      'properties': {
        'contact_name': {'type': 'string'},
        'to_account': {'type': 'string'},
        'bank_name': {'type': 'string'},
      },
      'required': ['contact_name', 'to_account', 'bank_name'],
    },
  ),
  Tool(
    name: 'initiate_transfer',
    description: 'Khoi tao lenh chuyen khoan.',
    parameters: {
      'type': 'object',
      'properties': {
        'from_account': {'type': 'string'},
        'to_account': {'type': 'string'},
        'bank_name': {'type': 'string'},
        'amount': {'type': 'integer'},
        'message': {'type': 'string'},
        'beneficiary_name': {'type': 'string'},
      },
      'required': ['from_account', 'to_account', 'bank_name', 'amount'],
    },
  ),
];
```

## Installation and Chat Creation Sketch

Use the modern `flutter_gemma` API.

```dart
Future<void> installBankingModel(String modelUrl, String? hfToken) async {
  await FlutterGemma.initialize(
    huggingFaceToken: hfToken,
    maxDownloadRetries: 10,
  );

  await FlutterGemma.installModel(
    modelType: ModelType.functionGemma,
  )
      .fromNetwork(modelUrl, token: hfToken)
      .withProgress((progress) {
        // progress is 0..100 in current flutter_gemma.
      })
      .install();
}

Future<InferenceChat> createBankingChat({
  required String systemInstruction,
}) async {
  final model = await FlutterGemma.getActiveModel(
    maxTokens: 2048,
    preferredBackend: PreferredBackend.gpu,
  );

  return model.createChat(
    temperature: 0.0,
    randomSeed: 42,
    topK: 1,
    modelType: ModelType.functionGemma,
    supportsFunctionCalls: true,
    tools: bankingTools,
    systemInstruction: systemInstruction,
  );
}
```

If GPU fails on a device, fall back to CPU. Keep `temperature: 0.0` and `topK: 1` for deterministic banking actions.

## Runtime Loop

The app must treat function calls as actions, not displayable chat text.

High-level loop:

1. Add the user message with `Message.text(text: userText, isUser: true)`.
2. Generate response stream.
3. If `TextResponse`, append token to a text buffer for UI display.
4. If `FunctionCallResponse`, validate `name` and `args`.
5. Execute only whitelisted native banking functions.
6. Add `Message.toolResponse(toolName: response.name, response: toolResult)`.
7. Generate again.
8. Repeat until text final answer, user clarification, or max tool depth.

Recommended max tool depth: `3`. This covers lookup-then-transfer flows:

`get_beneficiary_info -> initiate_transfer`

Sketch:

```dart
Future<String> sendBankingMessage(InferenceChat chat, String userText) async {
  await chat.addQueryChunk(Message.text(text: userText, isUser: true));
  final buffer = StringBuffer();

  for (var depth = 0; depth < 4; depth++) {
    FunctionCallResponse? pendingCall;

    await for (final response in chat.generateChatResponseAsync()) {
      if (response is TextResponse) {
        buffer.write(response.token);
      } else if (response is FunctionCallResponse) {
        pendingCall = response;
        break;
      }
    }

    if (pendingCall == null) {
      return buffer.toString().trim();
    }

    final toolResult = await dispatchBankingTool(
      pendingCall.name,
      pendingCall.args,
    );

    await chat.addQueryChunk(
      Message.toolResponse(
        toolName: pendingCall.name,
        response: toolResult,
      ),
    );
  }

  throw StateError('Exceeded max banking tool-call depth');
}
```

## Tool Dispatcher Rules

Never dynamically call arbitrary functions by model output. Validate everything.

Required validations:

- Tool name is one of the four known tools.
- Required args are present.
- `from_account == ACC_USER` for transfers.
- `account_id == ACC_USER` for account info.
- `amount` is integer VND and within app policy limits.
- `bank_name` is one of the known bank codes.
- `from_date` and `to_date` are valid `YYYY-MM-DD`.
- Recent transaction periods should be `1..30` days inclusive unless product changes the policy.
- For money movement, show the app's normal confirmation/authorization UI before committing transfer.

Example dispatcher shape:

```dart
Future<Map<String, dynamic>> dispatchBankingTool(
  String name,
  Map<String, dynamic> args,
) async {
  switch (name) {
    case 'get_account_info':
      validateAccountInfoArgs(args);
      return bankingApi.getAccountInfo(
        accountId: 'ACC_USER',
        infoType: args['info_type'] as String,
        fromDate: args['from_date'] as String?,
        toDate: args['to_date'] as String?,
        limit: (args['limit'] as num?)?.toInt() ?? 10,
      );

    case 'get_beneficiary_info':
      return bankingApi.getBeneficiaries();

    case 'initiate_transfer':
      validateTransferArgs(args);
      return bankingApi.initiateTransfer(
        fromAccount: 'ACC_USER',
        toAccount: args['to_account'] as String,
        bankName: args['bank_name'] as String,
        amount: (args['amount'] as num).toInt(),
        message: args['message'] as String?,
        beneficiaryName: args['beneficiary_name'] as String?,
      );

    case 'add_beneficiary':
      validateAddBeneficiaryArgs(args);
      return bankingApi.addBeneficiary(
        contactName: args['contact_name'] as String,
        toAccount: args['to_account'] as String,
        bankName: args['bank_name'] as String,
      );

    default:
      return {
        'status': 'error',
        'message': 'Unknown tool: $name',
      };
  }
}
```

## Expected Scenario Behaviors

These are the five trained scenario families. Use them as app QA prompts.

| Scenario | Expected behavior |
| --- | --- |
| `recent_transactions_time_period` | Call `get_account_info` with `info_type=transactions`, `from_date`, `to_date`, and `limit`. Time periods should be up to 30 days. |
| `full_bank_account_number` | Call `initiate_transfer`; normalize full/informal bank name to short code and amount to integer VND. |
| `vendor_payment` | Call `initiate_transfer` from field-style payment details such as bank, account, content, amount. |
| `missing_bank_code` | Ask `Bạn muốn chuyển đến ngân hàng nào vậy?`; after user supplies bank, call `initiate_transfer`. |
| `ambiguous_beneficiary_account_then_transfer` | Call `get_beneficiary_info`; filter by same bank plus addressed given name only; return `matching_beneficiaries` with 1-3 candidate accounts and ask `Bạn muốn chuyển đến tài khoản nào?`; after user selects, call `initiate_transfer`. |

Canonical Vietnamese final messages seen in training:

```text
Giao dịch chuyển khoản đã được khởi tạo thành công.
Đã lấy lịch sử giao dịch theo khoảng thời gian yêu cầu thành công.
```

## Known Good Python Reference

[notebooks/run_functiongemma_model.ipynb](../notebooks/run_functiongemma_model.ipynb) verifies the raw HF model in Python.

Known good generation path:

```python
inputs = tokenizer.apply_chat_template(
    messages,
    tools=tools,
    add_generation_prompt=True,
    return_dict=True,
    return_tensors="pt",
)

outputs = model.generate(
    **inputs.to(model.device),
    pad_token_id=tokenizer.eos_token_id,
    max_new_tokens=192,
    do_sample=False,
    bad_words_ids=[[tokenizer.pad_token_id]],
)
```

Known output for:

```text
Cho mình xem lịch sử giao dịch 7 ngày gần đây
```

First assistant:

```text
<start_function_call>call:get_account_info{account_id:<escape>ACC_USER<escape>,from_date:<escape>2026-05-27<escape>,info_type:<escape>transactions<escape>,limit:10,to_date:<escape>2026-06-02<escape>}<end_function_call><start_function_response>
```

Final assistant after demo tool response:

```text
Đã lấy lịch sử giao dịch theo khoảng thời gian yêu cầu thành công.<end_of_turn>
```

Both had `pad_count: 0`.

## Debugging Notes

If Flutter app returns raw FunctionGemma tokens instead of `FunctionCallResponse`:

- Confirm `modelType: ModelType.functionGemma`.
- Confirm `supportsFunctionCalls: true`.
- Confirm the model artifact is a FunctionGemma-compatible `.task` or `.litertlm`.
- Confirm the app is not using a generic Gemma model type.

If Python/Jupyter returns repeated `<pad>`:

- Restart kernel and run all cells.
- Ensure prompt tokenization uses `apply_chat_template(..., return_dict=True, return_tensors="pt")` directly.
- Do not render template to string and then call `tokenizer(prompt)` with default special-token behavior; that can add an extra BOS token.
- Suppress pad token with `bad_words_ids=[[tokenizer.pad_token_id]]` during Python smoke tests.

If Flutter returns wrong dates:

- Check `current_date` in `systemInstruction`.
- The model learns relative windows from that date, not device time unless you pass device time.

If Flutter calls a dangerous or malformed transfer:

- Do not execute blindly. Validate args and use the normal banking authorization flow.

## Implementation Checklist for Future App

- Convert/publish app-ready `.task` or `.litertlm` artifact.
- Add `flutter_gemma` dependency.
- Initialize `FlutterGemma` at startup.
- Install the model with `ModelType.functionGemma`.
- Build `bankingTools` from this document or generate them from `src/tools/banking.py`.
- Build per-session `systemInstruction` with current customer context and date.
- Create chat with function calling enabled.
- Implement a strict `dispatchBankingTool` allowlist.
- Add UI states for loading model, downloading model, generating, tool execution, clarification, and final response.
- Add QA prompts for all five scenarios above.
