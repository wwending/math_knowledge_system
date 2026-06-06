# DECISIONS

说明：本文件按时间倒序记录决策。较早决策中的“当前主链路”等表述保留为当时历史事实；如与顶部较新决策冲突，以较新决策和 `docs/STATUS.md` 当前 checkpoint 为准。

## 决策 26：PaperRenderModel 由后端生成，前端只负责展示

结论：

- 新增 `POST /api/v1/papers/{paper_id}/render-model`，由后端将 Paper / PaperItem 快照转换为稳定 PaperRenderModel。
- PaperRenderModel 独立放在 `backend/app/schemas/paper_render.py` 和 `backend/app/services/paper_render_service.py`，避免扩大既有 Paper schema/service 职责。
- 当前只支持 `homework` 模板、`student` 版本、`A4`、按 `question_type` 分组、按 `position` 排序。
- 学生版响应层面不返回答案或解析快照，前端不承担隐藏敏感字段的责任。
- 前端新增 `PaperPreview.vue` 负责 A4 视觉展示，并复用共享 Markdown / LaTeX 渲染工具。
- 后续 PDF / DOCX 导出应优先复用 PaperRenderModel，而不是重新读取 PaperItem 并各自拼装结构。

原因：

- 预览、PDF、DOCX 的核心内容结构应保持一致，避免不同导出通道各自实现排序、分组、题型兜底和答题区逻辑。
- 后端生成模型可以统一权限、学生版字段裁剪和历史数据归一化。
- 前端只做展示可以降低后续模板扩展和导出接入的分叉风险。

边界：

- 不新增数据库表，不修改 Paper / PaperItem 模型，不做数据库迁移。
- 不做 PDF / DOCX 导出。
- 不做自定义模板、模板编辑器、自动分页、拖拽排序、知识点排序、难度排序或复杂答题卡。
- 不修改 Draft flow 或 legacy `/api/v1/recognize`。

日期：2026-06-06

## 决策 25：题型与难度元数据改为保存后后台补全

结论：

- 交互式 `POST /api/v1/drafts/{draft_id}/recognize` 优先保证 OCR、`corrected_text` 和知识点标签快速返回。
- 题型和五星难度作为增强元数据，不再阻塞 Draft recognize 主链路。
- `POST /api/v1/drafts/{draft_id}/save-to-bank` 创建 `Question` 后将 `metadata_status` 设为 `pending`。
- 当前使用 FastAPI `BackgroundTasks` 调用后台任务补全 `question_type`、`difficulty_level`、`difficulty_label`、`difficulty_confidence`、`difficulty_reason`、`difficulty_model` 和 `difficulty_evaluated_at`。
- 后台任务内部新建 DB session，不复用请求 session。
- 后台任务失败只更新 `metadata_status=failed` 和 `metadata_error`，不回滚已经保存入题库的结果。
- 当前不引入 Celery / Redis；未来如果部署并发压力或任务可靠性要求提高，再迁移到真正任务队列。

原因：

- 用户录入题目时更关心 `corrected_text` 主结果，题型和难度是后续题库/组卷增强能力。
- 同步 recognize 同时承担 OCR、洗稿、知识点、题型和难度评估会让交互等待变长。
- 使用 `BackgroundTasks` 可以在当前架构内完成最小性能收口，不扩大基础设施复杂度。

边界：

- 不改变 Draft 状态机。
- 不删除 legacy recognize。
- 不做自动轮询、WebSocket、重新评估按钮、智能组卷、模板、导出或答题区域。
- 后台任务依赖当前后端进程，服务重启可能丢失正在执行的元数据评估任务。

日期：2026-06-04

## 决策 24：LLM 洗稿阶段同时生成题型与五星难度元数据

结论：

- LLM analyze 从“文本清洗 + 知识点标签”扩展为“题目结构化分析”。
- `corrected_text` 仍是主结果，继续优先保障识别和保存流程。
- `question_type` 和 `difficulty` 是增强结果；`difficulty` 缺失或非法时不阻断 Draft recognize。
- 后端兼容旧 `tags` 字段，并将其归一为 `knowledge_tags`。
- Draft 使用独立 nullable 字段暂存题型与难度，避免把 `current_content` 从正文结果扩展成复杂元数据载体。
- Question 保存最终题型与难度；PaperItem 保存可选题型与难度快照。

五星评分标准：

- 1星：基础识记题，直接套概念或公式即可完成。
- 2星：基础应用题，单一知识点，一到两步计算。
- 3星：中等综合题，涉及两类知识点或多步推理。
- 4星：较难综合题，需要分类讨论、复杂计算或较强转化能力。
- 5星：压轴难题，需要抽象建模、创新构造或高综合能力。

原因：

- 后续按题型、知识点、难度组卷需要题库层稳定保存元数据。
- 难度评估来自 LLM，可信度低于 `corrected_text`，因此不能让增强字段失败影响主识别流程。
- PaperItem 快照可以保持已创建试卷的题型和难度展示稳定。

边界：

- 不做按难度排序、按知识点排序、组卷模板、PDF / DOCX 导出、答题区域或智能组卷。
- 不改变 Draft flow 状态机。
- 不删除 legacy recognize。
- 用户编辑题目后不会自动重新评估题型或难度。

日期：2026-06-04

## 决策 23：前端组卷入口采用 BankPanel 选题 + PaperPanel 展示

结论：

- 在 `BankPanel.vue` 中增加最小选题和创建试卷入口。
- 新增 `PaperPanel.vue` 作为试卷列表和试卷详情的独立展示组件。
- `Dashboard.vue` 新增独立“组卷”菜单入口，避免组卷 UI 干扰题目录入、Draft 保存入库、题库查看和历史记录。
- 前端继续沿用现有 axios 全局 token 注入，不新增统一 API 层或状态管理。

原因：

- 本轮目标是前端组卷入口 MVP，不是前端结构重构。
- 题库选题最贴近现有题库列表，放在 `BankPanel.vue` 能减少跨组件状态复杂度。
- 试卷列表和详情是独立展示职责，拆成 `PaperPanel.vue` 可以避免继续扩大 `BankPanel.vue` 的展示责任。
- 复用 `renderMarkdown.ts` 能保持题目内容、答案、解析的 Markdown / LaTeX 渲染规则一致。

边界：

- 不修改后端 Paper API 主逻辑。
- 不修改 Draft flow。
- 不修改 legacy recognize。
- 不做导出、智能组卷、拖拽排序、分值编辑、复杂排版或打印样式优化。

日期：2026-06-03

## 决策 22：组卷 MVP 使用 Paper + PaperItem 并保存题目快照

结论：

- 新增 `Paper` 表表示一张试卷草稿。
- 新增 `PaperItem` 表表示试卷中的题目条目，按请求顺序生成 `position`。
- `PaperItem` 关联 `question_id`，并在存在 `QuestionRevision` 时记录当前最新 `question_revision_id`。
- `PaperItem` 同时保存 `content_snapshot`、`answer_snapshot`、`analysis_snapshot`、`knowledge_tags_snapshot`。

原因：

- 组卷 MVP 当前目标是后端最小手动选题竖切，不引入智能组卷、导出或前端复杂交互。
- 题库题目后续可能被编辑，如果试卷只动态读取 Question 当前内容，历史试卷会被动变化。
- 保存快照可以保证已创建试卷内容稳定，同时保留与题库题目的关联。
- 当前 `QuestionRevision` 已存在，但历史题目不一定都有完整 revision；因此同时保存快照作为稳定兜底。

边界：

- 当前不做智能组卷算法。
- 当前不做 PDF/Word 导出。
- 当前不做前端组卷入口。
- 当前不做拖拽排序或自动配比。
- 不改变 Draft flow、legacy recognize 或题库保存逻辑。

日期：2026-05-27

## 决策 21：保留两个 Draft smoke 文档并明确主次

结论：

- 保留 `docs/API_SMOKE_DRAFT_FLOW.md` 和 `docs/API_SMOKE_DRAFT_PIPELINE.md`，本轮不合并、不删除。
- `docs/API_SMOKE_DRAFT_FLOW.md` 作为当前推荐 smoke 文档，负责 Dashboard Draft 主路径、异常契约、legacy 边界和人工/API 验收标准。
- `docs/API_SMOKE_DRAFT_PIPELINE.md` 作为脚本化 smoke 补充文档，负责 `scripts/smoke_draft_pipeline.ps1` 的执行方式、参数和脚本断言说明。

原因：

- 两个文档存在部分 API 顺序重复，但受众不同：一个用于理解和人工核查，一个用于脚本执行。
- 合并会让主路径验收口径和脚本参数说明互相干扰，后续维护成本不一定更低。
- 明确主次和互链可以降低维护者误读风险，同时保持现有链接不失效。

边界：

- 不删除任何 smoke 文档。
- 不改变 Draft API 或业务行为。
- 后续修改 Draft 主链路或 smoke 脚本时，应同步检查两个 smoke 文档。

日期：2026-05-27

## 决策 20：legacy recognize 先审计标注，后续小步退场

结论：

- 当前 Dashboard 上传主路径继续以 Draft 流水线为基线。
- `POST /api/v1/recognize` 和 `runLegacyRecognition()` 本轮不删除、不重构，作为 legacy / 兼容入口保留。
- 后续清理顺序应先补足引用审计和测试保护，再评估是否隐藏、废弃或移除 legacy 入口。

原因：

- Dashboard 主流程已经不调用 `runLegacyRecognition()`，直接删除 legacy 入口会扩大兼容风险。
- 后端仍有 `/api/v1/recognize` 失败路径测试覆盖，说明该入口仍有明确兼容价值。
- 本轮目标是降低误用风险，而不是改变业务行为。

边界：

- 不把 legacy recognize 描述成当前 Dashboard 主路径。
- 不删除 `/api/v1/recognize`。
- 不删除 `runLegacyRecognition()`。
- 不修改 OCR / LLM service 或数据库模型。

日期：2026-05-27

## 决策 19：Draft 重复保存当前返回 409 而不是幂等结果

结论：

- 当前 Draft 流程中，Draft 已达到 `saved_to_bank` 状态后，再次调用 `POST /api/v1/drafts/{draft_id}/save-to-bank` 返回 `409 Conflict`。
- 当前不重建并返回已有的保存结果。

原因：

- 防止重复创建 `Question` / `QuestionRevision`。
- 保持当前实现小而明确。
- 在保存结果模型完全稳定前，避免提前引入幂等响应重建逻辑。

影响：

- 前端应将该行为视为可恢复的状态冲突。
- 后续可升级为幂等返回既有 `question_id` / `question_revision_id` / `rev_no`。

日期：2026-05-27

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
