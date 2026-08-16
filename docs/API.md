# API

## 当前 Dashboard 主路径

当前 `Dashboard.vue` 上传主路径已接入 Draft 流水线：

- `POST /api/v1/assets`
- `POST /api/v1/drafts`
- `POST /api/v1/drafts/{draft_id}/recognize`
- `POST /api/v1/drafts/{draft_id}/save-to-bank`

`POST /api/v1/recognize` 未删除、未重构，保留为 legacy / 兼容入口。

当前推荐 smoke 文档为 `docs/API_SMOKE_DRAFT_FLOW.md`；`docs/API_SMOKE_DRAFT_PIPELINE.md` 是脚本化 smoke 补充文档。

## LLM 题目分析元数据

第十九轮性能收口后，交互式 Draft recognize 只强制等待 OCR、`corrected_text` 和知识点标签；题型与五星难度作为增强元数据，在保存入题库后由后台任务补全。

LLM 目标输出结构：

```json
{
  "corrected_text": "修复后的题目文本",
  "knowledge_tags": ["圆与方程", "切线"],
  "question_type": "single_choice",
  "difficulty": {
    "level": 3,
    "label": "中等",
    "confidence": 0.78,
    "reason": "涉及圆的切线方程与参数代入，需要两步推理。"
  }
}
```

兼容说明：

- 旧字段 `tags` 仍兼容；如 LLM 返回 `tags` 但没有 `knowledge_tags`，后端会转换为知识点标签。
- `corrected_text` 是主结果；`question_type` 和 `difficulty` 是增强结果。
- `POST /api/v1/drafts/{draft_id}/recognize` 不再保证返回题型和难度，相关字段可为空。
- `POST /api/v1/drafts/{draft_id}/save-to-bank` 创建 `Question` 后将 `metadata_status` 设为 `pending`，并用 FastAPI `BackgroundTasks` 后台补全题型与难度。
- 后台元数据评估失败不会回滚已经保存入题库的题目，失败时 `metadata_status=failed` 并写入 `metadata_error`。
- `question_type` 可选值为 `single_choice`、`multiple_choice`、`fill_blank`、`solution`、`judge`、`unknown`。
- `difficulty.level` 为 1-5 星整数，`difficulty.confidence` 为 0-1 小数，`difficulty.reason` 是简短理由。

相关 API 返回字段：

- `POST /api/v1/drafts/{draft_id}/recognize` 和 `GET /api/v1/drafts/{draft_id}` 仍保留可空的 `question_type`、`difficulty_level`、`difficulty_label`、`difficulty_confidence`、`difficulty_reason` 字段用于兼容。
- `GET /api/v1/questions` 和 `GET /api/v1/questions/{question_id}` 返回题型、难度、置信度、理由、评估模型、评估时间，以及 `metadata_status`、`metadata_error`、`metadata_started_at`、`metadata_finished_at`。
- `GET /api/v1/papers/{paper_id}` 的 `items` 返回可选快照字段 `question_type_snapshot`、`difficulty_level_snapshot`、`difficulty_label_snapshot`；如果创建试卷时题目元数据尚未 ready，快照字段为空。

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

- `POST /api/v1/papers/{paper_id}/render-model`
  - 返回当前登录用户自己的试卷渲染模型，用于前端 A4 作业预览，并为后续 PDF / DOCX 导出复用同一模型打基础。
  - 当前仅支持请求体：

```json
{
  "template_type": "homework",
  "version": "student",
  "paper_size": "A4",
  "group_by": "question_type",
  "sort_by": "position",
  "answer_area_mode": "none"
}
```

  - `answer_area_mode` 支持 `none` 和 `after_each_question`，默认 `none`。
  - 非法枚举值由 Pydantic 校验返回 `422`。
  - 试卷不存在或不属于当前用户时返回 `404`。
  - 学生版响应不包含答案或解析快照。
  - 题型快照为空时归入 `unknown / 未分类`。
  - 返回示例：

```json
{
  "template_type": "homework",
  "version": "student",
  "paper_size": "A4",
  "group_by": "question_type",
  "sort_by": "position",
  "answer_area_mode": "after_each_question",
  "paper": {
    "id": 1,
    "title": "Render Paper",
    "description": "render model",
    "status": "draft",
    "item_count": 1,
    "total_score": 5.0
  },
  "layout": {
    "show_answers": false,
    "show_analysis": false
  },
  "sections": [
    {
      "key": "unknown",
      "title": "未分类",
      "items": [
        {
          "paper_item_id": 1,
          "question_id": 10,
          "position": 1,
          "display_number": 1,
          "score": 5.0,
          "content": "题目内容",
          "question_type": "unknown",
          "question_type_label": "未分类",
          "knowledge_tags": [
            { "label": "函数", "score": null }
          ],
          "answer_area": {
            "mode": "after_each_question",
            "lines": 4
          }
        }
      ]
    }
  ]
}
```

- `POST /api/v1/papers/{paper_id}/pdf`
  - 使用与 `render-model` 相同的 `PaperRenderRequest` 请求体与用户归属检查。
  - 服务端执行固定链路：`Paper -> PaperRenderModel -> controlled HTML -> Gotenberg Chromium -> PDF`。
  - 成功返回 `application/pdf` 与 attachment `Content-Disposition`；响应不缓存，也不会在服务器永久保存 PDF。
  - 当前仅开放 A4 portrait 默认版式。Gotenberg 不可用时返回稳定的 `503`，不会向客户端暴露内部服务地址或上游响应。
  - 该接口不接受任意 HTML 或 URL，不能作为通用 HTML/URL-to-PDF 代理。

组卷快照：

- `PaperItem` 创建时保存题目内容快照，避免题库后续编辑导致历史试卷内容被动变化。
- 如果题目已有 `QuestionRevision`，优先使用最新 revision 的内容生成快照。
- 当前返回字段包括 `content_snapshot`、`answer_snapshot`、`analysis_snapshot`、`knowledge_tags_snapshot`，以及可选的题型和难度快照字段。

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
