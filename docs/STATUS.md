# STATUS

## 2026-05-27 第十二轮后当前状态

当前项目进入“可启动、可验证、可继续开发”的状态。该结论不等于生产可用，也不表示所有正式流水线已经闭环。

## 当前结论

- `Dashboard.vue` 当前上传主路径已初步接入 Draft 流水线，并接受为新的前端主路径基线。
- `POST /api/v1/recognize` 仍存在，后端未删除、未重构，定义为 legacy / 兼容入口。
- 第七轮已新增 Draft 后端旁路正式流水线最小竖切。
- 第八轮已完成后端 LLM LaTeX 分隔符程序级归一化。
- 第九轮已补充 LLM analyze 成功路径 LaTeX 归一化集成测试。
- 第十轮已完成前端 Markdown / LaTeX 渲染工具抽取。
- 第十一轮补充确认：当前 `Dashboard.vue` 上传按钮实际调用 `POST /api/v1/assets`、`POST /api/v1/drafts`、`POST /api/v1/drafts/{draft_id}/recognize`，保存调用 `POST /api/v1/drafts/{draft_id}/save-to-bank`。
- `Dashboard.vue` 中仍保留 `runLegacyRecognition()` 对 `POST /api/v1/recognize` 的调用，但当前上传按钮未引用该函数。
- 本轮接受当前 Dashboard Draft 初步接入作为新基线；这属于渐进式迁移的路线推进，不再按疑似误改处理。
- Draft 主路径已接受为当前基线，已补充 API smoke 验证文档；当前仍是可启动、可验证、可继续开发，不是生产可用。
- Draft 前端接入不是完整生产级完成，仍需补异常场景、UI 状态和 legacy 清理。
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

## 最新验证结果

| 范围 | 命令 | 状态 |
| --- | --- | --- |
| frontend | `npm run build` | 通过，仅有 Vite chunk size warning |
| frontend | `npm run test:auth-contract` | 通过 |
| frontend | `npm run test:stage3-contract` | 通过 |
| backend | `python -m compileall app` | 通过 |
| backend | `python -m unittest discover tests` | 通过，`Ran 46 tests OK` |
| backend | `python -m pytest tests/test_llm.py` | 通过，`8 passed` |

说明：

- 第十二轮已重新实测上述最小验证命令。
- `npm run build` 仍有 Vite chunk size warning，但构建成功。

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
- Dashboard Draft 接入已接受为新基线，已补充 API smoke 验证文档，但尚未补齐异常场景、UI 状态和 legacy 清理。
- mock/legacy 文件需要清理，但不应在下一阶段做大重构。
- 后端测试已通过本轮验证，但稳定性仍需持续关注。
- 真实第三方失败场景仍缺少系统化在线验证矩阵。
- 完整多页 PDF 和批量 draft 能力未完成，不应在当前状态中夸大。
- 当前状态不是生产可用。

## 下一阶段口径

下一阶段以收敛和稳定为主，不新增规划之外的大模块，不做大重构。优先级为：前端中文乱码、Draft 异常场景和 UI 状态、mock/legacy 文件清理、后端测试稳定性。

明确不做：

- 不删除 `/recognize`。
- 不把 Draft 前端接入写成完整生产级完成。
- 不做 OCR/LLM provider 抽象。
- 不做异步队列。
- 不做批量 PDF。
- 不做多页 draft 管理。
