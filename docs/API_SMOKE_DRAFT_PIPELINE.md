# Draft Pipeline API Smoke

> 补充文档：本文档说明 `scripts/smoke_draft_pipeline.ps1` 的脚本化 smoke 用法，适合在后端已启动、账号和图片样例已准备好时执行自动/半自动检查。
>
> 当前推荐入口：[API_SMOKE_DRAFT_FLOW.md](./API_SMOKE_DRAFT_FLOW.md) 负责说明 Dashboard Draft 主路径、异常契约、legacy 边界和人工/API smoke 验收标准。两个文档暂不合并，避免把脚本参数说明和主路径验收口径混在一起。

This smoke script verifies the Draft pipeline APIs used by the current Dashboard upload main flow.

## Preconditions

- Backend is running, for example at `http://127.0.0.1:8000`.
- Database migrations have been applied: `alembic upgrade head`.
- An administrator or test user exists and can log in.
- Required server-side environment variables are configured for live recognition:
  - `BAIDU_API_KEY`
  - `BAIDU_SECRET_KEY`
  - `DEEPSEEK_API_KEY`
- A small test image is available on disk.

## Run

Basic API checks without OCR/LLM:

```powershell
.\scripts\smoke_draft_pipeline.ps1 `
  -Username "test-phone-or-username" `
  -Password "test-password" `
  -ImagePath ".\test_data\sample.png" `
  -SkipRecognize
```

Auto mode checks local `BAIDU_API_KEY`, `BAIDU_SECRET_KEY`, and `DEEPSEEK_API_KEY`. If any are missing, it skips recognize and save-to-bank with a clear message:

```powershell
.\scripts\smoke_draft_pipeline.ps1 `
  -Username "test-phone-or-username" `
  -Password "test-password" `
  -ImagePath ".\test_data\sample.png"
```

Live OCR/LLM mode calls the backend Draft recognize endpoint even if the current shell does not have those variables:

```powershell
.\scripts\smoke_draft_pipeline.ps1 `
  -BaseUrl "http://127.0.0.1:8000/api/v1" `
  -Username "test-phone-or-username" `
  -Password "test-password" `
  -ImagePath ".\test_data\sample.png" `
  -LiveRecognize
```

Do not put real passwords or API keys in the script. Do not commit `backend/.env`.

## Covered APIs

The script calls these APIs in order:

- `POST /api/v1/auth/login`
- `POST /api/v1/assets`
- `POST /api/v1/drafts`
- `GET /api/v1/drafts/{draft_id}`
- `POST /api/v1/drafts/{draft_id}/recognize`
- `POST /api/v1/drafts/{draft_id}/save-to-bank`

In `-SkipRecognize` mode, the last two live pipeline steps are intentionally skipped. In auto mode, they are skipped when local OCR/LLM variables are missing.

## Expected Success Shape

A successful basic run prints:

- Access token prefix from login.
- `source_asset_id` from asset upload.
- `draft_id` and `draft_status` after creation.
- The same `draft_id` and current status from `GET /drafts/{draft_id}`.

A successful live run continues with:

- Recognize response with `draft_status: draft_ready`.
- `partial_success: False` when OCR and DeepSeek both succeed.
- `partial_success: True` when OCR succeeds but LLM fails and raw OCR text is retained.
- Save-to-bank response with `question_id`, `question_revision_id`, and `rev_no`.

If recognize fails because of OCR configuration, the script prints `error_type` and `error` from the API response and does not call save-to-bank.

## Assertions

The script fails fast when:

- Login does not return `access_token`.
- Asset upload does not return `source_asset_id`, `asset_id`, or `id`.
- Draft creation does not return a draft id.
- `GET /drafts/{draft_id}` does not return the created draft.
- Recognize returns a status outside the current accepted set: `draft_ready`, `failed`, `recognizing`.
- Save-to-bank is attempted only for `draft_ready`.
- Save-to-bank does not return both `question_id` and `question_revision_id`.

## Common Failures

- `401`: token is missing, expired, invalid, or login credentials are wrong.
- `400`: Draft recognize was called for a non-image asset; current Draft recognize only supports image assets.
- `404`: asset or draft does not exist, or the id belongs to another user.
- `409`: draft status does not allow `save-to-bank`; only `draft_ready` is valid.
- `409`: a draft already saved to bank cannot be recognized or saved again; the current contract rejects duplicates and does not recreate Question or QuestionRevision.
- OCR key not configured: check `BAIDU_API_KEY` and `BAIDU_SECRET_KEY` in the backend runtime environment.
- DeepSeek key not configured: check `DEEPSEEK_API_KEY` in the backend runtime environment.
- File path error: `ImagePath` does not exist or points to a non-file path.
- Unsupported file type: `/assets` accepts only MIME types allowed by the backend.

## Current Boundary

- `Dashboard.vue` upload now uses the Draft pipeline as the main flow.
- `POST /api/v1/recognize` is still kept as a legacy / compatibility entry.
- This script validates the Draft API sequence; it does not remove or replace the legacy endpoint.
- The project is startable, verifiable, and ready for continued development, but this smoke script does not prove production readiness.
