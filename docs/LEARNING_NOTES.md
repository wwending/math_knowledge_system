# LEARNING_NOTES

## 1. MVP

- 概念是什么
  MVP 是 Minimum Viable Product，最小可用产品。它不是完整产品，而是能跑通核心价值、能被验证、能继续迭代的最小版本。
- 为什么项目需要它
  本项目当前目标是先把“上传题目图片、识别、整理、保存、查看题库/历史”跑通，避免一开始就做批量 PDF、多页管理、异步队列、复杂 provider 抽象等大功能。
- 在本项目对应哪些文件
  - `README.md`
  - `docs/STATUS.md`
  - `docs/DECISIONS.md`
  - `backend/app/api/v1/endpoints.py`
  - `frontend/src/views/Dashboard.vue`
- 一个生活类比
  先开一家能点单、出餐、收钱的小店，而不是第一天就建中央厨房、会员系统和全国配送。
- 常见误区
  - 误以为 MVP 是“随便做个半成品”。
  - 误以为 MVP 必须覆盖所有未来功能。
  - 误以为 MVP 通过后就等于生产可用。

## 2. 主链路

- 概念是什么
  主链路是用户当前真正使用、端到端能闭环的核心流程。
- 为什么项目需要它
  项目需要明确当前可验证事实：现在前端主链路仍是 `POST /api/v1/recognize`，Draft 流水线还没有接入主前端。
- 在本项目对应哪些文件
  - `docs/API.md`
  - `docs/STATUS.md`
  - `docs/DECISIONS.md`
  - `backend/app/api/v1/endpoints.py`
  - `frontend/src/views/Dashboard.vue`
  - `frontend/src/components/HistoryPanel.vue`
  - `frontend/src/components/BankPanel.vue`
- 一个生活类比
  主链路像超市当前正在使用的收银通道；旁边可以装修新自助收银机，但顾客今天结账走的还是老通道。
- 常见误区
  - 把已经建好的数据库模型误认为已经接入主链路。
  - 把后端旁路接口误写成前端已上线功能。
  - 为了“看起来先进”过早删除仍可用的老入口。

## 3. Draft

- 概念是什么
  Draft 是题目进入题库前的草稿对象，记录来源素材、裁剪区域、识别状态、当前内容以及最近一次 OCR/LLM 运行结果。
- 为什么项目需要它
  它让题目从“上传素材”到“保存入题库”之间有一个可追踪、可失败、可重试、可审核的中间状态。
- 在本项目对应哪些文件
  - `backend/app/models/draft.py`
  - `backend/app/schemas/draft.py`
  - `backend/app/core/constants.py`
  - `backend/app/services/draft_state.py`
  - `backend/app/api/v1/endpoints.py`
  - `docs/API.md`
- 一个生活类比
  Draft 像写作文时的草稿纸，正式交卷前可以修改、标注状态，也能知道它来自哪份原始材料。
- 常见误区
  - 把 Draft 当成最终题库记录。
  - 只保存文本，不保存来源、状态和运行记录。
  - 忽略 Draft 目前只是后端旁路能力，尚未成为主前端闭环。

## 4. SourceAsset

- 概念是什么
  SourceAsset 是用户上传的原始素材记录，例如图片或 PDF，保存文件路径、MIME 类型、大小、尺寸、哈希等元数据。
- 为什么项目需要它
  题目识别需要知道内容来自哪个原始文件；后续追溯、去重、裁剪、重新识别都依赖稳定的素材记录。
- 在本项目对应哪些文件
  - `backend/app/models/source_asset.py`
  - `backend/app/api/v1/endpoints.py`
  - `backend/alembic/versions/20260319_0001_auth_production_baseline.py`
  - `docs/API_SMOKE_DRAFT_PIPELINE.md`
- 一个生活类比
  SourceAsset 像档案柜里的原始发票，后面生成的报表可以改，但必须知道原始凭证是哪一张。
- 常见误区
  - 把 SourceAsset 当成识别后的题目内容。
  - 只保存文件路径，不保存哈希、类型、大小等校验信息。
  - 忘记检查素材归属，导致用户访问别人的文件。

## 5. OCRRun

- 概念是什么
  OCRRun 是一次 OCR 文字识别调用记录，包含 provider、请求摘要、原始响应、解析结果、耗时和错误信息。
- 为什么项目需要它
  OCR 可能成功也可能失败。项目需要记录每次识别过程，方便排查、复现、统计质量，并把题目版本关联到具体识别结果。
- 在本项目对应哪些文件
  - `backend/app/models/ocr_run.py`
  - `backend/app/api/v1/endpoints.py`
  - `backend/app/services/ocr_engine.py`
  - `backend/alembic/versions/20260319_0001_auth_production_baseline.py`
  - `docs/API.md`
- 一个生活类比
  OCRRun 像快递的一次扫描记录：包裹本身是一件东西，但每次扫描都有时间、地点和结果。
- 常见误区
  - 只在成功时记录，失败时不落库。
  - 把 OCRRun 当成 Draft 本身。
  - 直接保存敏感请求参数，而不是保存脱敏后的请求摘要。

## 6. LLMRun

- 概念是什么
  LLMRun 是一次大模型整理调用记录，包含模型、prompt 版本、输入文本、原始输出、解析结果、校验状态、fallback 和错误信息。
- 为什么项目需要它
  OCR 产出的原文可能需要纠错、整理和打知识标签。LLMRun 让这一步可追踪，也允许 LLM 失败时保留 OCR 原文形成 `partial_success`。
- 在本项目对应哪些文件
  - `backend/app/models/llm_run.py`
  - `backend/app/api/v1/endpoints.py`
  - `backend/app/services/llm.py`
  - `backend/app/services/nlp_engine.py`
  - `backend/alembic/versions/20260319_0001_auth_production_baseline.py`
  - `docs/API.md`
- 一个生活类比
  LLMRun 像请编辑帮你润色一段扫描文字；编辑可能改得很好，也可能失败，但原稿和编辑记录都要留下。
- 常见误区
  - 认为 LLM 成功是保存题目的唯一前提。
  - 不记录 prompt 版本，导致之后无法解释输出为什么变化。
  - 把模型输出直接当成可信结构，不做 JSON 或 schema 校验。

## 7. DraftEvent

- 概念是什么
  DraftEvent 是 Draft 状态变化和关键动作的事件日志，记录从哪个状态到哪个状态、事件类型、附加信息和时间。
- 为什么项目需要它
  Draft 流水线有创建、开始识别、识别成功/失败、保存入题库等步骤。事件日志可以解释一个 Draft 为什么处于当前状态。
- 在本项目对应哪些文件
  - `backend/app/models/draft_event.py`
  - `backend/app/services/draft_state.py`
  - `backend/app/core/constants.py`
  - `backend/app/api/v1/endpoints.py`
  - `docs/API.md`
- 一个生活类比
  DraftEvent 像医院病历里的时间线：什么时候挂号、检查、出结果、转科，都有记录。
- 常见误区
  - 只更新 Draft 当前状态，不记录状态变化历史。
  - 把事件类型写得随意，导致后续统计和排查困难。
  - 手动改状态时绕过统一的状态转换函数。

## 8. QuestionRevision

- 概念是什么
  QuestionRevision 是题目内容的版本记录，保存某个题目第几版、内容、裁剪区域、来源素材、OCRRun、LLMRun 和修改原因。
- 为什么项目需要它
  题目进入题库后可能继续编辑。版本记录能说明当前题目来自哪次识别和整理，也能支持未来回滚、审计和比较。
- 在本项目对应哪些文件
  - `backend/app/models/question_revision.py`
  - `backend/app/models/question.py`
  - `backend/app/api/v1/endpoints.py`
  - `backend/alembic/versions/20260319_0001_auth_production_baseline.py`
  - `docs/API.md`
- 一个生活类比
  QuestionRevision 像文档的历史版本：最终文档是一份，但每次修改都能看到第几版、改了什么、为什么改。
- 常见误区
  - 只覆盖 Question 当前内容，不保留版本。
  - 不关联 SourceAsset、OCRRun、LLMRun，导致题目来源断链。
  - 忽略同一题目版本号不能重复。

## 9. Alembic 数据库迁移

- 概念是什么
  Alembic 数据库迁移是用版本化脚本管理数据库结构变化的机制，例如建表、加字段、加索引、加约束。
- 为什么项目需要它
  项目有 users、questions、source_assets、drafts、ocr_runs、llm_runs、draft_events、question_revisions 等表，需要一个可信路径让不同环境的数据库结构保持一致。
- 在本项目对应哪些文件
  - `backend/alembic.ini`
  - `backend/alembic/env.py`
  - `backend/alembic/script.py.mako`
  - `backend/alembic/versions/20260319_0001_auth_production_baseline.py`
  - `backend/alembic/versions/20260320_0002_auth_audit_and_rate_limit.py`
  - `backend/app/db/migrations.py`
  - `backend/tests/db_migration_helper.py`
  - `docs/DECISIONS.md`
- 一个生活类比
  Alembic 像房屋施工图的变更记录：什么时候加了一堵墙、换了管线，都按版本执行，不能靠师傅临场记忆。
- 常见误区
  - 依赖运行时 `create_all` 替代正式迁移。
  - 修改模型后忘记写迁移脚本。
  - 不先执行 `alembic upgrade head` 就启动或初始化环境。

## 10. API Contract

- 概念是什么
  API Contract 是前后端约定好的接口契约，包括路径、方法、请求字段、响应字段、状态码和错误形态。
- 为什么项目需要它
  前端、后端、测试脚本需要按同一套接口说话。契约清楚，前端才能稳定调用，后端改动也能知道是否破坏兼容性。
- 在本项目对应哪些文件
  - `docs/API.md`
  - `backend/app/api/v1/endpoints.py`
  - `backend/app/schemas/draft.py`
  - `backend/app/schemas/ocr.py`
  - `backend/app/schemas/question.py`
  - `frontend/tests/login-page-auth-contract.test.mjs`
  - `frontend/tests/auth-session-contract.test.mjs`
  - `frontend/tests/admin-user-management-contract.test.mjs`
  - `docs/API_SMOKE_DRAFT_PIPELINE.md`
- 一个生活类比
  API Contract 像餐厅菜单：顾客按菜单点菜，厨房按菜单出菜，菜单改了双方都要知道。
- 常见误区
  - 只看后端能不能跑，不检查响应字段是否符合前端预期。
  - 改接口路径或字段名但不更新文档和测试。
  - 把内部数据库字段直接当成对外 API 契约。

## 11. Smoke Test

- 概念是什么
  Smoke Test 是快速验证系统关键路径是否基本可用的测试，不追求覆盖所有细节，而是先确认“冒烟级别”的主流程没有断。
- 为什么项目需要它
  项目需要快速确认后端启动、登录、上传素材、创建 Draft、查询 Draft、识别、保存入题库等关键动作是否能连起来。
- 在本项目对应哪些文件
  - `docs/API_SMOKE_DRAFT_PIPELINE.md`
  - `scripts/smoke_draft_pipeline.ps1`
  - `scripts/verify_backend_env.ps1`
  - `docs/STATUS.md`
  - `README.md`
- 一个生活类比
  Smoke Test 像新装电器后先插电看能不能亮，不是马上拆开检查每个零件寿命。
- 常见误区
  - 把 Smoke Test 当成完整测试套件。
  - 只测成功路径，不给失败信息留下清晰输出。
  - 没有准备前置条件，例如服务未启动、迁移未执行、测试用户不存在。

## 12. Git Checkpoint

- 概念是什么
  Git Checkpoint 是用 Git 记录一个阶段性保存点，通常通过查看状态、分组提交、写清提交信息来固定当前工作成果。
- 为什么项目需要它
  项目在逐步迁移主链路和新增 Draft 流水线时，需要把可验证阶段保存下来，方便回看、比较、回滚和继续开发。
- 在本项目对应哪些文件
  - `.git`
  - `docs/WORKLOG.md`
  - `docs/STATUS.md`
  - `docs/DECISIONS.md`
  - `docs/DELIVERY_2026-03-19.md`
- 一个生活类比
  Git Checkpoint 像游戏存档：打过一个关键关卡后先保存，后面探索失败也能回到明确位置。
- 常见误区
  - 把没验证过的代码随手提交成 checkpoint。
  - 一个提交混入太多无关改动，之后难以定位问题。
  - 误以为 checkpoint 会自动说明项目状态，实际还需要清楚的提交信息和文档记录。
