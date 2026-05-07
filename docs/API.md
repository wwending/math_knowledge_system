# API

## 当前主入口

当前前端主链路仍然是：

- `POST /api/v1/recognize`

`Dashboard.vue` 尚未切换到 Draft 流水线。`/api/v1/recognize` 未删除、未重构，仍是当前 MVP 主入口。

## Draft 后端旁路流水线

第七轮新增后端旁路正式流水线接口：

- `POST /api/v1/drafts`
- `GET /api/v1/drafts/{draft_id}`
- `POST /api/v1/drafts/{draft_id}/recognize`
- `POST /api/v1/drafts/{draft_id}/save-to-bank`

这些接口目前表示后端旁路能力，不表示正式流水线已经接入主前端，也不表示生产可用。

## Draft 状态

- `draft_created`
- `recognizing`
- `draft_ready`
- `failed`
- `saved_to_bank`

## 落库行为

- `DraftEvent`：创建、开始识别、识别成功/失败、保存入题库都会写入。
- `OCRRun`：Draft 识别后写入，失败也记录错误。
- `LLMRun`：OCR 成功后写入，LLM 失败记录错误并允许 `partial_success`。
- `QuestionRevision`：保存入题库时创建 v1，并关联 `source_asset_id`、`ocr_run_id`、`llm_run_id`。

## 当前边界

- Draft 流水线目前是后端旁路能力。
- 当前前端主链路仍然是 `/api/v1/recognize`。
- `Dashboard.vue` 尚未切换到 Draft 流水线。
- `/api/v1/recognize` 未删除、未重构，仍是当前 MVP 主入口。
- 当前不表述为生产可用。
- 当前不表述为完整多页 PDF 或批量 draft 能力已完成。
