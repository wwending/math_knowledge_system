# STATUS

## 2026-08-05 v0.1 单机部署候选栈

当前 `v0.1 Release Candidate` 已增加可重复的单机容器部署能力，不改变 OCR、LLM、Draft、题库或组卷业务逻辑。

- Nginx Web 容器提供 Vue dist，并反向代理 `/api/`、`/static/`、`/healthz`；FastAPI 的 `8000` 不映射到宿主机。
- FastAPI 使用 Python 3.11 slim、非 root 用户和单 Uvicorn worker；SQLite、上传文件与 PDF 临时目录统一持久化到宿主机 `/srv/math-knowledge/data/`。
- 部署脚本在启动前显式执行 Alembic migration，不允许应用启动时自动修改 schema。
- 备份脚本通过 SQLite Backup API 生成一致快照，同时保存上传文件、部署 commit 和不含值的环境字段清单。
- 前端开发默认地址仍为 `http://127.0.0.1:8000`；生产默认改为同源 `/api/v1` 与 `/static`，仍支持 `VITE_API_BASE_URL` 覆盖。
- 本地后端 125 项 pytest、125 项 unittest、前端 Stage 3 契约和生产构建通过；生产 dist 不包含 localhost API 地址。
- 当前 Windows 环境没有 Docker 命令，Compose 解析和 Linux 镜像构建已加入 GitHub Actions，仍需等待 PR CI 与目标服务器 smoke 验证。

## 2026-08-05 v0.1 MVP 交付收尾

当前项目状态已收口为 `v0.1 Release Candidate`。本轮目标是建立可重复的自动门禁与人工发布验收标准，完成后停止无边界开发，只根据真实客户需求迭代。

生产路线冻结：

- 主流程固定为“上传 → 百度 OCR → LLM 清洗 → Draft 确认 → 保存题库 → 组卷 → Paper Preview”。
- 生产默认固定为 `OCR_PROVIDER=baidu`，LLM 使用 DeepSeek 或兼容 OpenAI API 的服务。
- RapidOCR 只保留为历史实验代码，不属于 v0.1 交付范围；除非客户需求或成本数据要求重新评估，否则不再继续迁移或比较 RapidOCR、PaddleOCR、Pix2Text。
- 不修改 Draft 主流程，不新增题库删除/回收站、Draft 历史恢复、私有/共享/群组题库、服务端 PDF/DOCX 导出，不做大范围 UI 重构或无关依赖升级。

本轮交付内容：

- 新增 `.github/workflows/ci.yml`，在 main push、面向 main 的 PR 和手工触发时分别运行后端与前端 job。
- 后端 CI 使用 Python 3.11，安装正式依赖与 pytest，执行 `python -m compileall app` 和 `python -m pytest`；测试环境密钥为空或明确为 CI 占位值，不调用真实外部 API。
- 前端 CI 使用 Node.js 22 LTS、合法 lockfile 和 `npm ci`，执行 `npm run test:stage3-contract` 与 `npm run build`。
- 新增 `docs/MVP_RELEASE_CHECKLIST.md`，覆盖环境、启动、自动检查、至少 5 题真实 smoke、失败路径、保护机制、数据隔离、组卷快照、打印与发布签字。
- README 已改为 v0.1 RC 交付口径，并明确真实 smoke 完成前不能视为正式发布。

修改前基线（2026-08-05 实跑）：

- 后端解释器：`D:\math_knowledge_system\backend\venv\Scripts\python.exe`，Python 3.11.7。
- `python -m compileall app` 通过。
- `python -m pytest` 通过，`125 passed`，有 1 个 `.pytest_cache` 权限 warning。
- `python -m unittest discover tests` 通过，`Ran 125 tests OK`。
- `npm run test:stage3-contract` 通过，3 个契约脚本全部通过。
- `npm run build` 通过，仍有 Vite chunk size warning。

修改后验证（2026-08-05 实跑，百度/DeepSeek Key 显式为空）：

- `python -m compileall app` 通过。
- `python -m pytest` 通过，`125 passed`，有 1 个 `.pytest_cache` 权限 warning。
- `python -m unittest discover tests` 通过，`Ran 125 tests OK`。
- `npm run test:stage3-contract` 通过，3 个契约脚本全部通过。
- `npm run build` 通过，1601 个模块完成转换，仍有 Vite chunk size warning。
- 测试日志明确显示百度 OCR 与 DeepSeek 凭据未配置，全部自动测试仍通过，证明本轮自动门禁不依赖真实第三方调用。

发布门禁：

- 自动检查通过后仍需发布负责人按 `docs/MVP_RELEASE_CHECKLIST.md` 人工执行至少 5 张真实数学题图片的百度 OCR + LLM smoke。
- OCR/LLM 失败、风险提示与二次确认、重复保存保护、用户数据隔离、组卷快照、Paper Preview 浏览器打印/另存 PDF 均需人工确认。
- 人工 smoke 未完成前不创建 `v0.1.0` 标签，不把当前状态表述为正式发布或生产可用。

## 2026-06-17 第二十八点七轮 RapidOCR 3.8.4 返回结构适配

当前 MVP smoke 阶段已修复 `RapidOcrProvider` 对 RapidOCR 3.8.4 返回对象的解析兼容问题，`unsupported result format` 不再误伤当前版本。

本轮结果：

- 项目 venv 使用 `D:\math_knowledge_system\backend\venv\Scripts\python.exe`。
- 项目 venv 中 `rapidocr` 已升级到 `3.8.4`，`onnxruntime 1.27.0` 已安装。
- 探测确认 RapidOCR 3.8.4 返回 `rapidocr.utils.output.RapidOCROutput`。
- 关键字段为 `txts`、`boxes`、`scores`，其中 `txts` 是 tuple，`boxes` 是 numpy ndarray，并提供 `to_json()`。
- 解析器已优先支持 `txts/texts`，避免对 numpy/array-like `boxes` 做布尔判断，并增加 `to_dict()` / `model_dump()` / `to_json()` 兜底解析。
- 空 `txts` 视为合法空文本，不再误报 unsupported；真正 unsupported 时错误信息包含类型、属性摘要和截断 repr。
- 新增 `backend/scripts/__init__.py` 与 `backend/scripts/evaluation/__init__.py`，避免第三方 `scripts` 包遮蔽项目脚本导致 pytest 收集失败。
- RapidOCR-only smoke 对 3 张图片均成功返回文本。
- 完整 baidu vs rapidocr A/B 已重跑，双方均 3 张成功。

Smoke 摘要：

- RapidOCR-only：3/3 成功，耗时约 2029-2811 ms，文本长度分别为 43、87、95；第二张触发 `choice_options_incomplete`。
- 完整 A/B 中 Baidu：3/3 成功，耗时约 930-1430 ms，文本长度分别为 74、326、291；3 张均触发 `choice_options_incomplete`。
- 完整 A/B 中 RapidOCR：3/3 成功，耗时约 2134-2824 ms，文本长度分别为 43、87、95；第二张触发 `choice_options_incomplete`。

OCR 当前状态：

- RapidOCR 已完成 Provider 接入和真实 smoke，但当前数学题图识别完整性明显弱于百度 OCR。
- 当前默认 OCR 继续使用 Baidu。

当前边界：

- RapidOCR 已能完成本地 OCR smoke，但质量仍需人工判断。
- RapidOCR 文本长度明显短于 Baidu，可能存在漏题、漏选项或版面识别不足。
- 本轮不修改默认 `OCR_PROVIDER`，默认仍为 `baidu`。
- 本轮不修改 Draft recognize API、不修改前端、不修改数据库模型、不修改 BaiduOcrProvider、不修改 legacy `/api/v1/recognize`。
- 本地完整报告和 JSON 位于 `backend/reports/ocr_ab/`，该目录已被 `.gitignore` 忽略，不作为提交内容。

验证结果：

- `cd backend && python -m pytest tests/test_ocr_provider.py` 通过，`15 passed`，仍有 `.pytest_cache` 权限 warning。
- `cd backend && python -m pytest tests/test_ocr_ab_evaluation.py` 通过，`5 passed`，仍有 `.pytest_cache` 权限 warning。
- `cd backend && python -m pytest` 通过，`125 passed`，仍有 `.pytest_cache` 权限 warning。
- `cd backend && python -m compileall app` 通过。
- `cd backend && python -m unittest discover tests` 通过，`Ran 125 tests OK`。
- `cd backend && python scripts/evaluation/compare_ocr_providers.py --input "D:\math_knowledge_system\data\manual_smoke\ocr_images" --providers rapidocr --output reports/ocr_ab/rapidocr_smoke_after_parser_fix.md --json-output reports/ocr_ab/rapidocr_smoke_after_parser_fix.json` 通过。
- `cd backend && python scripts/evaluation/compare_ocr_providers.py --input "D:\math_knowledge_system\data\manual_smoke\ocr_images" --providers baidu,rapidocr --output reports/ocr_ab/ocr_ab_first_smoke_parser_fixed.md --json-output reports/ocr_ab/ocr_ab_first_smoke_parser_fixed.json` 通过。

## 2026-06-17 第二十八点五轮 OCR A/B first smoke 实跑

当前 MVP smoke 阶段已使用本地 3 张 smoke 图片运行 OCR Provider A/B 评测，输入目录明确为 `D:\math_knowledge_system\data\manual_smoke\ocr_images`。

本轮结果：

- 评测命令从 `backend/` 目录运行，providers 为 `baidu,rapidocr`。
- 本轮未带 `--with-llm`，未调用 LLM。
- Baidu OCR 对 3 张图片均成功返回文本。
- 3 张图片均触发 `choice_options_incomplete` 风险提示。
- RapidOCR 包已安装，但运行依赖 `onnxruntime` 缺失，3 张图片均失败并记录 `onnxruntime is not installed.`。
- 本地完整报告和 JSON 已生成在 `backend/reports/ocr_ab/`，该目录已被 `.gitignore` 忽略，不作为提交内容。
- 新增 `docs/OCR_AB_FIRST_SMOKE.md` 作为提交用摘要，不粘贴完整 OCR 原文。

当前边界：

- 本轮不能形成 RapidOCR 识别质量结论，只确认失败原因和脚本容错行为。
- 本轮不修改默认 `OCR_PROVIDER`，默认仍为 `baidu`。
- 本轮不修改 Draft recognize API、不修改前端、不修改数据库模型、不修改 legacy `/api/v1/recognize`。

验证结果：

- `cd backend && python scripts/evaluation/compare_ocr_providers.py --input "D:\math_knowledge_system\data\manual_smoke\ocr_images" --providers baidu,rapidocr --output reports/ocr_ab/ocr_ab_first_smoke.md --json-output reports/ocr_ab/ocr_ab_first_smoke.json` 通过。
- `cd backend && python -m pip show rapidocr` 显示已安装 `rapidocr 3.8.4`。
- `cd backend && python -m pip show onnxruntime` 显示未安装。

## 2026-06-17 第二十八轮 OCR Provider A/B smoke 评测机制

当前 MVP smoke 阶段新增 OCR Provider A/B 手工评测入口，用于对比 `baidu` 和 `rapidocr` 在同一批题图上的 OCR 文本、耗时、失败信息和识别质量风险。

新增能力：

- 新增 `backend/scripts/evaluation/compare_ocr_providers.py`，支持单图或目录输入。
- `--providers` 默认 `baidu,rapidocr`，也支持只跑单个 provider。
- `--output` 输出 Markdown 报告，`--json-output` 可额外输出结构化 JSON。
- 默认只跑 OCR 和 `quality_warnings`；只有显式 `--with-llm` 才调用现有 LLM 清洗服务。
- 单个 provider、单张图片或 LLM 调用失败只记录失败信息，不中断整批评测。
- `OCRService.recognize()` 增加可选 `provider_name` 单次覆盖参数，默认仍读取 `OCR_PROVIDER`，默认 provider 仍是 `baidu`。
- `backend/reports/ocr_ab/` 已加入 `.gitignore`，真实评测报告默认不入库。

当前边界：

- 本轮不修改默认 `OCR_PROVIDER`，不把 RapidOCR 设为默认。
- 本轮不修改 Draft recognize API、不修改前端、不修改数据库模型。
- 本轮不优化 OCR 精度，不重构 Draft 流程，不强制安装 RapidOCR。
- 自动化测试使用 fake OCR/LLM，不调用真实百度 OCR、RapidOCR 模型、DeepSeek API、网络或 API key。

验证结果：

- `cd backend && python -m unittest tests.test_ocr_provider.OcrProviderTests.test_ocr_service_can_override_provider_per_recognize_call` 先按预期失败，实现后通过。
- `cd backend && python -m unittest tests.test_ocr_ab_evaluation` 先按预期失败，实现后通过，`Ran 5 tests OK`。
- `cd backend && python -m compileall app` 通过。
- `cd backend && python -m py_compile scripts/evaluation/compare_ocr_providers.py` 通过。
- `cd backend && python -m unittest tests.test_ocr_provider tests.test_ocr_ab_evaluation` 通过，`Ran 18 tests OK`。
- `cd backend && python -m unittest discover tests` 首次 120 秒超时未取得最终结论；提高超时后通过，`Ran 123 tests OK`。

## 2026-06-16 第二十七点五轮 pytest 根目录遗留测试收口

当前 MVP smoke 阶段已清理 pytest 根目录遗留收集问题，后端全量 pytest 可直接运行。

新增/调整：

- 将根目录历史手工脚本 `backend/test_deepseek.py` 移出 pytest 自动收集范围。
- 新位置为 `backend/scripts/manual/deepseek_manual_check.py`，并标注为手工 DeepSeek 检查脚本，不属于自动测试套件。
- 手工脚本改用当前 `app.services.llm.nlp_service.analyze()` 接口，不恢复已废弃的 `correct_text`。
- 自动化测试仍集中在 `backend/tests/`，不引入真实 DeepSeek API 调用到测试。

验证结果：

- `cd backend && python -m compileall app` 通过。
- `cd backend && python -m unittest discover tests` 通过，`Ran 117 tests OK`。
- `cd backend && python -m pytest tests` 通过，`117 passed`，仍有 `.pytest_cache` 权限 warning。
- `cd backend && python -m pytest` 通过，`117 passed`，仍有 `.pytest_cache` 权限 warning。
- `cd backend && python -m py_compile scripts/manual/deepseek_manual_check.py` 通过。

## 2026-06-16 第二十七轮 RapidOCR 本地 OCR Provider 实验接入

当前 MVP smoke 阶段新增 RapidOCR 本地 OCR Provider 实验接入，用于验证 Draft OCR Provider 可配置切换能力。

新增能力：

- `OCR_PROVIDER` 支持 `baidu` 和 `rapidocr`，默认仍为 `baidu`。
- 新增 `RapidOcrProvider`，通过延迟导入 `rapidocr.RapidOCR` 避免未安装 rapidocr 时影响默认 baidu 流程。
- RapidOCR 引擎在 provider 内懒加载并缓存，`OCRService` 也按 provider 名称缓存实例，避免每次识别重复初始化。
- RapidOCR 返回结果增加最小兼容解析，覆盖对象 `txts/texts`、`boxes/scores`、旧式 `(boxes, txts, scores)` 和逐行 tuple/dict 结构。
- `backend/.env.example` 增加 `OCR_PROVIDER=baidu` 与 `# OCR_PROVIDER=rapidocr` 示例；`requirements.txt` 仅注释 RapidOCR 为可选依赖。

当前边界：

- 百度 OCR 仍是稳定默认 provider，本轮不替换百度 OCR。
- 本轮不修改 Draft recognize API 请求/响应结构、不改前端、不改数据库模型。
- RapidOCR 当前只是本地文本 OCR 实验 provider，真实高中数学题、公式和双栏选项效果需要后续用 smoke 图片实测对比。

验证结果：

- `cd backend && python -m unittest tests.test_ocr_provider` 通过，`Ran 12 tests OK`。
- `cd backend && python -m compileall app` 通过。
- `cd backend && python -m unittest discover tests` 通过，`Ran 117 tests OK`。
- `cd backend && python -m pytest tests` 通过，`117 passed`，仍有 `.pytest_cache` 权限 warning。
- `cd backend && python -m pytest` 在第二十七点五轮已收口通过。

## 2026-06-16 第二十六轮识别结果风险提示与保存前校验

当前 MVP smoke 阶段新增识别质量风险提示，用于避免疑似残缺题无感保存入题库。

新增能力：

- Draft detail / recognize / save-to-bank 响应新增 `quality_warnings`，按当前识别文本、原始 OCR 文本和 LLM 清洗文本动态计算，不新增数据库字段。
- 新增选择题风险提示：疑似选择题选项不足 4 个时返回 `choice_options_incomplete`。
- 新增选择题标签断档提示：如 A/C 缺 B 或 A/B/D 缺 C 时返回 `choice_options_sequence_gap`。
- 新增保守文本质量提示：识别文本过短返回 `recognized_text_too_short`，LLM 清洗后明显短于 OCR 原文返回 `ocr_llm_text_changed_substantially`。
- Dashboard 结果区展示“识别风险提示”，用户仍可编辑草稿。
- Dashboard 保存入题库前如果存在 `quality_warnings`，弹出确认框；用户可取消返回编辑，也可确认继续保存。

当前边界：

- 本轮不解决 OCR 双栏选项漏识别本身，只提示风险。
- 本轮不接入 RapidOCR、PaddleOCR、Pix2Text，不改 OCRService provider、BaiduOcrProvider 或 LLM prompt。
- 本轮不阻止后端 save-to-bank，不改变 API 兼容性，不做数据库迁移。
- 本轮不修改 legacy `/api/v1/recognize`、PaperRenderModel 或 PaperPreview 打印逻辑。

验证结果：

- `cd backend && python -m compileall app` 通过。
- `cd backend && python -m unittest tests.test_recognition_quality` 通过，`Ran 6 tests OK`。
- `cd backend && python -m unittest tests.test_draft_pipeline` 通过，`Ran 17 tests OK`。
- `cd backend && python -m unittest discover tests` 通过，`Ran 109 tests OK`。
- `cd frontend && npm run test:stage3-contract` 通过。
- `cd frontend && npm run build` 通过，仍有 Vite chunk size warning。

## 2026-06-16 第二十五轮重复素材上传支持 smoke 复用

当前 MVP smoke 阶段已修复同一用户重复上传同一张本地 smoke 图片时被 `Asset already exists` 卡死的问题。

新增能力：

- `POST /api/v1/assets` 首次上传仍正常创建 `SourceAsset`。
- 同一用户重复上传相同图片时，后端不重复保存文件，不再作为阻塞性失败返回，而是复用已有 asset。
- 重复上传响应包含 `deduplicated=true`、`existing_asset_id` 和提示信息，前端可继续用该 asset 创建 Draft。
- Dashboard 收到复用响应时显示“素材已存在，已复用已有素材继续录入。”，并继续后续 Draft 创建和识别流程。
- 当前 `Draft.source_asset_id` 没有唯一约束，同一张 smoke 图片可以多次创建 Draft，用于反复测试 OCR/LLM 效果。

当前边界：

- 本轮保留 asset 去重，不重复保存同一份图片文件。
- 本轮不做历史记录重构，不支持历史记录重新编辑旧素材。
- 本轮不做题库删除功能。
- 本轮不修改 OCR provider、BaiduOcrProvider、LLM prompt、legacy `/api/v1/recognize`、PaperRenderModel 或 PaperPreview 打印逻辑。
- `SourceAsset.sha256` 当前仍是全局唯一；如果未来需要严格支持不同用户上传相同文件并各自拥有独立 asset，需要单独设计 asset user isolation 和迁移。

验证结果：

- `cd backend && python -m unittest tests.test_draft_pipeline.DraftPipelineTests.test_repeated_asset_upload_reuses_existing_asset_and_allows_new_draft` 先按预期失败，实现后通过。
- `cd frontend && npm run test:stage3-contract` 先按预期失败，实现后通过。
- `cd backend && python -m compileall app` 通过。
- `cd backend && python -m unittest discover tests` 通过，`Ran 103 tests OK`。
- `cd frontend && npm run test:auth-contract` 通过。
- `cd frontend && npm run test:stage3-contract` 通过。
- `cd frontend && npm run build` 通过，仍有 Vite chunk size warning。

## 2026-06-16 第二十四轮 OCR/LLM 保真与可回溯修复

当前项目针对 3 张本地 MVP smoke 样例暴露的 OCR/LLM 保真问题，优先收口“可回溯、可定位、禁止 LLM 猜题改题意”，而不是继续接入本地 OCR 或扩展导出能力。

新增能力：

- Draft detail / recognize / save-to-bank 响应新增可选 `recognition_debug`，包含 `ocr_provider`、`ocr_raw_text`、`llm_cleaned_text`、`ocr_error`、`llm_error`。
- `recognition_debug` 复用已有 `OCRRun`、`LLMRun`、`Draft.current_content` 字段，不新增数据库字段，不做迁移。
- Dashboard 题目录入结果区新增默认折叠的“识别调试信息”，展示“原始 OCR 文本”和“LLM 清洗文本”，便于人工比较原图、OCR 原文、LLM 清洗结果和当前草稿。
- Draft LLM prompt 调整为保真整理模式：禁止猜题、补题、改题意、替换变量/焦点编号/线段名、删除残缺选项或把一个数学表达式改成另一个表达式。
- 增加后端测试锁定 prompt 防篡改规则和 Draft detail 调试字段，前端契约测试锁定调试展示入口。

当前边界：

- 本轮不提升 OCR 准确率，不接入 RapidOCR、PaddleOCR、Pix2Text。
- 未修改 OCRService provider 选择逻辑、BaiduOcrProvider、legacy `/api/v1/recognize`、PaperRenderModel 或 PaperPreview 打印逻辑。
- 未新增数据库字段、迁移或 QuestionAsset 表。
- LLM prompt 约束只能降低篡改概率，仍需用 3 张 smoke 图片复测确认错误来源。

验证结果：

- `cd backend && python -m compileall app` 通过。
- `cd backend && python -m unittest tests.test_llm` 通过，`Ran 23 tests OK`。
- `cd backend && python -m unittest tests.test_draft_pipeline` 通过，`Ran 16 tests OK`。
- `cd backend && python -m unittest discover tests` 通过，`Ran 102 tests OK`。
- `cd frontend && npm run test:auth-contract` 通过。
- `cd frontend && npm run test:stage3-contract` 通过。
- `cd frontend && npm run build` 通过，仍有 Vite chunk size warning。

## 2026-06-16 第二十三轮 MVP 使用闭环与本地 smoke 样例收口

当前项目从 OCR 评估基础阶段转入 MVP 使用闭环收口：优先保证少量真实用户可以完成“上传图片 -> Draft 识别 -> 人工编辑 -> 保存题库 -> 创建试卷 -> 预览 -> 浏览器打印/另存 PDF”的本地演示链路。

新增能力和文档：

- 新增 `docs/DEMO_FLOW.md`，说明一次 MVP Demo 从启动前后端到浏览器打印/另存 PDF 的完整流程。
- 新增 `docs/MVP_SMOKE_CHECKLIST.md`，约定 3 张本地 PDF 截图 smoke 图片和人工检查项。
- `.gitignore` 已忽略 `data/manual_smoke/ocr_images/` 和 `data/manual_smoke/predictions/`，真实图片和本地预测记录不提交到 Git。
- `PaperPreview.vue` 新增最小“打印/导出 PDF”按钮，点击后调用 `window.print()`。
- `PaperPreview.vue` 新增最小 print CSS，打印时隐藏试卷列表、详情按钮、预览工具栏和不必要导航，保留 A4 预览内容。
- `frontend/tests/paper-mvp-contract.test.mjs` 增加打印入口契约检查。

当前边界：

- OCR Eval 暂停扩展，本轮不新增复杂评估集。
- 当前默认 OCR provider 仍为 `baidu`，本地 OCR 尚未接入。
- 当前 smoke 图片来自本地 PDF 截图，不覆盖真实拍照噪声、阴影、倾斜、手写批注或低清晰度场景。
- 当前导出方案为浏览器打印/另存为 PDF，服务端 PDF/DOCX 导出尚未实现。
- 未修改 Draft recognize 主流程，未修改 legacy `/api/v1/recognize`，未修改 OCRService provider 选择逻辑。
- 未修改 PaperRenderModel 核心数据结构，未做数据库迁移。

验证结果：

- `cd frontend && node ./tests/paper-mvp-contract.test.mjs` 先按预期失败，提示缺少浏览器打印导出、按钮文案和 print CSS；实现后通过，`Paper MVP frontend contract passed.`。
- `cd backend && python -m compileall app` 通过。
- `cd backend && python -m unittest discover tests` 通过，`Ran 102 tests OK`。
- `cd frontend && npm run build` 通过，仍有 Vite chunk size warning。

## 2026-06-16 第二十二轮 OCR 方案评估集与评估指标基础

当前项目在第二十一轮 Draft OCR Provider 抽象之后，新增 OCR 离线评估集和文本级评估指标基础，但不接入新 OCR 引擎，不调用真实 OCR API。

新增能力：

- 新增轻量 OCR eval case JSON 结构，记录 `case_id`、占位 `image_path`、人工 `expected_text`、类别、难度、关键术语和说明。
- 新增轻量 OCR prediction JSON 结构，记录 `case_id`、`provider`、`predicted_text`、`latency_ms` 和 `error`。
- 新增 `ocr_evaluation.py`，支持文本归一化、单条 prediction 评估、批量按 provider 汇总。
- 指标包括 exact match、normalized exact match、文本相似度、长度差、关键术语召回和错误标记。
- 新增 `docs/OCR_EVAL.md`，说明为什么先建立评估标准，再接入本地 OCR provider。

当前边界：

- OCR Provider 已抽象，OCR Eval 基础已建立，本地 OCR 尚未接入。
- 当前默认 OCR provider 仍为 `baidu`。
- 未修改 Draft recognize 主流程，未修改 legacy `/api/v1/recognize`。
- 未接入 RapidOCR、PaddleOCR、Pix2Text 或云 fallback。
- 当前评估只是文本级初步评估，不覆盖数学公式语义、几何图结构或版面理解。
- 尚未建立真实大规模高中数学题图片评估集。

验证结果：

- `cd backend && python -m compileall app` 通过。
- `cd backend && python -m unittest tests.test_ocr_evaluation` 通过，`Ran 6 tests OK`。
- `cd backend && python -m unittest discover tests` 通过，`Ran 102 tests OK`。

## 2026-06-06 第二十一轮 OCR Provider 抽象与部署成本控制基础

当前项目完成 Draft recognize OCR Provider 抽象基础，但不替换 OCR 引擎，不改变 legacy `/api/v1/recognize`。

新增能力：

- 新增内部统一 `OCRResult` 和 `OcrProvider` 接口，字段包含 text、provider、confidence、boxes、raw_response_summary、latency_ms、error 等。
- 新增 `BaiduOcrProvider`，只封装既有 `ocr_engine.py` 行为，不改变百度 OCR 识别逻辑或文本处理口径。
- 新增 `OCRService`，通过 `OCR_PROVIDER` 选择 provider；当前实际支持 `baidu`。
- `OCR_PROVIDER` 默认 `baidu`，`OCR_FALLBACK_PROVIDER` 已预留但本轮未启用 fallback。
- Draft recognize 改为调用 `OCRService`，OCRRun 记录实际 provider，性能日志增加 `ocr_provider`。
- 未知 OCR provider 会明确返回 `unsupported_provider` / `unsupported_ocr_provider:<provider>`。

当前边界：

- 本轮未接入 RapidOCR、PaddleOCR、Pix2Text 或任何本地 OCR。
- 本轮未解决百度 OCR 成本问题，只为后续切换和 fallback 打基础。
- 本轮未修改数据库模型、Alembic 迁移、PaperRenderModel、PaperPreview、前端或 legacy `/api/v1/recognize`。
- 自动化测试均使用 fake / mock，不真实调用百度 OCR API。

验证结果：

- `cd backend && python -m unittest tests.test_ocr_provider` 通过，`Ran 4 tests OK`。
- `cd backend && python -m unittest tests.test_draft_pipeline.DraftPipelineTests.test_draft_pipeline_recognize_is_lightweight_and_save_to_bank_sets_metadata_pending` 通过。
- `cd backend && python -m compileall app` 通过。
- `cd backend && python -m unittest discover tests` 通过，`Ran 96 tests OK`。

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
