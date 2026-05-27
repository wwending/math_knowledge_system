# API

## 当前 Dashboard 主路径

当前 `Dashboard.vue` 上传主路径已接入 Draft 流水线：

- `POST /api/v1/assets`
- `POST /api/v1/drafts`
- `POST /api/v1/drafts/{draft_id}/recognize`
- `POST /api/v1/drafts/{draft_id}/save-to-bank`

`POST /api/v1/recognize` 未删除、未重构，保留为 legacy / 兼容入口。

## Draft 流水线

Draft 当前作为 Dashboard 上传主路径的开发基线，相关接口为：

- `POST /api/v1/drafts`
- `GET /api/v1/drafts/{draft_id}`
- `POST /api/v1/drafts/{draft_id}/recognize`
- `POST /api/v1/drafts/{draft_id}/save-to-bank`

这些接口已接入当前 Dashboard 主上传流程，但当前项目仍不表示生产可用。

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

- Draft 流水线是当前 Dashboard 上传主路径。
- `/api/v1/recognize` 未删除、未重构，保留为 legacy / 兼容入口。
- `runLegacyRecognition()` 仍保留在 `Dashboard.vue` 中，但当前上传按钮和主上传流程不引用它。
- 当前不表述为生产可用。
- 当前不表述为完整多页 PDF 或批量 draft 能力已完成。
