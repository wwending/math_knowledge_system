# DECISIONS

## 决策 18：接受 Dashboard Draft 初步接入为新的前端主路径基线

结论：

- 第十一轮补充确认，当前 `Dashboard.vue` 上传主路径已初步接入 Draft 流水线。
- 上传按钮链路为：图片/PDF 单页确认后调用 `runRecognition()`，依次请求 `POST /api/v1/assets`、`POST /api/v1/drafts`、`POST /api/v1/drafts/{draft_id}/recognize`。
- 保存入题库调用 `POST /api/v1/drafts/{draft_id}/save-to-bank`。
- `runLegacyRecognition()` 仍保留，并继续调用 `POST /api/v1/recognize`，但当前上传按钮和主上传流程不引用它。
- 接受该状态作为新的前端主路径基线。
- `POST /api/v1/recognize` 不删除、不重构，定义为 legacy / 兼容入口。

原因：

- 代码事实已经显示 Dashboard 上传主流程走 Draft 接口，继续保留“尚未接入主前端”的口径会误导后续开发。
- Draft 前端接入符合既定渐进式迁移方向，可作为路线推进接受。
- 当前接入仍不是完整生产级完成，仍需补 API smoke 文档、异常场景、UI 状态和 legacy 清理。
- 当前项目仍只表述为“可启动、可验证、可继续开发”，不表述为生产可用。

边界：

- 不删除 `/api/v1/recognize`。
- 不删除 `runLegacyRecognition()`。
- 不做异步队列、批量 PDF、多页 draft 或 OCR/LLM provider 抽象。
- 不声称 Draft 已完整生产可用。

日期：2026-05-27

## 决策 17：前端 Markdown/LaTeX 渲染逻辑统一收敛到共享工具

结论：

- 将 `Dashboard.vue`、`BankPanel.vue`、`HistoryPanel.vue` 中重复的 `markdown-it + markdown-it-mathjax3` 渲染逻辑抽取到 `frontend/src/utils/renderMarkdown.ts`。

原因：

- 避免多个组件各自维护 Markdown/LaTeX 渲染规则。
- 确保识别结果、题库详情、历史详情使用一致的渲染行为。
- 为历史数据或异常数据中的 `\(...\)` / `\[...\]` 提供展示层兜底。
- 后续如果需要调整 Markdown 配置、LaTeX 兼容规则或渲染安全策略，只需要修改一个入口。

边界：

- 不改变后端返回结构。
- 不改变原始题目内容。
- 只在展示前做格式归一化。
- 本轮不处理 `katex` 冗余依赖和 `markdown-body` 样式问题。

日期：2026-05-26

## 决策 16：Draft 流水线先作为后端旁路能力

结论：

- 第七轮新增 Draft 后端旁路正式流水线最小竖切。
- 新增接口为 `POST /api/v1/drafts`、`GET /api/v1/drafts/{draft_id}`、`POST /api/v1/drafts/{draft_id}/recognize`、`POST /api/v1/drafts/{draft_id}/save-to-bank`。
- Draft 状态流转为 `draft_created`、`recognizing`、`draft_ready`、`failed`、`saved_to_bank`。
- `DraftEvent` 会记录创建、开始识别、识别成功/失败、保存入题库。
- `OCRRun` 在 Draft 识别后写入，失败也记录错误。
- `LLMRun` 在 OCR 成功后写入，LLM 失败记录错误并允许 `partial_success`。
- `QuestionRevision` 在保存入题库时创建 v1，并关联 `source_asset_id`、`ocr_run_id`、`llm_run_id`。
- 当前前端主链路仍然是 `/api/v1/recognize`。
- `Dashboard.vue` 尚未切换到 Draft 流水线。
- `/api/v1/recognize` 未删除、未重构，仍是当前 MVP 主入口。

原因：

- 先让正式流水线具备可验证的后端旁路能力，可以降低直接切换主前端的风险。
- 当前 MVP 主入口仍可用，立即硬切前端会扩大验证面。
- 下一阶段更适合先补 API smoke 文档或做前端接入方案评估。

日期：2026-05-07

## 决策 15：主链路采用渐进式迁移

结论：

- 选择 C：短期继续使用 `POST /api/v1/recognize`，长期逐步迁移到 `assets/drafts/ocr_runs/llm_runs` 正式流水线。
- 当前主链路仍是 `/api/v1/recognize`。
- `/upload_pdf`、`/assets`、drafts 当前不是主前端闭环。
- 下一阶段目标是新增最小正式流水线后端竖切，不影响现有前端。
- 不要删除 `/recognize`。
- 不要现在硬切 `Dashboard.vue`。
- 不要做 OCR/LLM provider 抽象、异步队列、批量 PDF、多页 draft 管理。

原因：

- 当前 `/recognize -> questions -> history/bank` 已经跑通，是现有可用 MVP 主链路。
- `assets/drafts/ocr_runs/llm_runs` 已有模型和迁移，但缺少主接口、schema、前端闭环和测试。
- 现在硬切正式流水线风险过大。
- 继续只维护 `/recognize` 又会让正式流水线长期架空。
- 因此采用渐进式迁移：先新增后端正式流水线竖切，不影响现有前端；验证通过后再切 Dashboard。

日期：2026-05-07

## 决策 14：第三轮只做文档和示例配置收口

结论：

- 第三轮只允许修改文档和示例配置文件。
- 不修改业务代码、测试代码、前端代码、后端代码。
- `backend/.env` 作为本地文件，不应提交；需要示例配置时使用 `backend/.env.example`。

原因：

- 第二轮已经完成必要修复与验证，本轮目标是让交付口径一致。
- 继续改代码会扩大本轮范围，干扰“文档收口”的判断。

日期：2026-05-05

## 决策 13：当前状态表述为“可启动、可验证、可继续开发”

结论：

- 当前项目可以表述为“可启动、可验证、可继续开发”。
- 不表述为生产可用。
- 不夸大 `/upload_pdf`、`/assets`、draft 流水线的完成度。

原因：

- 第二轮验证命令已通过，但仍存在前端中文乱码、主链路决策、mock/legacy 清理、后端测试稳定性等后续工作。
- `assets/drafts/ocr_runs/llm_runs` 已建模，但未形成主前端闭环。

日期：2026-05-05

## 决策 12：当前主链路仍是 `/api/v1/recognize`

结论：

- 当前主链路继续按 `POST /api/v1/recognize` 说明。
- `assets/drafts/ocr_runs/llm_runs` 作为正式流水线预留。
- `/upload_pdf`、`/assets`、draft 流水线目前不写成主前端已接入能力。

原因：

- 主前端闭环尚未切到 draft 流水线。
- 文档必须反映当前可验证事实，而不是按未来结构提前表述完成。

日期：2026-05-05

## 决策 11：下一阶段避免大重构

结论：

- 下一阶段优先处理前端中文乱码、主链路决策、mock/legacy 文件清理、后端测试稳定性。
- 不新增规划之外的大模块。
- 不以大重构方式解决当前收敛问题。

原因：

- 当前项目刚进入可启动、可验证状态，优先级应是稳定和收敛。
- 大范围重构会削弱第二轮已经建立的验证基线。

日期：2026-05-05

## 决策 10：`alembic upgrade head` 是硬前置

结论：

- 后端启动、管理员初始化和共享环境验证前必须执行 `alembic upgrade head`。
- 不依赖运行时 `create_all` 或兼容补表替代正式迁移链。

原因：

- 数据库 schema 的正式演进需要单一可信路径。
- 运行时兜底会让本地和目标环境行为分叉。

日期：2026-03-24

## 决策 9：README / STATUS / WORKLOG / DECISIONS / KNOWN_ISSUES 职责边界

结论：

- README 负责启动、配置、验证和当前能力边界。
- STATUS 负责当前阶段状态和当前门禁结论。
- WORKLOG 记录时间线，不承载当前唯一真相。
- DECISIONS 记录为什么这样定。
- KNOWN_ISSUES 记录当前未解决边界与风险。

原因：

- 多个文档同时承载当前真相会导致重复、冲突和过时结论并存。
- 明确职责后，后续维护可以判断应修改哪个文件。

日期：2026-04-20
