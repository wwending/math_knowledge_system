# API

## 当前 Dashboard 主路径

当前 `Dashboard.vue` 上传主路径已接入 Draft 流水线：

- `POST /api/v1/assets`
- `POST /api/v1/drafts`
- `POST /api/v1/drafts/{draft_id}/recognize`
- `POST /api/v1/drafts/{draft_id}/save-to-bank`

`POST /api/v1/recognize` 未删除、未重构，保留为 legacy / 兼容入口。

当前推荐 smoke 文档为 `docs/API_SMOKE_DRAFT_FLOW.md`；`docs/API_SMOKE_DRAFT_PIPELINE.md` 是脚本化 smoke 补充文档。

## 组卷 MVP

第十七轮新增后端最小组卷能力。当前只支持登录用户手动选择自己题库中的题目生成草稿试卷，不支持智能组卷、导出、前端组卷或拖拽排序。

接口：

- `POST /api/v1/papers`
  - 创建试卷。
  - 请求体：`title`、可选 `description`、`items`。
  - `items` 中每项包含 `question_id` 和可选 `score`。
  - `items` 不能为空；同一张试卷内重复 `question_id` 返回冲突错误。
  - 只能使用当前登录用户自己的题目；不存在或不属于当前用户的题目按不存在处理。
  - 返回 `PaperRead`，包含 `items`、`item_count`、`total_score`。

- `GET /api/v1/papers`
  - 返回当前登录用户自己的试卷列表。
  - 返回每张试卷的 `id`、`title`、`status`、`item_count`、`total_score`、`created_at`、`updated_at`。

- `GET /api/v1/papers/{paper_id}`
  - 返回当前登录用户自己的试卷详情。
  - 试卷不存在或不属于当前用户时返回 `404`。

组卷快照：

- `PaperItem` 创建时保存题目内容快照，避免题库后续编辑导致历史试卷内容被动变化。
- 如果题目已有 `QuestionRevision`，优先使用最新 revision 的内容生成快照。
- 当前返回字段包括 `content_snapshot`、`answer_snapshot`、`analysis_snapshot`、`knowledge_tags_snapshot`。

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
- Draft 后端异常契约已阶段性收口：缺失 asset/draft 返回 `404`，非图片 asset recognize 返回 `400`，状态冲突和重复保存返回 `409`。
- 当前不表述为生产可用。
- 当前不表述为完整多页 PDF 或批量 draft 能力已完成。
