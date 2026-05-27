# WORKLOG

## 2026-05-27 第十四轮：Dashboard UI 状态收口

目标：

- 只收口 `Dashboard.vue` 中 Draft 主路径的前端 UI 状态。
- 保留当前上传主路径 `runRecognition(file)` 调用 Draft API。
- 保留 `runLegacyRecognition()` 和 legacy `POST /api/v1/recognize` 兼容逻辑。
- 不修改后端、数据库模型、API schema，不做大重构。

结果：

- Dashboard 上传、创建 Draft、识别、保存入题库阶段从单一模糊 loading 收敛为阶段化提示。
- 上传确认按钮在识别流程中禁用，保存按钮在保存流程中禁用；重复保存 409 后阻止继续重复点击保存。
- `partial_success` 作为 warning 展示，保留识别结果，不再按完全失败处理。
- 前端对 `400`、`404`、`409`、`401`、`403`、`500` 和网络错误补充可理解提示。
- 409 重复保存提示为“当前草稿已保存或状态不允许重复保存”。
- 非图片 Draft recognize 提示为“当前 Draft recognize 仅支持图片素材”。
- token 失效或权限异常提示指向重新登录。

验证结果：

- `cd frontend && npm run test:auth-contract` 通过。
- `cd frontend && npm run test:stage3-contract` 通过。
- `cd frontend && npm run build` 通过，仅有 Vite chunk size warning。
- `cd backend && python -m compileall app` 通过。
- `cd backend && python -m unittest discover tests` 通过，`Ran 53 tests OK`。

边界：

- 未修改后端代码。
- 未删除、未重构 legacy `POST /api/v1/recognize`。
- 未删除 `runLegacyRecognition()`。
- 未引入大型状态管理库。
- 未处理批量 PDF、多页 Draft 或 legacy 清理。

## 2026-05-27 第十三轮：Draft 异常场景收口

目标：

- 只收口 Draft 主路径后端异常契约和测试。
- 不修改前端 UI，不修改 `Dashboard.vue`，不重构 legacy `POST /api/v1/recognize`。
- 不修改数据库模型或迁移文件。

结果：

- `POST /api/v1/drafts` 对不存在的 `source_asset_id` 返回 `404`。
- `POST /api/v1/drafts/{draft_id}/recognize` 对不存在的 Draft 返回 `404`，对非图片 asset 返回 `400`。
- `POST /api/v1/drafts/{draft_id}/save-to-bank` 对不存在的 Draft 返回 `404`，对未 ready Draft 返回 `409`。
- `saved_to_bank` 状态再次 recognize 返回 `409`。
- `saved_to_bank` 状态再次 save-to-bank 返回 `409`，并验证不会重复创建 Question 或 QuestionRevision。
- `docs/API_SMOKE_DRAFT_FLOW.md` 已补充异常场景期望。
- `docs/STATUS.md` 和 `docs/KNOWN_ISSUES.md` 已同步当前异常契约和重复保存边界。

验证结果：

- `cd backend && python -m compileall app` 通过。
- `cd backend && python -m unittest discover tests` 通过，`Ran 53 tests OK`。
- `cd backend && python -m pytest tests/test_draft_pipeline.py` 通过，`9 passed`。
- `cd backend && python -m pytest tests/test_llm.py` 通过，`8 passed`。
- `cd frontend && npm run test:auth-contract` 通过。
- `cd frontend && npm run test:stage3-contract` 通过。
- `cd frontend && npm run build` 通过，仅有 Vite chunk size warning。

边界：

- 未修改前端代码。
- 未修改数据库模型或 Alembic 迁移。
- 未删除、未重构 legacy `POST /api/v1/recognize`。
- 重复 save-to-bank 当前返回 `409`，未实现幂等返回既有保存结果。

## 2026-05-27 第十二轮：Draft API smoke 验证文档补充

目标：

- 只新增 Draft 主路径 API smoke 验证文档。
- 在 README.md 增加 smoke 文档入口。
- 同步 STATUS 中当前基线与 smoke 文档状态。
- 不修改后端业务代码、前端业务代码、数据库模型、迁移文件或 API schema。

结果：

- 新增 `docs/API_SMOKE_DRAFT_FLOW.md`，说明 Dashboard Draft 主路径、legacy `/api/v1/recognize` 边界、前置条件、推荐验证命令、手动 smoke API 流程、非目标、常见失败原因和验收标准。
- README.md 已增加 Draft API smoke 文档链接，并同步第十二轮文档补充状态。
- docs/STATUS.md 已补充：Draft 主路径已接受为当前基线，已补充 API smoke 验证文档；当前仍是可启动、可验证、可继续开发，不是生产可用。
- 未修改业务代码。
- 未删除 legacy `POST /api/v1/recognize`。

验证结果：

- `cd backend && python -m compileall app` 通过。
- `cd backend && python -m unittest discover tests` 通过，`Ran 46 tests OK`。
- `cd frontend && npm run test:auth-contract` 通过。
- `cd frontend && npm run test:stage3-contract` 通过。
- `cd frontend && npm run build` 通过，仅有 Vite chunk size warning。

边界：

- 未执行手动真实接口 smoke；本轮补充的是验证文档，并运行项目最小验证命令。
- 未修改后端业务代码、前端业务代码、数据库模型、Alembic 迁移或 API schema。
- 未删除 `/api/v1/recognize`。

## 2026-05-27 第十一轮补充：Dashboard Draft 接入基线确认

目标：

- 核查 `Dashboard.vue` 当前上传入口事实。
- 复跑后端和前端最小验证命令。
- 判断当前 Dashboard Draft 接入是否接受为新的前端主路径基线。
- 不修改后端业务代码、前端业务代码，不删除 `/api/v1/recognize` 或 `runLegacyRecognition()`。

结果：

- `Dashboard.vue` 当前上传按钮链路为：`confirmCropAndUpload()` / `uploadFullImage()` -> `runRecognition()` -> `POST /api/v1/assets` -> `POST /api/v1/drafts` -> `POST /api/v1/drafts/{draft_id}/recognize`。
- 保存入题库调用 `POST /api/v1/drafts/{draft_id}/save-to-bank`。
- `runLegacyRecognition()` 仍存在，仍调用 `POST /api/v1/recognize`，但当前上传按钮和主上传流程不引用它。
- 接受当前 Dashboard Draft 初步接入作为新的前端主路径基线。
- `/api/v1/recognize` 定义为 legacy / 兼容入口，继续保留。
- Draft 前端接入仍不是完整生产级完成，后续仍需 smoke 文档、异常场景、UI 状态和 legacy 清理。

验证结果：

- `cd backend && python -m compileall app` 通过。
- `cd backend && python -m unittest discover tests` 通过，`Ran 46 tests OK`。
- `cd backend && python -m pytest tests/test_llm.py` 通过，`8 passed`。
- `cd frontend && npm run test:auth-contract` 通过。
- `cd frontend && npm run test:stage3-contract` 通过。
- `cd frontend && npm run build` 通过，仅有 Vite chunk size warning。

边界：

- 未修改后端业务代码、前端业务代码、数据库模型、Alembic 迁移或 API schema。
- 未删除 `/api/v1/recognize`。
- 未删除 `runLegacyRecognition()`。
- 未做异步队列、批量 PDF、多页 draft 或 provider 抽象。

## 2026-05-27 第十一轮：阶段评估与下一阶段路线确认

目标：

- 只做项目阶段评估。
- 执行 git 状态确认和后端、前端最小验证命令。
- 检查 README、STATUS、WORKLOG、KNOWN_ISSUES、DECISIONS 与实际代码状态是否一致。
- 不开发新功能，不重构业务代码，不切换主链路。

结果：

- 当前分支确认为 `release-hardening-1`。
- 后端最小验证全部通过。
- 前端契约测试和构建全部通过，构建仍有 Vite chunk size warning。
- 发现文档状态与当前 `Dashboard.vue` 实际行为不一致：当前上传按钮已调用 Draft 相关接口，`runLegacyRecognition()` 中的 `/api/v1/recognize` 调用仍保留但未被上传按钮引用。
- 已更新 docs/STATUS.md 和 docs/KNOWN_ISSUES.md，记录上述状态漂移和下一阶段确认要求。

验证结果：

- `cd backend && python -m compileall app` 通过。
- `cd backend && python -m unittest discover tests` 通过，`Ran 46 tests OK`。
- `cd backend && python -m pytest tests/test_llm.py` 通过，`8 passed`。
- `cd frontend && npm run test:auth-contract` 通过。
- `cd frontend && npm run test:stage3-contract` 通过。
- `cd frontend && npm run build` 通过，仅有 Vite chunk size warning。

边界：

- 未修改后端业务代码、前端业务代码、数据库模型、Alembic 迁移或 API schema。
- 未修改 README.md，因为本轮用户允许更新范围只列出 docs 下项目记忆文件；README 仍需后续同步。
- 未修改 docs/DECISIONS.md，因为本轮没有新的架构决策，只记录阶段评估发现。

## 2026-05-27 第十一轮：README / STATUS 最新验证口径同步

目标：

- 只做文档同步。
- 将 README.md 和 docs/STATUS.md 对齐第八、第九、第十轮后的最新状态。
- 保留 `/api/v1/recognize` 仍是当前 MVP 主入口、Draft 流水线仍是后端旁路能力、当前不是生产可用的边界。

结果：

- README.md 已同步最新验证结果和第八、第九、第十轮已完成工作。
- docs/STATUS.md 已从第七轮后端旁路 Draft 流水线状态推进到第十轮前端 Markdown / LaTeX 渲染收敛后。
- 未修改任何后端代码、前端代码、测试代码或配置代码。

验证结果：

- 文档修改，未运行代码测试。

边界：

- 未修改 docs/DECISIONS.md，因为本轮没有新的架构、API、数据模型或流程决策。
- 未修改 docs/KNOWN_ISSUES.md，因为当前风险仍然成立，未发现与当前事实冲突。

## 2026-05-26 第十轮：前端 Markdown / LaTeX 渲染工具抽取

目标：

- 抽取前端共享 Markdown / LaTeX 渲染工具，统一 `Dashboard.vue`、`BankPanel.vue`、`HistoryPanel.vue` 的渲染配置。
- 统一使用 `html: true`、`breaks: true`、`linkify: true` 和 `markdown-it-mathjax3`。
- 仅在展示前归一化 LaTeX 分隔符，不修改题目原始数据。

结果：

- 新增 `frontend/src/utils/renderMarkdown.ts`，集中初始化 `markdown-it` 和 `markdown-it-mathjax3`。
- 新增前端展示层 `normalizeLatexDelimiters()`，将 `\(...\)` 转为 `$...$`、`\[...\]` 转为 `$$...$$`。
- 三个组件改为导入共享 `renderMarkdown`，删除各自重复的 MarkdownIt 初始化。
- 为满足 `@/utils/renderMarkdown` 导入，`frontend/vite.config.js` 增加 `@ -> src` alias。

验证结果：

- `cd frontend && npm run build` 通过。
- `cd frontend && node --input-type=module -e '...'` 样例渲染检查通过，覆盖 `\(\triangle ABC\)`、`\(\frac{a}{b}\)`、`\[x^2 + y^2 = z^2\]`、`$x$`、`$$x^2$$`。
- `frontend/package.json` 未定义 `type-check` 或 `lint` 脚本，未运行对应命令。

边界：

- 未修改后端、API、Draft pipeline、数据库模型或前端 UI 布局。
- 未新增依赖，未删除 `katex`，未处理 `markdown-body` 样式。

## 2026-05-25 第九轮：LLM analyze 成功路径 LaTeX 归一化集成测试

目标：

- 补充 mock 级集成测试，证明 `NLPService.analyze()` 成功路径返回的 `corrected_text` 会经过 `normalize_latex_delimiters`。
- 不请求真实 DeepSeek API。
- 不修改生产代码、前端、Draft 流水线或 API schema。

结果：

- 在 `backend/tests/test_llm.py` 新增 fake LLM client 响应。
- 测试覆盖 LLM 返回纯 JSON、`corrected_text` 含 `\(...\)` 和 `\[...\]` 时，`analyze()` 返回结果会归一化为 `$...$` 和 `$$...$$`。
- 同时断言 tags 正常返回，旧分隔符不再出现在成功结果中。

验证结果：

- `cd backend && python -m pytest tests/test_llm.py` 通过，`8 passed`。
- `cd backend && python -m compileall app` 通过。
- `cd backend && python -m unittest discover tests` 通过，`Ran 46 tests OK`。

边界：

- 未修改 `backend/app/services/llm.py`。
- 未修改前端、Draft pipeline、API schema 或数据库模型。

## 2026-05-25 第八轮：LLM LaTeX 分隔符程序级归一化

目标：

- 在 LLM 输出后增加确定性的 LaTeX 分隔符归一化。
- 将 `\(...\)` 归一化为 `$...$`。
- 将 `\[...\]` 归一化为 `$$...$$`。
- 保持 `/api/v1/recognize` 返回结构不变，不改前端，不改 Draft 流水线。

结果：

- 在 `backend/app/services/llm.py` 新增 `normalize_latex_delimiters` 纯函数。
- 在 `corrected_text` 类型校验通过后、成功返回前调用归一化函数。
- 新增 `backend/tests/test_llm.py` 覆盖行内公式、块级公式、既有 dollar 分隔符、普通中文文本和空字符串。

验证结果：

- `cd backend && python -m compileall app` 通过。
- `cd backend && python -m unittest discover tests` 通过，`Ran 45 tests OK`。
- `cd backend && python -m pytest tests/test_llm.py` 通过，`7 passed`。

边界：

- 不修改 raw OCR text。
- 不修改 timeout、异常处理、JSON 解析、字段校验、tag normalization。
- 不新增依赖。

## 2026-05-07 第七轮：后端旁路正式流水线最小竖切

目标：

- 新增 Draft 后端旁路正式流水线最小竖切。
- 保持当前前端主链路仍使用 `/api/v1/recognize`。
- 不立即硬切 `Dashboard.vue`。

新增后端旁路接口：

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

验证结果：

- `cd backend && python -m compileall app` 通过。
- `cd backend && python -m unittest discover tests` 通过，`Ran 38 tests OK`。

边界：

- Draft 流水线目前是后端旁路能力。
- 当前前端主链路仍然是 `/api/v1/recognize`。
- `Dashboard.vue` 尚未切换到 Draft 流水线。
- `/api/v1/recognize` 未删除、未重构，仍是当前 MVP 主入口。
- 不写成生产可用。
- 不写成完整多页 PDF 或批量 draft 已完成。

下一步：

- 可以做 API smoke 文档。
- 可以做前端接入方案评估。
- 不要立即硬切前端。

## 2026-05-07 第六轮：记录主链路决策

目标：

- 只更新文档。
- 记录主链路选择 C：短期继续 `/api/v1/recognize`，长期逐步迁移到 `assets/drafts/ocr_runs/llm_runs` 正式流水线。
- 明确下一阶段只做最小正式流水线后端竖切，不硬切现有前端。

结果：

- [docs/DECISIONS.md](/d:/math_knowledge_system/docs/DECISIONS.md) 已新增主链路渐进式迁移决策。
- [docs/STATUS.md](/d:/math_knowledge_system/docs/STATUS.md) 已更新当前结论、未闭合边界和下一阶段口径。
- [docs/KNOWN_ISSUES.md](/d:/math_knowledge_system/docs/KNOWN_ISSUES.md) 已将“主链路决策尚未完成”更新为“正式流水线最小后端竖切尚未实现”。

边界：

- 当前主链路仍是 `/api/v1/recognize`。
- `/upload_pdf`、`/assets`、drafts 当前不是主前端闭环。
- 不删除 `/recognize`。
- 不现在硬切 `Dashboard.vue`。
- 不做 OCR/LLM provider 抽象、异步队列、批量 PDF、多页 draft 管理。

## 2026-05-05 第三轮：项目文档收口

目标：

- 只更新文档和示例配置文件。
- 记录第二轮修复结果。
- 明确当前能力边界，避免夸大完成度。

结果：

- [README.md](/d:/math_knowledge_system/README.md) 已收口启动、迁移、管理员初始化、最小验证和能力边界。
- [docs/STATUS.md](/d:/math_knowledge_system/docs/STATUS.md) 已更新当前状态为“可启动、可验证、可继续开发”。
- [docs/KNOWN_ISSUES.md](/d:/math_knowledge_system/docs/KNOWN_ISSUES.md) 已更新当前未闭合风险。
- [docs/DECISIONS.md](/d:/math_knowledge_system/docs/DECISIONS.md) 已补充第三轮文档口径决策。
- [backend/.env.example](/d:/math_knowledge_system/backend/.env.example) 已创建为后端本地配置示例。

第二轮验证记录：

- `frontend npm run build` 通过，仅有 Vite chunk size warning。
- `frontend npm run test:auth-contract` 通过。
- `frontend npm run test:stage3-contract` 通过。
- `backend python -m compileall app` 通过。
- `backend python -m unittest discover tests` 通过，`Ran 36 tests OK`。
- `backend/requirements.txt` 已补齐 `passlib[bcrypt]`。
- `frontend/package.json` 已显式声明 `@element-plus/icons-vue`。
- README 已修正管理员初始化路径。
- README 已明确 `alembic upgrade head` 是硬前置。
- README 已标注 `/upload_pdf`、`/assets`、draft 流水线目前未接入主前端。
- `backend/.env` 是本地文件，不应提交。

## 2026-04-20 测试与交付治理收口

结果：

- 固定最小回归测试集和发布前门禁。
- 明确 README / STATUS / WORKLOG / DECISIONS / KNOWN_ISSUES 的职责边界。
- 历史快照和历史设计稿继续保留，但不作为当前状态依据。

## 2026-03-24 数据库迁移治理收口

结果：

- 明确正式 schema 演进以 Alembic 为唯一可信路径。
- production 环境禁止运行时 schema 变更。
- 非 production 环境也只有显式开启兼容开关时才允许运行时 schema 兜底。

## 2026-03-19 主链路修复与验收

结果：

- 收敛后端配置和路径解析。
- 接入真实 JWT 登录。
- 统一图片 URL 返回。
- 收口 OCR / LLM 失败路径。
- 完成人工浏览器验收。
- 明确真实第三方失败场景尚未系统化验证。
