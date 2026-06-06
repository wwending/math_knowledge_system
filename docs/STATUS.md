# STATUS

## 2026-06-06 第二十点六轮 Draft LLM 非思考模式 + JSON 输出稳定化

当前项目暂停第二十一轮新功能，根据 DeepSeek 官方文档将第二十点六轮目标从“单纯提高 max_tokens”调整为 Draft LLM 非思考模式和 JSON 输出稳定化。

新增能力：

- Draft LLM 调用默认关闭 thinking：OpenAI SDK 调用传入 `extra_body={"thinking": {"type": "disabled"}}`。
- thinking mode 可通过 `LLM_THINKING_MODE` 配置，默认 `disabled`。
- 启用 JSON Output：OpenAI SDK 调用传入 `response_format={"type": "json_object"}`。
- system/user prompt 均明确 JSON 要求，user prompt 包含 JSON 输出样例。
- Prompt 角色调整为“高中数学 OCR 文本清洗与结构化工具”，强调不解题、不证明、不分析、不输出推理过程，只修正 OCR、只规范 LaTeX、只返回 JSON。
- `max_tokens` 可通过 `LLM_MAX_TOKENS` 配置，默认 `2048`；timeout 可通过 `LLM_TIMEOUT_SECONDS` 配置，默认 `45` 秒。
- 不传 `reasoning_effort`，避免 DeepSeek low/medium 映射为 high。
- 第二十点五轮安全摘要日志继续保留：`finish_reason`、`content_len`、`reasoning_content_len`、`usage_completion_tokens`、`usage_total_tokens`、`raw_response_preview` 等字段仍记录。
- `finish_reason=length` 且 content 为空时继续 fallback，并返回可区分 detail：`deepseek_length_exhausted_empty_content`。

当前边界：

- 本轮未修改 PaperRenderModel、PaperPreview、前端、数据库模型、Alembic 迁移或 legacy `/api/v1/recognize`。
- 本轮未把 max_tokens 直接升到 6000。
- 本轮未把 `reasoning_content` 当作 `corrected_text` 使用。
- Draft fallback 状态机未改变：LLM 失败仍返回 `draft_ready + partial_success=True`。
- 复杂椭圆题仍需真实在线复测，以确认关闭 thinking 和 JSON Output 后是否消除 empty content。

验证结果：

- `cd backend && python -m unittest tests.test_llm` 通过。
- `cd backend && python -m unittest tests.test_draft_pipeline.DraftPipelineTests.test_draft_recognize_records_empty_content_invalid_response` 通过。
- `cd backend && python -m compileall app` 通过。
- `cd backend && python -m unittest discover tests` 通过，`Ran 92 tests OK`。

## 2026-06-06 第二十点五轮 Draft LLM 空响应诊断增强

当前项目暂停第二十一轮新功能，针对第二十轮人工验收发现的复杂 OCR 文本触发 DeepSeek empty content 问题，完成 Draft LLM 响应解析的最小可观测性增强。

新增诊断能力：

- `NLPService.analyze()` 对 DeepSeek 响应生成安全摘要日志，覆盖 response 类型、id、model、choices 数、finish_reason、message role、content 长度和截断预览、refusal、reasoning_content、tool_calls、usage token、输入长度、配置模型、timeout 和截断 raw response preview。
- empty content、空 choices、缺 choices、非 JSON、缺 `corrected_text`、字段结构非法等分支不再打印完整 response/result，改为打印安全摘要。
- empty content 的 `detail` 包含 `choices_count`、`finish_reason`、`content_len`、`completion_tokens`，便于下一次复杂题复现时定位原因。
- Draft fallback 状态机未改变：LLM 失败仍返回 `draft_ready + partial_success=True`，并保留 warning 和 LLMRun 错误信息。

当前边界：

- 本轮未修改 PaperRenderModel、PaperPreview、前端、数据库模型、Alembic 迁移或 legacy `/api/v1/recognize`。
- 本轮未恢复 `response_format={"type": "json_object"}`；是否启用需等待复杂椭圆题复现后的日志证据。
- 本轮不表示已彻底解决所有 DeepSeek 空响应，只表示已有可诊断日志和测试保护。

验证结果：

- `cd backend && python -m compileall app` 通过。
- `cd backend && python -m unittest discover tests` 通过，`Ran 90 tests OK`。

## 2026-06-06 第二十轮 PaperRenderModel + 作业模板预览 MVP

当前项目在不修改 Paper / PaperItem 数据库模型、不做迁移、不做 PDF / DOCX 导出、不切换 Draft/Paper 主流程的前提下，为已有试卷增加学生版作业预览能力。

新增能力：

- 新增 `POST /api/v1/papers/{paper_id}/render-model`，将 Paper / PaperItem 快照转换为 PaperRenderModel。
- 当前仅支持 `template_type=homework`、`version=student`、`paper_size=A4`、`group_by=question_type`、`sort_by=position`。
- 支持 `answer_area_mode=none` 和 `after_each_question`，默认 `none`。
- PaperRenderModel 按 `question_type_snapshot` 分组，每组内按 `position` 排序，`display_number` 全局连续。
- `question_type_snapshot` 为空时归入 `unknown / 未分类`。
- 学生版响应层面不返回答案解析快照。
- `PaperPanel.vue` 增加预览入口，`PaperPreview.vue` 渲染 A4 作业样式并复用 `renderMarkdown.ts`。

当前边界：

- 不支持自动分页；长题会撑开 A4 视觉容器。
- 不支持 PDF / DOCX 导出。
- 不支持用户自定义模板、模板编辑器、拖拽排序、知识点排序、难度排序或复杂答题卡。
- 当前预览适合 MVP 验收，不等同于正式打印排版引擎。

## 2026-06-04 第十九轮性能收口：元数据后台补全

当前项目在不重构 OCR / Draft / Paper 主流程、不删除 legacy recognize、不新增排序/模板/导出/答题区/智能组卷的前提下，将题型与五星难度从同步 Draft recognize 主链路拆出，改为保存入题库后后台补全。

新增能力：

- LLM analyze 默认轻量返回 `corrected_text` 和 `knowledge_tags`；题型/难度评估需显式调用元数据评估。
- 旧字段 `tags` 继续兼容；`corrected_text` 仍是主结果。
- Draft recognize 只强制等待 OCR + 轻量 LLM 洗稿 + 知识点标签，不再强制等待题型/难度。
- Draft save-to-bank 创建 `Question` 后设置 `metadata_status=pending`，并通过 FastAPI `BackgroundTasks` 后台补全题型与难度。
- Question 列表和详情返回题型、难度以及 `metadata_status` / `metadata_error` / 开始结束时间。
- PaperItem 仅在 Question 元数据 ready 且已有难度时保存题型与难度快照；pending/failed/null 时快照为空但不阻止组卷。
- `BankPanel.vue` 支持展示“元数据评估中”“难度评估失败”“未评估”和五星难度。
- Draft recognize 增加 `[DraftRecognizePerf]` 性能日志；后台元数据评估增加 `[QuestionMetadataPerf]` 性能日志。
- 补充 recognize 和 metadata 阶段耗时日志：Draft recognize 记录 OCR、轻量 LLM、total 和失败阶段；后台 metadata 记录 load、prompt、api、parse、db 和 total。

当前边界：

- 不支持按难度排序或筛选。
- 不支持按知识点排序。
- 不支持组卷模板、自定义模板、PDF / DOCX 导出、答题区域或智能组卷。
- LLM 难度评分是估计值，不是绝对标准。
- 历史题目可能没有题型和难度字段。
- 用户编辑题目后不会自动重新评估难度。
- 前端不轮询元数据状态；用户刷新题库后可看到后台评估结果。
- 后台任务依赖当前后端进程，服务重启可能丢失正在执行的元数据评估任务。

## 2026-06-03 第十八轮前端组卷入口 MVP

当前项目在不改动后端 Paper API 主逻辑、不改动 Draft flow、不改动 legacy recognize 的前提下，新增前端最小组卷入口。

新增前端能力：

- `BankPanel.vue` 支持从当前题库勾选题目、显示已选数量，并创建试卷。
- 创建试卷调用 `POST /api/v1/papers`，items 使用当前已选题目生成 `{ question_id, score }`，score 当前统一为 `0`。
- 新增 `PaperPanel.vue`，支持查看当前用户试卷列表和试卷详情。
- `Dashboard.vue` 新增独立“组卷”菜单入口，不干扰题目录入、Draft 保存入库、题库查看和历史记录。
- 试卷详情中的题目内容、答案、解析继续复用 `frontend/src/utils/renderMarkdown.ts` 渲染 Markdown / LaTeX。

当前组卷前端能力边界：

- 只支持手动从题库选题创建试卷。
- 不支持拖拽排序。
- 不支持分值编辑。
- 不支持 PDF / Word 导出。
- 不支持智能组卷。
- 不支持复杂试卷排版或打印样式优化。

## 2026-05-27 第十七轮组卷 MVP 后端最小竖切

当前项目在既有 Draft flow、legacy recognize 和题库保存逻辑不重构的前提下，新增后端最小组卷能力。

新增接口：

- `POST /api/v1/papers`
- `GET /api/v1/papers`
- `GET /api/v1/papers/{paper_id}`

当前组卷能力边界：

- 只支持登录用户手动选择自己题库中的题目组卷。
- `PaperItem` 保存题目快照；如存在 `QuestionRevision`，优先以最新 revision 生成快照。
- 当前不支持智能组卷、PDF/Word 导出、前端组卷、拖拽排序、自动配比。

## 2026-05-27 第十六轮 release checkpoint

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
- 第十三轮已阶段性收口 Draft 后端异常契约：缺失 asset/draft、非图片 recognize、未 ready 保存、重复保存、已保存后再次识别均返回可解释的 4xx。
- 第十四轮已收口 Dashboard Draft 主路径 UI 状态：上传素材、创建草稿、识别、保存入题库有阶段化提示；识别中和保存中按钮分别禁用；`partial_success` 作为 warning 展示；常见错误码有前端可理解提示。
- 第十五轮已完成 legacy recognize 引用审计与最小标注：Dashboard 主路径确认继续走 Draft，`runLegacyRecognition()` 和 `POST /api/v1/recognize` 均保留为 legacy / 兼容入口。
- 第十六轮已完成阶段性文档去重和 release checkpoint：README、API、smoke 文档、STATUS、DECISIONS、KNOWN_ISSUES、WORKLOG 的当前口径已统一。
- 第十七轮已完成组卷 MVP 后端最小竖切，新增 Paper / PaperItem、papers API、service 和后端测试；不涉及前端、导出或智能组卷。
- 第十八轮已完成前端组卷入口 MVP：题库选题、创建试卷、试卷列表、试卷详情已接入；不涉及后端 Paper API 主逻辑、导出、智能组卷或 Draft/recognize 改动。
- 第十九轮已完成 LLM 题型与五星难度元数据，并完成性能收口：Draft recognize 主链路只强制等待 OCR、`corrected_text` 和知识点标签，题型/难度在 save-to-bank 后通过后台任务补全到 Question。
- Draft 前端接入不是完整生产级完成，legacy recognize 已完成引用审计和误用风险标注，仍需后续退场策略执行。
- 当前推荐 smoke 文档为 `docs/API_SMOKE_DRAFT_FLOW.md`；`docs/API_SMOKE_DRAFT_PIPELINE.md` 保留为脚本化 smoke 补充文档。
- `saved_to_bank` 状态重复 save-to-bank 当前返回 `409`，本轮不改为幂等返回，且已测试不会重复创建 Question 或 QuestionRevision。
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
| frontend | `npm run test:auth-contract` | 通过 |
| frontend | `npm run test:stage3-contract` | 通过 |
| frontend | `npm run build` | 通过，仅有 Vite chunk size warning |
| backend | `python -m compileall app` | 通过 |
| backend | `python -m unittest discover tests` | 通过，`Ran 74 tests OK` |
| backend | `alembic current` | 默认本地 SQLite 当前 `20260604_0004` |
| backend | `DATABASE_URL=sqlite:///./alembic_verify_tmp.db alembic upgrade head; alembic current` | 通过，当前 `20260604_0005 (head)` |
说明：

- 第十九轮性能收口已重新实测 `python -m compileall app`、`python -m unittest discover tests`、`npm run build`、`npm run test:auth-contract`、`npm run test:stage3-contract`。
- 第十九轮性能收口默认 `alembic upgrade head` 因当前本地 SQLite 数据库只读失败，默认 `alembic current` 显示仍为 `20260604_0004`；已改用临时 SQLite 数据库验证迁移链成功到 `20260604_0005 (head)`。
- 第十九轮初次元数据实现已重新实测 `python -m compileall app`、`python -m unittest discover tests`、`npm run build`、`npm run test:auth-contract`、`npm run test:stage3-contract`；当时临时 SQLite 迁移链验证到 `20260604_0004 (head)`。
- 第十八轮已重新实测 `npm run build`、`npm run test:auth-contract`、`npm run test:stage3-contract`；其中 `test:stage3-contract` 已纳入 Paper MVP 前端契约检查。
- 第十七轮已重新实测 `python -m compileall app`、`python -m unittest discover tests`。
- 第十六轮已重新实测 `npm run test:auth-contract`、`npm run test:stage3-contract`、`npm run build`、`python -m compileall app`、`python -m unittest discover tests`。
- `python -m pytest tests/test_draft_pipeline.py` 和 `python -m pytest tests/test_llm.py` 为第十三轮专项验证结果，本轮未重复执行。
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
- Dashboard Draft 接入已接受为新基线，已补充 API smoke 验证文档，后端异常契约和前端 UI 状态已完成阶段性收口；仍需后续 legacy 清理。
- Draft 重复保存当前以 `409` 拒绝，不返回既有保存结果；如后续需要幂等返回，应另行设计保存结果追踪方式。
- mock/legacy 文件需要清理，但不应在下一阶段做大重构。
- 后端测试已通过本轮验证，但稳定性仍需持续关注。
- 真实第三方失败场景仍缺少系统化在线验证矩阵。
- 完整多页 PDF 和批量 draft 能力未完成，不应在当前状态中夸大。
- legacy recognize 最终退场未完成，当前仍保留为兼容入口。
- 当前状态不是生产可用。

## 下一阶段口径

下一阶段以收敛和稳定为主，不新增规划之外的大模块，不做大重构。优先级为：前端中文乱码、mock/legacy 文件清理、后端测试稳定性。

明确不做：

- 不删除 `/recognize`。
- 不把 Draft 前端接入写成完整生产级完成。
- 不做 OCR/LLM provider 抽象。
- 不做异步队列。
- 不做批量 PDF。
- 不做多页 draft 管理。
- 不把 legacy recognize 写成 Dashboard 当前主路径。
