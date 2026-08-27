# API

## 题库题目编辑与回收站（#116）

题目接口均按当前用户 owner-scoped 查询；不存在、他人题目、已到期或已永久删除资源统一返回 `404`。

- `GET /api/v1/questions`：仅返回 active 题目。
- `GET /api/v1/questions/{id}`：返回当前投影及 `current_revision_no`。
- `PUT /api/v1/questions/{id}`：编辑题干、答案、解析、标签、题型和难度；有变化创建不可变 revision；可携带 `expected_revision_no`，冲突返回 `409`；仅提交 `content` 兼容旧客户端。
- `POST /api/v1/questions/{id}/trash`：进入回收站并设置 30 天 `purge_at`。
- `GET /api/v1/questions/trash`、`GET /api/v1/questions/trash/{id}`：查看未到期回收站题目。
- `POST /api/v1/questions/{id}/restore`：恢复 active 状态。
- `DELETE /api/v1/questions/{id}/permanent`：逻辑永久删除（设置 `purged_at`，不物理删除历史 revision、试卷快照或共享文件）。

回收、恢复、编辑不会改变已有 `PaperItem` 快照；新建试卷只能读取 active 题目的最新 revision。`/history`、`/tags`、题图和配图旁路同样排除到期/永久删除资源。

## 当前 Dashboard 主路径

当前 `Dashboard.vue` 上传主路径已接入 Draft 流水线：

- `POST /api/v1/assets`
- `POST /api/v1/drafts`
- `POST /api/v1/drafts/{draft_id}/recognize`
- `POST /api/v1/drafts/{draft_id}/save-to-bank`
- `GET /api/v1/drafts/{draft_id}/image`（识别结果页旁路展示原图，#22）

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
- `GET /api/v1/questions/{question_id}/image` 先按 Question 所有权鉴权，再读取最新 `QuestionRevision` 的 `source_asset_id` 与页面归一化 `crop_bbox`；有合法 bbox 时返回该题区域裁图，多题可共享同一 SourceAsset 但各自区域不同。无 revision 或无 bbox 的历史题回退 `origin_image` 整图；bbox 非法、文件缺失或无法解析时 fail-closed 返回 404。
- `GET /api/v1/papers/{paper_id}` 的 `items` 返回可选快照字段 `question_type_snapshot`、`difficulty_level_snapshot`、`difficulty_label_snapshot`；如果创建试卷时题目元数据尚未 ready，快照字段为空。

## 组卷 MVP

当前支持登录用户从自己的题库创建并完整编辑草稿试卷，以及预览和服务端 PDF 导出；不支持智能组卷、Word 导出或拖拽排序。

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

- `PATCH /api/v1/papers/{paper_id}`
  - 原子保存 owner 的草稿试卷标题、描述及完整有序 items；非 `draft` 状态返回冲突错误。
  - `items` 不能为空且 `question_id` 不得重复；后端忽略客户端 position，严格按数组顺序重建连续 `1..N`。
  - 已有条目使用 `kind=existing`，提交当前 paper item 的 `id`、`question_id`、`score` 和可编辑文本快照。
  - 从题库新增使用 `kind=question` 和 `question_id`；服务端从当前用户题库的最新 QuestionRevision 建立基础快照。可选文本字段只覆盖当前新 PaperItem，不能提交或修改题型、难度、知识点及 revision id。
  - 删除通过省略已有 item 表达；保存失败时整个事务回滚。试卷编辑不修改 Question 或 QuestionRevision。

```json
{
  "title": "高一函数练习",
  "description": "课堂练习",
  "items": [
    {
      "kind": "existing",
      "id": 11,
      "question_id": 21,
      "score": 10,
      "content_snapshot": "试卷专用题干",
      "answer_snapshot": "答案",
      "analysis_snapshot": "解析"
    },
    {
      "kind": "question",
      "question_id": 34,
      "score": 8
    }
  ]
}
```

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

  - `answer_area_mode` 支持 `none` 和 `after_each_question`；API 请求体省略该字段时仍默认 `none`，组卷界面默认请求 `after_each_question`。
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
            "height_mm": 50
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
  - `after_each_question` 在每题后生成固定 `50mm` 的纯白留白，不包含横线；短题末尾与留白尽量连续，长题题干仍允许跨页。
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
- `GET /api/v1/drafts/{draft_id}/image`

### 裁剪与坐标语义

- `DraftCreate.crop_bbox` 使用页面相对的归一化 `{x, y, w, h}` 坐标；各值相对于 SourceAsset 完整页面尺寸解释。
- 省略 `crop_bbox`、传 `null` 或 legacy `{}` 均表示完整页面，保持旧客户端兼容。
- `GET /api/v1/drafts/{draft_id}` 返回 Draft 的有效裁剪范围；`GET /api/v1/drafts/{draft_id}/image` 返回该有效范围裁出的图片，而不是始终返回 SourceAsset 完整原图。
- `save-to-bank` 的 `figure_bbox` 使用 Draft 有效裁剪区域内的归一化 `[x, y, w, h]` 坐标。保存时服务端将其与 Draft 裁剪范围组合为页面坐标，再持久化题目配图范围。
- 同一页面需要手工切分为多题时，对同一 `source_asset_id` 以不同 `crop_bbox` 多次调用现有 `POST /api/v1/drafts`，再分别调用现有 recognize 与 save-to-bank 接口；不新增批量或专用分割端点。

Draft 图片所有权校验挂在 Draft 行：未认证 401、非本人草稿 403、文件缺失 404；与 `GET /api/v1/questions/{id}/image` 同属鉴权图片通道，SourceAsset 按 sha256 全局去重仅作共享字节仓库，不承载归属语义。

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
