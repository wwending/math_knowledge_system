# Draft API Smoke 验证文档

> 当前推荐文档：本文档是 Dashboard Draft 主路径的人工/API smoke 验证入口，负责说明当前主链路、异常契约、legacy 边界和验收标准。
>
> 相关补充：[API_SMOKE_DRAFT_PIPELINE.md](./API_SMOKE_DRAFT_PIPELINE.md) 负责说明 `scripts/smoke_draft_pipeline.ps1` 的脚本化验证方式。两个文档暂不合并：本文档面向维护者理解与手动核查，脚本文档面向自动/半自动 smoke 执行。

## 文档目的

本文档用于验证当前 `Dashboard.vue` Draft 主路径是否能跑通，帮助新维护者快速理解现阶段 Dashboard 上传、识别、保存入题库的主链路。

该 smoke 验证只确认当前开发基线是否可启动、可验证、可继续开发，不代表生产可用。

## 当前主路径

当前已接受的新基线是：`Dashboard.vue` 上传主路径已初步接入 Draft 流水线。

主链路为：

1. `POST /api/v1/assets`：上传图片素材，返回 `asset_id`。
2. `POST /api/v1/drafts`：基于 `source_asset_id` 创建 Draft。
3. `POST /api/v1/drafts/{draft_id}/recognize`：触发 Draft 识别，写入 OCR/LLM 运行记录，并更新 Draft 内容。
4. `POST /api/v1/drafts/{draft_id}/save-to-bank`：将已识别完成的 Draft 保存入题库。

关键状态预期：

- 创建 Draft 后，`status` 应为 `draft_created`。
- 识别成功后，`status` 应为 `draft_ready`。
- 保存入题库后，`status` 应为 `saved_to_bank`。

## Legacy 入口说明

`POST /api/v1/recognize` 当前仍保留为 legacy / 兼容入口。

边界：

- 不删除 `/api/v1/recognize`。
- 不把 `/api/v1/recognize` 改成当前 Dashboard 主路径。
- 不用 legacy 入口替代 Draft smoke 验证。

## 前置条件

- backend 可启动。
- frontend 可构建。
- 已配置必要环境变量，例如数据库、JWT、OCR、LLM 相关配置。
- 后端启动前已执行 `alembic upgrade head`。
- 如接口需要鉴权，需要先获取 token，并在后续请求中携带 `Authorization: Bearer <token>` 或项目当前登录态使用的认证凭据。

## 推荐验证方式

后端编译检查：

```powershell
cd backend
python -m compileall app
```

后端单元测试：

```powershell
cd backend
python -m pytest -q
```

前端 contract 测试：

```powershell
cd frontend
npm run test:auth-contract
npm run test:stage3-contract
```

前端 build：

```powershell
cd frontend
npm run build
```

手动 smoke 流程：

1. 启动后端和前端。
2. 登录并获得有效认证凭据。
3. 使用 Dashboard 上传一张可识别的图片，或使用 API 客户端按下面步骤调用 Draft 主链路。
4. 检查每一步返回结构中的关键字段。

## 手动 Smoke API 流程

以下示例以 `http://127.0.0.1:8000` 为后端地址，`TOKEN` 为已获取 token，`test_data/sample.png` 为本地测试图片。实际路径和认证方式按本地环境调整。

### 1. 创建 asset

```powershell
curl.exe -X POST "http://127.0.0.1:8000/api/v1/assets" `
  -H "Authorization: Bearer <TOKEN>" `
  -F "file=@test_data/sample.png"
```

检查关键字段：

- `asset_id`
- `kind`
- `mime`
- `size_bytes`
- `sha256`

图片素材的 `kind` 应为 `image`，`mime` 应为图片 MIME 类型。

### 2. 创建 draft

```powershell
curl.exe -X POST "http://127.0.0.1:8000/api/v1/drafts" `
  -H "Authorization: Bearer <TOKEN>" `
  -H "Content-Type: application/json" `
  -d "{\"source_asset_id\": <ASSET_ID>, \"crop_bbox\": {}}"
```

检查关键字段：

- `id`
- `source_asset_id`
- `status`
- `current_content`
- `content`
- `knowledge_tags`

预期 `status` 为 `draft_created`。

### 3. 触发 recognize

```powershell
curl.exe -X POST "http://127.0.0.1:8000/api/v1/drafts/<DRAFT_ID>/recognize" `
  -H "Authorization: Bearer <TOKEN>"
```

检查关键字段：

- `success`
- `partial_success`
- `status`
- `current_content`
- `content`
- `knowledge_tags`
- `last_ocr_run_id`
- `last_llm_run_id`
- `warning`
- `error`
- `error_type`

成功路径预期：

- `success` 为 `true`。
- `status` 为 `draft_ready`。
- `content` 或 `current_content.text` 包含识别后的题目内容。
- `last_ocr_run_id` 有值。
- `last_llm_run_id` 有值。

LLM 失败但 OCR 成功的部分成功路径可能返回 `partial_success: true` 和 `warning`，此时仍需确认返回内容是否符合当前设计预期。

### 4. 保存入题库

```powershell
curl.exe -X POST "http://127.0.0.1:8000/api/v1/drafts/<DRAFT_ID>/save-to-bank" `
  -H "Authorization: Bearer <TOKEN>"
```

检查关键字段：

- `id`
- `status`
- `question_id`
- `question_revision_id`
- `rev_no`
- `source_asset_id`
- `content`
- `knowledge_tags`

成功路径预期：

- `status` 为 `saved_to_bank`。
- `question_id` 有值。
- `question_revision_id` 有值。
- `rev_no` 为 `1`。

### 5. 关键结构检查

Draft 相关返回至少应帮助确认：

- draft 身份：`id`、`source_asset_id`。
- draft 状态：`status`。
- 识别内容：`current_content`、`content`。
- 知识点：`knowledge_tags`。
- 运行记录：`last_ocr_run_id`、`last_llm_run_id`。

保存入题库返回至少应帮助确认：

- question 身份：`question_id`。
- revision 身份：`question_revision_id`、`rev_no`。
- 保存后的 Draft 状态：`saved_to_bank`。

## 异常场景期望

当前 Draft 主路径异常契约已阶段性收口。以下场景应返回可解释的 4xx，不应直接变成未解释的 500。

| 场景 | 预期 HTTP 状态 | 预期原因 |
| --- | --- | --- |
| 使用不存在的 `source_asset_id` 创建 Draft | `404` | 素材资源不存在 |
| 对不存在的 `draft_id` 调用 recognize | `404` | Draft 资源不存在 |
| 对不存在的 `draft_id` 调用 save-to-bank | `404` | Draft 资源不存在 |
| 对 PDF 或其他非图片 asset 调用 Draft recognize | `400` | 当前 Draft recognize 仅支持图片素材 |
| `draft_created` 等未 ready 状态直接 save-to-bank | `409` | Draft 尚未识别完成，不能保存入题库 |
| `saved_to_bank` 状态再次 save-to-bank | `409` | 当前不做幂等返回，且不能重复创建 Question 或 QuestionRevision |
| `saved_to_bank` 状态再次 recognize | `409` | 已保存入题库的 Draft 不能再次识别 |

## 非目标

- 不验证批量 PDF。
- 不验证多页 Draft。
- 不代表生产可用。
- 不删除 legacy `POST /api/v1/recognize`。
- 不覆盖全部第三方 OCR/LLM 异常。

## 常见失败原因

- token 缺失或过期。
- API base URL 配置错误。
- 上传文件字段名不匹配，`POST /api/v1/assets` 当前使用 multipart 字段名 `file`。
- OCR/LLM 环境变量缺失或配置无效。
- 前端仍误走 legacy `POST /api/v1/recognize`。
- 上传了 PDF 或非图片素材后直接调用 Draft recognize；当前 Draft recognize 仅支持图片素材。

## 验收标准

- 文档能让新维护者理解当前 Dashboard Draft 主链路。
- 文档明确 legacy `/api/v1/recognize` 与 Draft 主路径的边界。
- 推荐验证命令全部通过。
- 手动 smoke 流程能覆盖创建 asset、创建 draft、触发 recognize、保存入题库，并检查 draft/question 关键字段。
