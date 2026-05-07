# STATUS

## 2026-05-05 项目文档收口状态

当前项目进入“可启动、可验证、可继续开发”的状态。该结论不等于生产可用，也不表示所有正式流水线已经闭环。

## 当前结论

- 当前主链路仍是 `POST /api/v1/recognize`。
- 第七轮已新增 Draft 后端旁路正式流水线最小竖切。
- Draft 流水线目前是后端旁路能力，尚未接入主前端。
- `Dashboard.vue` 尚未切换到 Draft 流水线。
- `/api/v1/recognize` 未删除、未重构，仍是当前 MVP 主入口。
- `/upload_pdf`、`/assets`、draft 流水线目前不是主前端闭环。
- 主链路迁移采用渐进式方案：短期继续 `/api/v1/recognize`，长期逐步迁移到 `assets/drafts/ocr_runs/llm_runs` 正式流水线。
- 下一阶段可以做 API smoke 文档或前端接入方案评估，但不要立即硬切前端。
- 后端启动和管理员初始化前必须先执行 `alembic upgrade head`。
- `backend/.env` 是本地文件，不应提交；示例配置使用 `backend/.env.example`。

## 第七轮后端旁路 Draft 流水线

新增接口：

- `POST /api/v1/drafts`
- `GET /api/v1/drafts/{draft_id}`
- `POST /api/v1/drafts/{draft_id}/recognize`
- `POST /api/v1/drafts/{draft_id}/save-to-bank`

状态流转：

- `draft_created`
- `recognizing`
- `draft_ready`
- `failed`
- `saved_to_bank`

落库行为：

- `DraftEvent`：创建、开始识别、识别成功/失败、保存入题库都会写入。
- `OCRRun`：Draft 识别后写入，失败也记录错误。
- `LLMRun`：OCR 成功后写入，LLM 失败记录错误并允许 `partial_success`。
- `QuestionRevision`：保存入题库时创建 v1，并关联 `source_asset_id`、`ocr_run_id`、`llm_run_id`。

## 第七轮验证结果

| 范围 | 命令 | 状态 |
| --- | --- | --- |
| backend | `python -m compileall app` | 通过 |
| backend | `python -m unittest discover tests` | 通过，`Ran 38 tests OK` |

## 第二轮验证结果

| 范围 | 命令 | 状态 |
| --- | --- | --- |
| frontend | `npm run build` | 通过，仅有 Vite chunk size warning |
| frontend | `npm run test:auth-contract` | 通过 |
| frontend | `npm run test:stage3-contract` | 通过 |
| backend | `python -m compileall app` | 通过 |
| backend | `python -m unittest discover tests` | 通过，`Ran 36 tests OK` |

依赖收口：

- `backend/requirements.txt` 已补齐 `passlib[bcrypt]`。
- `frontend/package.json` 已显式声明 `@element-plus/icons-vue`。
- README 已修正管理员初始化路径为 `app.scripts.create_admin`。
- README 已明确 `alembic upgrade head` 是硬前置。

## 当前未闭合边界

- 前端中文乱码仍需优先处理。
- Draft 流水线已具备后端旁路最小竖切，但尚未形成主前端闭环。
- mock/legacy 文件需要清理，但不应在下一阶段做大重构。
- 后端测试已通过本轮验证，但稳定性仍需持续关注。
- 真实第三方失败场景仍缺少系统化在线验证矩阵。
- 完整多页 PDF 和批量 draft 能力未完成，不应在当前状态中夸大。

## 下一阶段口径

下一阶段以收敛和稳定为主，不新增规划之外的大模块，不做大重构。优先级为：前端中文乱码、API smoke 文档或前端接入方案评估、mock/legacy 文件清理、后端测试稳定性。

明确不做：

- 不删除 `/recognize`。
- 不现在硬切 `Dashboard.vue`。
- 不做 OCR/LLM provider 抽象。
- 不做异步队列。
- 不做批量 PDF。
- 不做多页 draft 管理。
