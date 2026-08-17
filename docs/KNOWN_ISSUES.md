# KNOWN_ISSUES

## 0.17 KaTeX 块公式资源限制边界已加固

块公式闭合行长度漏计和大量伪 `$$` 候选导致的重复尾部扫描已修复。长度检查发生在 KaTeX 调用前，结束符扫描为最多 200 行内的有界线性扫描；同行/末行超长、201 行和复杂度回归已覆盖。KaTeX 仍只支持既有文档所列常用公式，不扩大为完整 LaTeX 支持。

## 0.16 前端依赖审计仍有 25 项未清零

前端运行时安全加固已禁用 Markdown 原始 HTML 和自动裸链接转换，将 Axios 从 `1.13.2` 升级到 `1.19.0`，并以 `katex 0.16.27` 替换不安全的 `markdown-it-mathjax3` / `mathxyjax3` 公式链。2026-08-06 本次 registry 实时 audit 在 KaTeX 迁移前后均为 25 项（15 moderate、10 high、0 critical）；这取代较早同日 9 项的快照。KaTeX 不在公告链中，本次迁移没有新增 high/critical。

剩余注意：

- `markdown-it` 仍有 moderate ReDoS 公告，`linkify-it` 仍在依赖树中并有 high 复杂度公告；关闭 `linkify` 降低了业务入口攻击面，但不等于依赖公告已修复。
- Vite、Rollup、PostCSS、Picomatch、Immutable、Lodash 等构建链或传递依赖仍有 high 公告。
- Vite、Sass 和相关构建工具链升级必须在后续独立 PR 中评估，不运行 `npm audit fix` 或 `npm audit fix --force`。
- KaTeX renderer 支持仓库当前常用的上下标、分数、根号、`aligned`、`cases`、矩阵和中文 `\text{}`，但不支持动态 `\require`、Xy-pic、bussproofs 或任意完整 LaTeX；若未来引入这些核心公式，必须先做兼容性评估。
- 当前仍有既有 Vite chunk size warning；本轮不宣称所有 npm 漏洞已清零。

## 0.15 first-party digest-pinned deployment contract 已实现，待真实 Staging rollout 验证

2026-08-16 已在 [SERVER] 使用 `main` SHA `b78fbd43deadda495771d0fe221d76d81e9486b2` 完成首次完整 Staging GHCR pull-only deployment。backend/web release images 的 pull、OCI revision、RepoDigest、备份、Alembic migration、Compose rollout、HTTP/Nginx health 和 backend 到内部 Gotenberg 的真实 PDF smoke 均通过；数据库 `current == head == 20260604_0005`，服务 restart count 均为 0，数据库 quick check 与 uploads 完整性通过。

已验证：

- backend RepoDigest：`sha256:c4e78f2a6ce0f5c2b4d532be81c92d795522f1d446f6d88ce2daa8f354f5d524`。
- web RepoDigest：`sha256:f039b40b67c5b0f0ab319fd39c6649dcec4961c42f9b4c335d56b50434574993`。
- Gotenberg 宿主机端口 `3000` 未暴露；backend 到内部 Gotenberg 的真实 smoke 生成了有效 `%PDF-` 文件。

剩余注意：

- implementation PR 已将 backend/web Compose 与部署合同改为 trusted exact digest 输入，同时保留 checkout SHA 与 OCI revision 匹配门禁；当前 [SERVER] 仍运行上次已验证的 SHA-tag rollout，尚未执行真实 digest-pinned Staging deployment。
- 合并后必须等待新的 successful main `Publish release images`，取得其记录的 backend/web digest，再以精确 main checkout 做一次显式 Staging rollout 验证；在此之前不能宣称 digest-pinned Staging 已通过。
- 第三方 `gotenberg/gotenberg:8.34.0-chromium` 仍使用固定 version tag，未 digest pinning；本阶段不包含 image signing、SLSA 或 SBOM admission policy。
- GHCR credential 生命周期不由 `deploy.sh` 管理，仍是管理员 preflight 责任。
- authenticated business-level `/papers/{id}/pdf` 未在本次 infrastructure deployment 中重新执行；本次验证的是 backend 到 Gotenberg 的真实服务 smoke。
- Demo/production HTTPS 与 Demo/production deployment 尚未完成；首次 Staging deployment 通过不等于 production ready。
- 2026-08-06 前端运行时加固后，现场 `npm audit` 仍报告 9 项（1 moderate、8 high）；剩余问题覆盖 Markdown 渲染运行时依赖和 Vite/Sass/Rollup 等构建链，需在独立依赖安全 PR 中评估升级兼容性。

## v0.1 Release Candidate 范围说明

- 生产默认 OCR 固定为百度 OCR，`OCR_PROVIDER=baidu`。
- RapidOCR 只作为历史实验代码保留，不属于 v0.1 交付范围。下文 RapidOCR 记录是历史事实，不代表仍在迁移或评估。
- 除非真实客户需求或成本数据要求重新评估，否则不再继续比较或迁移 RapidOCR、PaddleOCR、Pix2Text。
- 当前发布阻塞项是至少 5 张真实数学题图片的百度 OCR + LLM 人工 smoke；自动化测试不调用真实外部服务。
- Vite 大 chunk warning 与受限 Windows 环境中的 pytest cache warning 当前为非阻塞问题。

## 0.14 RapidOCR 已能完成本地 smoke，但质量结论尚未形成

第二十八轮已新增 `backend/scripts/evaluation/compare_ocr_providers.py`，可以用同一批题图对比 `baidu` 和 `rapidocr`，并输出 Markdown / JSON 结果。

第二十八点五轮已使用 `D:\math_knowledge_system\data\manual_smoke\ocr_images` 中 3 张 smoke 图片真实运行 first smoke，未带 `--with-llm`。

第二十八点七轮已探测并适配 RapidOCR 3.8.4 返回结构，修复 `unsupported result format` 误判，并重新运行 rapidocr-only smoke 与完整 baidu vs rapidocr A/B。

已处理：

- 可以记录每张图每个 provider 的成功状态、错误信息、耗时、OCR 原文、文本长度和 `quality_warnings`。
- 可选 `--with-llm` 用于记录 LLM 清洗结果和知识点标签；默认不调用 LLM。
- 单个 provider、单张图片或 LLM 调用失败不会中断整批评测。
- `backend/reports/ocr_ab/` 已加入 `.gitignore`，真实评测报告默认不提交。
- Baidu OCR 在 3 张 smoke 图片上均成功返回文本。
- RapidOCR 3.8.4 返回对象类型为 `rapidocr.utils.output.RapidOCROutput`，关键字段为 `txts`、`boxes`、`scores`，并提供 `to_json()`。
- `RapidOcrProvider` 已兼容 `txts/texts`、array-like `boxes/scores`、`to_dict()` / `model_dump()` / `to_json()`、旧 tuple/list/dict 结构和合法空文本。
- RapidOCR-only smoke 对 3 张图片均成功返回文本。
- 完整 A/B 重跑中 Baidu 与 RapidOCR 均 3 张成功。

剩余注意：

- `unsupported result format` 已解决；当前剩余问题转为识别质量判断。
- RapidOCR 文本长度明显短于 Baidu：本轮完整 A/B 中 RapidOCR 3 张文本长度为 43、87、95，Baidu 为 74、326、291。
- RapidOCR 耗时约 2.1-2.8 秒，Baidu 约 0.9-1.4 秒；低配服务器 CPU 耗时仍需继续观察。
- RapidOCR 的数学公式、双栏选项、几何图题和版面结构仍需人工逐题核对，不能直接认定可替代 Baidu。
- 第二张 RapidOCR 结果触发 `choice_options_incomplete`，仍需关注选项漏识别。
- 如果报告包含真实题图路径、OCR 原文或第三方响应摘要，提交前需要人工判断是否适合入库。

## 0.13 pytest 根目录历史 DeepSeek 脚本收集失败已清理

第二十七点五轮已清理 `python -m pytest` 自动收集根目录历史 DeepSeek 调试脚本导致的失败。

已处理：

- `backend/test_deepseek.py` 确认为历史手工调试脚本，不是正式测试。
- 已移动到 `backend/scripts/manual/deepseek_manual_check.py`。
- 脚本改用当前 `app.services.llm.nlp_service.analyze()` 接口，不恢复旧 `correct_text`。
- `python -m pytest` 当前已能收集并运行 `backend/tests/` 下 117 个测试。

剩余注意：

- 手工脚本如需真实调用 DeepSeek，仍依赖本地 `.env` 中的 DeepSeek 配置。
- 自动化测试不得依赖真实 DeepSeek API key、外部网络或真实 LLM 响应。

## 0.12 RapidOCR 已实验接入但真实数学题效果待评估

第二十七轮已接入 `RapidOcrProvider`，Draft OCR Provider 可通过 `OCR_PROVIDER=baidu` / `OCR_PROVIDER=rapidocr` 切换，默认仍为 `baidu`。

当前限制：

- RapidOCR 当前只是本地文本 OCR 实验 provider，不代表已经解决数学公式、几何图、版面结构或双栏选项漏识别。
- RapidOCR 首次运行可能存在模型加载耗时，低配服务器 CPU 推理性能需要实测。
- 当前自动化测试只覆盖 provider 选择、依赖缺失错误和返回结构解析，不调用真实 RapidOCR 模型。
- 本地 RapidOCR 与百度 OCR 的质量差异需要用本地 smoke 题图逐题对比，尤其关注公式、选项完整性、`quality_warnings` 和 OCR 原文。

影响：

- 后续不能直接把 `rapidocr` 设为默认 provider。
- 下一步应运行第二十八轮 A/B smoke 脚本，记录 baidu/rapidocr 的识别文本、耗时、风险提示和人工结论。

## 0.11 OCR 双栏选项漏识别仍未根治

第二十六轮已增加识别结果风险提示和保存前确认，用于降低残缺选择题无感入库的风险。

当前已做的缓解：

- Draft 响应新增 `quality_warnings`，动态提示识别文本风险。
- 疑似选择题选项不足 4 个时提示 `choice_options_incomplete`。
- 选项标签不连续时提示 `choice_options_sequence_gap`。
- 识别文本过短或 LLM 清洗后明显短于 OCR 原文时提示用户核对。
- Dashboard 保存入题库前如果存在风险提示，会要求用户确认。

当前限制：

- 这不是 OCR 准确率提升，也不会恢复已经漏识别的双栏选项。
- 检测基于文本启发式规则，可能漏报或误报。
- 后端仍允许保存，最终是否入库由用户核对后决定。

影响：

- 后续 smoke 应重点观察选择题选项缺失时是否出现风险提示，以及保存前确认是否有效。
- 如果要根治双栏选项漏识别，需要单独评估 OCR boxes 重排、二次裁剪 OCR、双栏切分或本地 OCR provider。

## 0.10 重复 smoke 图片已可复用，但不是完整历史记录能力

第二十五轮已修复同一用户重复上传同一张 smoke 图片时 `Asset already exists` 阻断流程的问题。当前重复上传会复用已有 asset，并允许继续创建新的 Draft，用于反复测试 OCR/LLM 效果。

当前限制：

- 这只是 smoke 阶段的重复素材复用，不等于完整历史记录能力。
- 历史记录暂不能重新编辑旧素材，也不能从历史记录直接重开完整处理流程。
- 题库删除功能尚未实现；如果 smoke 中产生错误题，当前不能通过题库 UI 删除。
- `SourceAsset.sha256` 当前仍是全局唯一；虽然 `SourceAsset` 有 `user_id`，但不同用户上传完全相同文件时仍需要后续单独设计 asset user isolation 和迁移。

影响：

- 用户可以用同一张本地 smoke 图片多次创建 Draft 做 OCR/LLM 对比。
- 错误题清理和历史记录重做应单独排期，不应和 smoke 复用混做。

## 0.9 Smoke 暴露 OCR/LLM 保真风险

第二十四轮根据本地 3 张 smoke 图片的人工观察，确认当前最优先问题是定位 OCR 与 LLM 哪一层引入错误，而不是立即切换 OCR 引擎。

已观察到的风险：

- 填空题公式可能被误改，例如 `m^2y + 6` 被整理成不同表达式。
- 选择题多列选项可能丢失，例如 A/B/C/D 只保留 A/B。
- 椭圆综合题可能被 LLM 按常见题型改写命题，例如焦点编号、线段名和证明表达式被替换。

第二十四轮已做的缓解：

- Draft detail 增加 `recognition_debug`，可查看 OCR 原文和 LLM 清洗文本。
- Dashboard 结果区增加折叠的“识别调试信息”。
- LLM prompt 改为保真整理模式，明确禁止猜题、补题、改题意、删除选项或改写数学表达式。

当前限制：

- 本轮不保证 OCR 准确率立刻提升。
- 如果 OCR 原文已经错误，LLM 保真整理无法可靠恢复原图内容。
- 如果 OCR 原文正确但 LLM 仍改错，需要继续收紧 LLM 输出 contract 或增加更严格的后处理校验。
- 仍需重新跑 3 张 smoke 图片，逐题比较原图、OCR 原文、LLM 清洗文本和当前草稿。

影响：

- 后续接入本地 OCR 前，应先用 `recognition_debug` 判断错误来源。
- 用户保存入题库前应优先查看调试信息，尤其是公式、选项、焦点编号和证明命题。

## 0.8 MVP smoke 样例覆盖仍有限

第二十三轮已收口 MVP 使用闭环和本地 smoke 样例说明，但这仍是手动 smoke，不是生产级验收矩阵。

当前限制：

- 3 张 smoke 样例来自本地 PDF 截图，不覆盖真实拍照噪声、阴影、倾斜、手写批注、低清晰度或复杂图形。
- 真实用户样本仍不足，后续应根据实际使用中的 bug 小步修复。
- Paper Preview 已通过 authenticated `POST /api/v1/papers/{paper_id}/pdf` 支持服务端 PDF 导出，backend 使用内部 Gotenberg 生成 PDF；浏览器 print CSS 仍保留。
- DOCX 导出仍未实现，服务端 PDF 也不等同于正式排版引擎级自动分页。
- 当前 OCR 默认仍依赖 `baidu`，本地 OCR 尚未接入。

影响：

- 手动 smoke 通过只能说明 MVP 演示链路可走通，不能说明 OCR 质量已覆盖真实场景。
- 浏览器打印仍依赖用户浏览器和系统打印设置；服务端 PDF 的 authenticated business-level 路径仍需纳入发布验收。

## 0.7 OCR 评估指标仍是文本级，真实评估集尚未建立

第二十二轮已建立 OCR eval case、prediction 和离线评估指标基础。

当前限制：

- 指标只覆盖文本级 exact match、归一化匹配、相似度、长度差和关键术语召回。
- 不能准确评估数学公式语义等价。
- 不能评估几何图形结构、辅助线、坐标系或图中文字位置关系。
- 不能评估版面结构、分栏、表格或选项排版。
- 尚未建立真实大规模高中数学题图片评估集。

影响：

- 后续比较 baidu / rapidocr / paddleocr / pix2text 时，不能只看自动指标，还需要人工抽检。
- 真实评估图片应放在本地或对象存储，不应把大图片提交进 Git。

## 0.6 本地 OCR 尚未接入，百度 OCR 成本问题仍未解决

第二十一轮已完成 Draft OCR Provider 抽象：

- Draft recognize 通过 `OCRService` 调用 OCR provider。
- 当前默认 provider 仍为 `baidu`。
- 现有百度 OCR 仅被封装为 `BaiduOcrProvider`，识别逻辑和文本处理口径未改变。
- `OCR_FALLBACK_PROVIDER` 仅预留，当前未启用 fallback。

当前限制：

- 尚未接入 RapidOCR、PaddleOCR、Pix2Text 或其他本地 OCR。
- 百度 OCR 仍是当前实际 Draft OCR provider，供应商成本和可用性风险仍存在。
- 已建立 OCR 文本级离线评估基础，但尚未建立真实图片评估集、资源占用评估或 fallback 策略。

影响：

- 本轮不能宣称已经降低 OCR 成本。
- 下一轮应优先接入一个本地 provider 并使用评估结构离线比较，或继续收集真实图片样例对比识别质量、耗时和服务器资源占用。

## 0.5 Draft LLM 空响应仍需真实复杂题复现

第二十轮人工验收发现，复杂数学题 Draft 识别链路可能出现 DeepSeek empty content：

- Baidu OCR 成功。
- LLM 返回空 content 或异常响应结构。
- 后端 fallback 到 OCR 原文，`draft_ready + partial_success=True`。
- 前端会提示“智能整理服务返回了空数据”，公式可能因未被 LLM 标准化而渲染异常。

第二十点五轮已补充安全诊断日志：

- 记录 response 类型、id、model、choices 数、finish_reason、message role、content 长度和截断预览。
- 记录 refusal、reasoning_content、tool_calls、usage token、输入长度、配置模型、timeout 和截断后的 raw response preview。
- empty content 的错误 detail 会包含 `choices_count`、`finish_reason`、`content_len`、`completion_tokens`。

第二十点六轮已按 DeepSeek 官方文档调整 Draft LLM 调用：

- 默认通过 `extra_body={"thinking": {"type": "disabled"}}` 关闭 thinking，可用 `LLM_THINKING_MODE` 配置。
- 启用 `response_format={"type": "json_object"}`。
- Prompt 明确只返回 JSON，并提供 JSON 输出样例。
- 不使用 `reasoning_effort="low"`，因为 DeepSeek 文档说明 low/medium 会映射为 high。
- `finish_reason=length` 且 content 为空时，错误 detail 改为 `deepseek_length_exhausted_empty_content`。

当前限制：

- 该问题尚未通过真实复杂椭圆题在线复现闭环。
- 本轮未改变 fallback 状态机，也未禁止 partial_success Draft 保存入库。
- 本轮不表示已彻底解决所有 DeepSeek 空响应；仍需真实复杂题复测。

影响：

- 复杂 OCR 文本仍可能触发 LLM fallback；用户保存前应关注 partial_success warning。
- 后续应使用复杂椭圆题重新验收，依据新增日志判断关闭 thinking 和 JSON Output 后是否仍存在 token 截断、内容过滤、空 choices、字段位置变化或第三方异常体。

## 0. 组卷 MVP 后续能力仍未完成

第十七轮新增后端最小手动组卷能力。第十八轮新增前端组卷入口 MVP，支持从题库勾选题目、创建试卷、查看试卷列表和查看试卷详情。

第二十轮新增学生版 A4 作业预览 MVP；后续已增加服务端 PDF 导出，由后端通过内部 Gotenberg 生成文件。该能力仍不是正式排版引擎。

当前明确暂不支持：

- 智能组卷算法。
- Word 导出。
- 自动分页；长题可能撑开 A4 视觉容器。
- 拖拽排序。
- 分值编辑。
- 复杂试卷排版。
- 打印样式优化。
- 按知识点、难度或分值自动配比。

补充边界：

- 题型快照为空时，预览统一归入 `unknown / 未分类`。
- 当前答题区只支持无答题区或每题后固定 50mm 纯留白，不支持逐题自定义高度或复杂答题卡。
- 当前预览不包含答案或解析，且学生版后端响应层面不返回答案解析快照。

影响：

- 当前组卷前端只适合 MVP 验收，不应表述为完整组卷系统。
- 后续如果补导出、智能组卷、拖拽排序或分值编辑，应继续保持小步推进，并避免影响 Draft flow、legacy recognize 和题库保存逻辑。

## 1. LLM 难度评估是增强元数据，不是绝对标准

第十九轮新增 LLM 题型与五星难度元数据；性能收口后，Draft recognize 主链路只强制等待 OCR、`corrected_text` 和知识点标签，题型与难度在 save-to-bank 后通过后台任务补全到 Question。

当前限制：

- LLM 难度评分是估计值，不是严格教研标准或绝对难度。
- 历史题目可能没有 `question_type`、`difficulty_level`、`difficulty_label`、`difficulty_confidence` 或 `difficulty_reason`。
- 用户后续编辑题目内容后，题型和难度不会自动重新评估。
- 当前不支持按难度排序、按知识点排序、难度筛选或智能组卷。
- 后台任务依赖当前后端进程，服务重启可能丢失正在执行的元数据评估任务。
- 当前不做自动轮询或 WebSocket，前端需要刷新题库后看到后台更新结果。
- PaperItem 创建时如果 Question 元数据尚未 ready，题型和难度快照可能为空。
- `difficulty` 缺失或非法时，后端会保留 `corrected_text` 主流程并让难度字段为空或将元数据评估标记为失败。

影响：

- 前端和后续组卷逻辑必须把难度字段视为可空。
- 如后续要用于正式组卷策略，应增加人工校验、手动重新评估、版本化策略或真正任务队列。

## 2. 前端中文乱码

当前文档和部分前端显示曾出现中文乱码问题。下一阶段应优先处理编码与展示链路，避免继续扩大文案维护成本。

影响：

- 影响人工验收和后续维护判断。
- 可能掩盖真实交互文案问题。

## 3. Dashboard Draft 接入已阶段性收口但仍非生产完成态

主链路已决策采用渐进式迁移。第十一轮补充确认，当前 `Dashboard.vue` 上传主路径已初步接入 Draft 流水线，并接受为新的前端主路径基线。

当前 `Dashboard.vue` 上传按钮实际调用 Draft 相关接口：

- `POST /api/v1/assets`
- `POST /api/v1/drafts`
- `POST /api/v1/drafts/{draft_id}/recognize`
- `POST /api/v1/drafts/{draft_id}/save-to-bank`

同时，`Dashboard.vue` 中仍保留 `runLegacyRecognition()` 对 `POST /api/v1/recognize` 的调用，但当前上传按钮未引用该函数。`POST /api/v1/recognize` 不删除、不重构，保留为 legacy / 兼容入口。

已阶段性收口：

- API smoke 文档已补充。
- Draft 后端异常契约已阶段性收口：缺失 asset/draft 返回 `404`，非图片 asset recognize 返回 `400`，状态冲突和重复保存返回 `409`。
- Dashboard UI 状态已阶段性收口：上传、创建草稿、识别、保存有阶段提示，`partial_success` 以 warning 展示，常见错误码有可理解提示。
- legacy recognize 引用审计已完成，当前 Dashboard 主上传流程不调用 legacy 入口。
- 两个 smoke 文档已明确主次：`API_SMOKE_DRAFT_FLOW.md` 是当前推荐入口，`API_SMOKE_DRAFT_PIPELINE.md` 是脚本化 smoke 补充文档。

仍保留风险：

- Draft 前端接入尚未达到完整生产级完成。
- `saved_to_bank` 状态重复保存当前返回 `409`，尚未做成返回既有保存结果的幂等接口。
- `/api/v1/recognize` 仍需作为 legacy / 兼容入口保留。
- 两个 smoke 文档仍并存，后续修改 Draft 主链路或脚本参数时需要同步检查主文档和脚本文档，避免再次漂移。
- 不做 OCR/LLM provider 抽象、异步队列、批量 PDF、多页 draft 管理。

## 4. legacy recognize 仍需后续退场

第十五轮已完成 legacy recognize 引用审计与最小标注。当前 `runLegacyRecognition()` 和 `POST /api/v1/recognize` 仍保留为 legacy / 兼容入口，不被 Dashboard 主上传流程调用。

影响：

- 新开发仍可能误用 legacy 入口。
- 后续应在测试保护和兼容影响明确后，小步执行退场策略。
- 本轮不删除 legacy 入口，不改变后端业务行为。

## 5. mock/legacy 文件需要清理

项目中仍存在历史 mock、legacy 或过渡文件。它们不一定阻断当前启动和验证，但会增加后续判断成本。

影响：

- 新开发容易误用历史入口。
- 清理应小步进行，避免演变成大重构。

## 6. 后端测试稳定性仍需持续关注

第七轮后端验证已通过：

- `python -m compileall app` 通过。
- `python -m unittest discover tests` 通过，`Ran 38 tests OK`。

但当前测试仍依赖已正确安装 `backend/requirements.txt` 的 Python 环境，后续仍需关注环境一致性和测试隔离。

影响：

- 裸 Python 环境或依赖不完整时会出现非业务失败。
- 下一阶段应优先提升测试稳定性，而不是扩大功能面。

## 7. 真实第三方失败场景尚未系统化在线验证

当前不能声称错误密钥、第三方超时、第三方限流、异常响应结构、网络抖动等场景都已逐项在线验证。

影响：

- 可以记录本地失败分支语义，但不能等同于真实第三方异常验收完成。
- 对外交付说明必须区分“主链路可验证”和“生产级异常覆盖”。

## 8. 当前状态不是生产可用

当前项目状态是“可启动、可验证、可继续开发”。不要把它表述为生产可用。

影响：

- 后续文档、验收、汇报需要保持该边界。
- 下一阶段不要新增规划之外的大模块，也不要做大重构。
