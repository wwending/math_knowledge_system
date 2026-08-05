# WORKLOG

说明：本文件按时间倒序记录每轮工作。较早轮次中的“当前主链路”等表述保留为当时历史事实；当前状态以 `docs/STATUS.md` 最新 checkpoint 和较新的 DECISIONS 为准。

### PaddleOCR heavy 本地实验

- 在独立环境 `backend/.venv_paddle_ocr_test/` 中安装并验证：
  - `paddleocr`
  - `paddlepaddle 3.3.1`
- `paddle.utils.run_check()` 验证通过，PaddlePaddle 可在当前 Windows CPU 环境运行。
- PaddleOCR 成功加载以下模型：
  - `PP-LCNet_x1_0_doc_ori`
  - `UVDoc`
  - `PP-LCNet_x1_0_textline_ori`
  - `PP-OCRv6_medium_det`
  - `PP-OCRv6_medium_rec`
- 在第一张 smoke 图片进入文本检测推理时失败，错误为：

```text
NotImplementedError:
ConvertPirAttribute2RuntimeAttribute not support
[pir::ArrayAttribute<pir::DoubleAttribute>]
```

- 尝试设置以下环境变量后问题仍然存在：

```text
FLAGS_use_mkldnn=0
FLAGS_enable_pir_api=0
```

- 日志仍显示执行路径进入 oneDNN，因此判断为当前 `PaddleOCR / PaddlePaddle / Windows CPU` 组合的推理兼容问题。
- 本轮没有取得 PaddleOCR OCR 文本结果，无法评价其识别精度。
- 未将 PaddleOCR 接入正式 Provider，也未修改正式后端环境和默认 `OCR_PROVIDER=baidu`。

PaddleOCR heavy 在当前 Windows CPU 实验环境中模型能够初始化，但 PP-OCRv6 medium 推理阶段存在 oneDNN/PIR 兼容问题，因此本轮无法评价识别质量。该方案暂缓接入，不代表 PaddleOCR 本身识别效果差。

## 2026-06-17 第二十八点七轮：RapidOCR 3.8.4 返回结构适配

目标：

- 探测 RapidOCR 3.8.4 的真实返回对象结构。
- 最小修复 `RapidOcrProvider` 解析逻辑，避免当前版本被误判为 unsupported result format。
- 保留旧格式兼容，不修改默认 OCR provider、Draft recognize API、前端、数据库或 Baidu provider。
- 自动化测试继续使用 fake result，不调用真实 RapidOCR、百度 OCR、DeepSeek 或网络。
- 修复后用本地 3 张 smoke 图片运行 rapidocr-only smoke；成功后再运行 baidu vs rapidocr A/B，不带 `--with-llm`。

探测结果：

- 项目 venv 已确认使用 `D:\math_knowledge_system\backend\venv\Scripts\python.exe`。
- 本轮将项目 venv 中 `rapidocr` 从 3.4.5 升级到 3.8.4，并确认 `onnxruntime 1.27.0` 已安装。
- RapidOCR 3.8.4 返回对象类型为 `rapidocr.utils.output.RapidOCROutput`。
- 关键字段包括 `txts`、`boxes`、`scores`、`word_results`、`elapse_list`、`elapse`，并提供 `to_json()`。
- `txts` 是 tuple；`boxes` 是 numpy ndarray。旧解析逻辑对 `boxes` 做布尔判断，触发 array truth value `ValueError`，导致 provider 误报 unsupported result format。

结果：

- `RapidOcrProvider` 解析器改为优先读取 `txts/texts`，不再对 numpy/array-like `boxes`、`scores` 做布尔判断。
- 增加 `to_dict()` / `model_dump()` / `to_json()` 返回结构的兜底解析。
- 空 `txts` 视为合法空文本，返回 `text=""`，不误报 unsupported。
- unsupported 错误信息增加类型、可见属性摘要和截断 repr，便于下一次诊断。
- 新增 `backend/scripts/__init__.py` 和 `backend/scripts/evaluation/__init__.py`，避免 venv 中第三方 `scripts` 包遮蔽项目脚本，保证 `python -m pytest tests/test_ocr_ab_evaluation.py` 可收集。

验证结果：

- `cd backend && python -m pytest tests/test_ocr_provider.py` 通过，`15 passed`，仍有 `.pytest_cache` 权限 warning。
- `cd backend && python -m pytest tests/test_ocr_ab_evaluation.py` 通过，`5 passed`，仍有 `.pytest_cache` 权限 warning。
- `cd backend && python -m pytest` 通过，`125 passed`，仍有 `.pytest_cache` 权限 warning。
- `cd backend && python -m compileall app` 通过。
- `cd backend && python -m unittest discover tests` 通过，`Ran 125 tests OK`。
- `cd backend && python scripts/evaluation/compare_ocr_providers.py --input "D:\math_knowledge_system\data\manual_smoke\ocr_images" --providers rapidocr --output reports/ocr_ab/rapidocr_smoke_after_parser_fix.md --json-output reports/ocr_ab/rapidocr_smoke_after_parser_fix.json` 通过。
- `cd backend && python scripts/evaluation/compare_ocr_providers.py --input "D:\math_knowledge_system\data\manual_smoke\ocr_images" --providers baidu,rapidocr --output reports/ocr_ab/ocr_ab_first_smoke_parser_fixed.md --json-output reports/ocr_ab/ocr_ab_first_smoke_parser_fixed.json` 通过。

Smoke 摘要：

- RapidOCR-only smoke：3 张全部成功，耗时约 2029-2811 ms，文本长度分别为 43、87、95；第二张触发 `choice_options_incomplete`。
- 完整 A/B：Baidu 3 张全部成功，耗时约 930-1430 ms，文本长度分别为 74、326、291；3 张均触发 `choice_options_incomplete`。
- 完整 A/B：RapidOCR 3 张全部成功，耗时约 2134-2824 ms，文本长度分别为 43、87、95；第二张触发 `choice_options_incomplete`。

边界：

- 本轮只解决 RapidOCR 3.8.4 返回结构解析，不表示 RapidOCR 质量优于百度。
- RapidOCR 输出文本长度明显短于 Baidu，可能存在漏题、漏选项或版面识别不足，需要人工逐题核对完整报告和原图。
- 未修改默认 `OCR_PROVIDER`，默认仍为 `baidu`。
- 未修改 Draft recognize API、前端、数据库模型、BaiduOcrProvider 或 legacy `/api/v1/recognize`。
- 本地报告位于 `backend/reports/ocr_ab/`，不提交完整报告和 JSON。

## 2026-06-17 第二十八点五轮：OCR A/B first smoke 实跑摘要

目标：

- 使用 `D:\math_knowledge_system\data\manual_smoke\ocr_images` 中的 3 张 smoke 图片运行 OCR Provider A/B 评测。
- 从 `backend/` 目录运行 `compare_ocr_providers.py`，providers 为 `baidu,rapidocr`。
- 本轮不带 `--with-llm`，不调用 LLM。
- 不修改默认 `OCR_PROVIDER`，不提交本地真实评测产物。
- 成功后新增提交用摘要文档，不粘贴完整 OCR 原文。

结果：

- 已生成本地真实评测产物：
  - `backend/reports/ocr_ab/ocr_ab_first_smoke.md`
  - `backend/reports/ocr_ab/ocr_ab_first_smoke.json`
- 上述报告目录已被 `.gitignore` 忽略，本轮不提交完整报告和 JSON。
- Baidu OCR 对 3 张图片均成功返回文本。
- 3 张图片均触发 `choice_options_incomplete` 风险提示。
- RapidOCR 包已安装，但运行时报错 `onnxruntime is not installed.`，3 张图片均未产生 OCR 文本。
- 新增 `docs/OCR_AB_FIRST_SMOKE.md`，只记录运行范围、摘要表、初步观察和边界，不粘贴完整 OCR 原文。

验证结果：

- `cd backend && python scripts/evaluation/compare_ocr_providers.py --input "D:\math_knowledge_system\data\manual_smoke\ocr_images" --providers baidu,rapidocr --output reports/ocr_ab/ocr_ab_first_smoke.md --json-output reports/ocr_ab/ocr_ab_first_smoke.json` 通过，脚本退出码为 0。
- `cd backend && python -m pip show rapidocr` 显示已安装 `rapidocr 3.8.4`。
- `cd backend && python -m pip show onnxruntime` 显示未安装，符合 RapidOCR 失败原因。
- 本轮为真实 smoke 与文档摘要更新，未运行后端自动化测试。

边界：

- 未安装 `onnxruntime`，因此本轮不能形成 RapidOCR 识别质量结论。
- 未启用 LLM，不评价 LLM 清洗或知识点标签效果。
- 未修改后端代码、前端代码、数据库模型、Draft API 或 legacy `/api/v1/recognize`。
- 未修改默认 OCR provider。

## 2026-06-17 第二十八轮：OCR Provider A/B smoke 评测机制

目标：

- 新增一个可重复运行的手工评测脚本，用同一批题图分别跑 `baidu` 和 `rapidocr`。
- 输出结构化结果和 Markdown 报告，便于记录 OCR 文本、耗时、质量风险和人工结论。
- 默认不调用 LLM；只有显式 `--with-llm` 才调用现有 LLM 清洗服务。
- 不修改默认 OCR provider、不修改 Draft recognize API、不修改前端、不修改数据库模型。
- 自动化测试不依赖真实 OCR/LLM/API key/网络。

结果：

- 新增 `backend/scripts/evaluation/compare_ocr_providers.py`。
- 脚本支持 `--input` 单图或目录，目录只收集 `.jpg`、`.jpeg`、`.png`、`.webp` 并按文件名排序。
- 脚本支持 `--providers`、`--output`、`--json-output`、`--with-llm`。
- 每张图片每个 provider 记录 `image_path`、`image_name`、`provider`、`success`、`error_message`、`elapsed_ms`、`raw_text`、`raw_text_length`、`quality_warnings`、LLM 字段、`manual_conclusion` 和 `notes`。
- Provider 或 LLM 异常会写入对应结果，不中断其他 provider 或图片。
- `OCRService.recognize()` 增加可选 `provider_name` 单次覆盖参数；默认仍读取 `OCR_PROVIDER`，默认仍为 `baidu`。
- `.gitignore` 忽略 `backend/reports/ocr_ab/`，避免真实评测报告默认入库。
- `docs/OCR_EVAL.md` 增加脚本用法、PowerShell 示例、JSON 输出和报告入库边界。

验证结果：

- `cd backend && python -m unittest tests.test_ocr_provider.OcrProviderTests.test_ocr_service_can_override_provider_per_recognize_call` 先按预期失败，错误为 `OCRService.recognize()` 不支持 `provider_name`；实现后通过。
- `cd backend && python -m unittest tests.test_ocr_ab_evaluation` 先按预期失败，错误为缺少 `scripts.evaluation` 模块；实现后通过，`Ran 5 tests OK`。
- `cd backend && python -m compileall app` 通过。
- `cd backend && python -m py_compile scripts/evaluation/compare_ocr_providers.py` 通过。
- `cd backend && python -m unittest tests.test_ocr_provider tests.test_ocr_ab_evaluation` 通过，`Ran 18 tests OK`。
- `cd backend && python -m unittest discover tests` 首次 120 秒超时未取得最终结论；提高超时后通过，`Ran 123 tests OK`。

边界：

- 未真实调用百度 OCR、RapidOCR 模型或 DeepSeek API。
- 未把 RapidOCR 设为默认 provider。
- 未修改 Draft recognize API、前端、数据库模型或 legacy `/api/v1/recognize`。
- 未优化 OCR 精度，未解决公式、双栏和选项漏识别问题。
- 真实 smoke 报告需要人工判断是否适合提交。

## 2026-06-16 第二十七点五轮：pytest 根目录遗留测试收口

目标：

- 清理 `python -m pytest` 自动收集根目录历史脚本导致的失败。
- 不修改 RapidOCR Provider、OCRService、Draft recognize API、前端或 LLM 服务主逻辑。
- 不恢复旧的 `correct_text` 函数，不让自动测试依赖真实 DeepSeek API。

结果：

- 确认 `backend/test_deepseek.py` 是历史手工调试脚本，不是正式自动化测试。
- 将该脚本移至 `backend/scripts/manual/deepseek_manual_check.py`，避开 pytest 默认 `test_*.py` 收集规则。
- 新手工脚本顶部明确说明不属于自动测试套件。
- 手工脚本改用当前 `app.services.llm.nlp_service.analyze()` 接口，未恢复废弃的 `app.services.nlp_engine.correct_text`。
- 记录测试目录规范：自动化测试放 `backend/tests/`，手工 API/LLM 调试脚本放 `backend/scripts/manual/`。

验证结果：

- `cd backend && python -m pytest` 先按预期失败，错误为根目录 `test_deepseek.py` 导入不存在的 `correct_text`。
- 移动并改写手工脚本后，`cd backend && python -m compileall app` 通过。
- `cd backend && python -m unittest discover tests` 通过，`Ran 117 tests OK`。
- `cd backend && python -m pytest tests` 通过，`117 passed`，仍有 `.pytest_cache` 权限 warning。
- `cd backend && python -m pytest` 通过，`117 passed`，仍有 `.pytest_cache` 权限 warning。
- `cd backend && python -m py_compile scripts/manual/deepseek_manual_check.py` 通过。

边界：

- 未修改 DeepSeek 业务逻辑。
- 未修改 pytest 收集配置。
- 未修改 RapidOCR、OCRService、Draft recognize API、前端或数据库模型。

## 2026-06-16 第二十七轮：RapidOCR 本地 OCR Provider 实验接入

目标：

- 接入 `RapidOcrProvider`，让 Draft 主识别流程可通过 `OCR_PROVIDER=baidu` / `OCR_PROVIDER=rapidocr` 切换。
- 默认仍使用 `baidu`，不破坏现有稳定流程。
- RapidOCR 作为可选依赖处理，未安装时不影响 baidu 启动和测试。
- 不修改 Draft recognize API、前端、数据库模型或 legacy `/api/v1/recognize`。

结果：

- 新增 `backend/app/services/ocr_providers/rapidocr.py`，延迟导入 `rapidocr.RapidOCR`，依赖缺失时提示 `pip install rapidocr`。
- RapidOCR provider 支持懒加载并缓存 engine；`OCRService` 支持 `rapidocr` 并按 provider 名称缓存 provider 实例。
- RapidOCR 解析函数支持对象 `txts/texts`、`boxes/scores`、旧式 `(boxes, txts, scores)`、逐行 tuple/dict 和空结果。
- 未知 `OCR_PROVIDER` 返回清晰错误：`Unsupported OCR_PROVIDER: <value>. Supported values: ...`。
- `backend/.env.example` 增加 OCR provider 切换示例；`backend/requirements.txt` 仅注释 RapidOCR 为可选本地 OCR 依赖。
- 新增/扩展后端单元测试覆盖默认 baidu、rapidocr 选择、provider 缓存、缺依赖错误和 RapidOCR 解析。

验证结果：

- `cd backend && python -m unittest tests.test_ocr_provider` 先按预期失败，提示缺少 `app.services.ocr_providers.rapidocr`；实现后通过，`Ran 12 tests OK`。
- `cd backend && python -m compileall app` 通过。
- `cd backend && python -m unittest discover tests` 通过，`Ran 117 tests OK`。
- `cd backend && python -m pytest tests` 通过，`117 passed`，仍有 `.pytest_cache` 权限 warning。
- `cd backend && python -m pytest` 在第二十七点五轮已收口通过。

边界：

- 未真实安装或调用 RapidOCR 模型。
- 未提升 OCR 精度，未解决双栏选项漏识别。
- 未修改前端、数据库模型、Draft API 请求/响应结构或 legacy `/api/v1/recognize`。

## 2026-06-16 第二十六轮：识别结果风险提示与保存前校验

目标：

- 不解决 OCR 漏识别本身，只增加保存前质量风险提示。
- 对疑似选择题 A/B/C/D 选项不完整、选项顺序断档、文本过短、OCR/LLM 长度差异过大给出 warning。
- Dashboard 结果区展示风险提示，并在保存入题库前要求用户确认。
- 不修改 OCR provider、BaiduOcrProvider、LLM prompt、legacy `/api/v1/recognize`、数据库模型、PaperRenderModel 或 PaperPreview。

结果：

- 新增 `RecognitionQualityWarning` 和 Draft 响应字段 `quality_warnings`，动态计算，不落库。
- 新增 `backend/app/services/recognition_quality.py`，支持检测常见 `A. / A． / A、 / A）` 等选项标签。
- Draft detail / recognize / save-to-bank 响应均可带出 `quality_warnings`。
- Dashboard 结果区新增“识别风险提示”，保存前若存在风险提示会弹出确认框。
- 前端确认后仍可保存，不在后端强制阻断 save-to-bank。
- `docs/MVP_SMOKE_CHECKLIST.md` 增加选择题选项缺失、风险提示和保存确认检查项。

验证结果：

- `cd backend && python -m compileall app` 通过。
- `cd backend && python -m unittest tests.test_recognition_quality` 通过，`Ran 6 tests OK`。
- `cd backend && python -m unittest tests.test_draft_pipeline` 通过，`Ran 17 tests OK`。
- `cd backend && python -m unittest discover tests` 通过，`Ran 109 tests OK`。
- `cd frontend && npm run test:stage3-contract` 通过。
- `cd frontend && npm run build` 通过，仍有 Vite chunk size warning。

边界：

- 未提升 OCR 准确率，未恢复漏识别选项。
- 未接入 RapidOCR、PaddleOCR、Pix2Text。
- 未改 OCRService provider、BaiduOcrProvider 或 LLM prompt。
- 未改 legacy `/api/v1/recognize`。
- 未做数据库迁移、QuestionAsset、历史记录重构、题库删除或服务端 PDF/DOCX 导出。

## 2026-06-16 第二十五轮：重复素材上传支持 smoke 复用

目标：

- 解决同一用户反复上传同一张本地 smoke 图片时 `Asset already exists` 阻断流程的问题。
- 保留 asset 去重，不重复保存同一份图片文件。
- 重复上传时返回已有 asset 信息，让前端继续创建新的 Draft 并 recognize。
- 不做历史记录重构、题库删除、OCR provider 修改或 LLM prompt 修改。

结果：

- `POST /api/v1/assets` 在 `SourceAsset.sha256` 唯一约束冲突后，会删除本次临时保存的重复文件，并查询当前用户自己的同 hash asset。
- 如果找到当前用户已有 asset，返回 `200` 和原 asset 信息，并附带 `deduplicated=true`、`existing_asset_id`、`message="Asset already exists, using existing asset."`。
- 如果冲突 asset 不属于当前用户，仍返回通用 `409 Asset already exists`，不暴露其他用户 asset id。
- Dashboard 收到去重复用响应时显示“素材已存在，已复用已有素材继续录入。”，并继续 Draft 创建和识别。
- 已验证 `Draft.source_asset_id` 没有唯一约束，同一 asset 可以创建多个 Draft，支持 smoke 反复测试 OCR/LLM 效果。
- `docs/MVP_SMOKE_CHECKLIST.md` 增加重复上传复用检查项。

验证结果：

- `cd backend && python -m unittest tests.test_draft_pipeline.DraftPipelineTests.test_repeated_asset_upload_reuses_existing_asset_and_allows_new_draft` 先按预期失败，提示重复上传仍返回 409；实现后通过。
- `cd frontend && npm run test:stage3-contract` 先按预期失败，提示 Dashboard 未处理重复 asset 复用；实现后通过。
- `cd backend && python -m compileall app` 通过。
- `cd backend && python -m unittest discover tests` 通过，`Ran 103 tests OK`。
- `cd frontend && npm run test:auth-contract` 通过。
- `cd frontend && npm run test:stage3-contract` 通过。
- `cd frontend && npm run build` 通过，仍有 Vite chunk size warning。

边界：

- 未修改数据库模型或 Alembic 迁移。
- 未新增 QuestionAsset 表。
- 未做完整历史记录重构或历史记录重新编辑。
- 未做题库删除功能。
- 未接入 RapidOCR、PaddleOCR、Pix2Text。
- 未修改 OCRService provider 选择逻辑、BaiduOcrProvider、LLM prompt、legacy `/api/v1/recognize`、PaperRenderModel 或 PaperPreview 打印逻辑。
- 自动化测试不调用真实 OCR 或 LLM API。

## 2026-06-16 第二十四轮：OCR/LLM 保真与可回溯修复

目标：

- 区分 OCR 错误和 LLM 清洗错误。
- Draft detail 和 Dashboard 结果区能查看原始 OCR 文本与 LLM 清洗文本。
- 将 Draft LLM prompt 调整为保真整理模式，禁止猜题、补题、改题意。
- 不追求 OCR 准确率提升，不接入新 OCR provider，不做数据库迁移。

结果：

- `DraftDetail` 新增可选 `recognition_debug`，字段包含 `ocr_provider`、`ocr_raw_text`、`llm_cleaned_text`、`ocr_error`、`llm_error`。
- `_build_draft_detail()` 复用 `Draft.current_content`、`OCRRun.parsed_blocks/response_raw_json`、`LLMRun.parsed_output/raw_output` 组装调试信息。
- Dashboard 识别结果区新增默认折叠的“识别调试信息”，展示“原始 OCR 文本”和“LLM 清洗文本”。
- LLM prompt 增加保真规则：不改变题意，不根据常见题型猜测原题，不删除选项，不替换变量/点名/线段名/焦点编号，不改写数学表达式，并加入 AF1/AF2、`|F1A|·|F1B|/|AB|`、`m^2y + 6` 等防篡改示例。
- 后端测试覆盖 prompt 保真规则和 Draft detail 调试信息；前端契约测试覆盖调试展示文案。
- STATUS、DECISIONS、KNOWN_ISSUES 同步本轮保真与可回溯口径。

验证结果：

- `cd backend && python -m compileall app` 通过。
- `cd backend && python -m unittest tests.test_llm` 通过，`Ran 23 tests OK`。
- `cd backend && python -m unittest tests.test_draft_pipeline` 通过，`Ran 16 tests OK`。
- `cd backend && python -m unittest discover tests` 通过，`Ran 102 tests OK`。
- `cd frontend && npm run test:auth-contract` 通过。
- `cd frontend && npm run test:stage3-contract` 通过。
- `cd frontend && npm run build` 通过，仍有 Vite chunk size warning。

边界：

- 未接入 RapidOCR、PaddleOCR、Pix2Text 或其他本地 OCR。
- 未修改 OCRService provider 选择逻辑、BaiduOcrProvider 或 legacy `/api/v1/recognize`。
- 未修改数据库模型、Alembic 迁移、QuestionAsset、PaperRenderModel 或 PaperPreview 打印逻辑。
- 未调用真实百度 OCR 或真实 LLM API。

## 2026-06-16 第二十三轮：MVP 使用闭环与本地 smoke 样例收口

目标：

- 明确本地 smoke 样例图片放置位置。
- 使用 3 张 PDF 截图数学题作为手动 smoke 样例，不提交真实图片。
- 新增 MVP 手动 smoke checklist 和 Demo 使用流程文档。
- 如 PaperPreview 缺少打印入口，则增加最小浏览器打印入口。
- 不接入新 OCR，不扩展评估集，不修改主流程。

结果：

- `.gitignore` 已忽略 `data/manual_smoke/ocr_images/` 和 `data/manual_smoke/predictions/`。
- 新增 `docs/DEMO_FLOW.md`，说明后端启动、前端启动、登录、上传 smoke 图片、创建 Draft、recognize、编辑草稿、保存题库、创建试卷、预览和浏览器打印/另存 PDF。
- 新增 `docs/MVP_SMOKE_CHECKLIST.md`，记录 `smoke_ocr_001_interval_choice.png`、`smoke_ocr_002_parallel_line_blank.png`、`smoke_ocr_003_ellipse_solution.png` 的元信息和人工检查项。
- `PaperPreview.vue` 新增“打印/导出 PDF”按钮，点击后调用 `window.print()`。
- `PaperPreview.vue` 新增最小 print CSS，打印时隐藏不必要按钮、列表和导航，保留 A4 预览内容。
- `frontend/tests/paper-mvp-contract.test.mjs` 增加打印入口契约断言。
- README 增加 Demo 和 smoke 文档入口。
- STATUS 和 KNOWN_ISSUES 同步 MVP 闭环收口、OCR Eval 暂停扩展、本地 OCR 未接入、浏览器打印导出和当前样本局限。

验证结果：

- `cd frontend && node ./tests/paper-mvp-contract.test.mjs` 先按预期失败，提示缺少打印导出能力；实现后通过。
- `cd backend && python -m compileall app` 通过。
- `cd backend && python -m unittest discover tests` 通过，`Ran 102 tests OK`。
- `cd frontend && npm run build` 通过，仍有 Vite chunk size warning。

边界：

- 未接入 RapidOCR、PaddleOCR、Pix2Text 或其他本地 OCR。
- 未扩展 OCR 评估集，未读取真实 smoke 图片做自动化测试。
- 未调用真实 OCR API 做自动化测试。
- 未修改 OCRService provider 选择逻辑、Draft recognize 主流程或 legacy `/api/v1/recognize`。
- 未做数据库迁移、QuestionAsset 表、服务端 PDF/DOCX 导出或 PaperRenderModel 核心结构修改。

## 2026-06-16 第二十二轮：OCR 方案评估集与评估指标基础

目标：

- 建立轻量 OCR eval case 和 prediction JSON 结构。
- 新增离线 OCR 文本级评估指标，用于后续比较百度、本地 OCR 和云 fallback。
- 不调用真实 OCR，不接入 RapidOCR、PaddleOCR、Pix2Text，不修改 Draft recognize 或 legacy `/api/v1/recognize`。

结果：

- 新增 `backend/app/services/ocr_evaluation.py`，提供 `normalize_ocr_text()`、`evaluate_ocr_prediction()`、`evaluate_ocr_batch()`。
- 新增 `OcrEvalMetrics`、`OcrEvalRecord`、`OcrProviderEvalSummary`、`OcrEvalSummary`，支持单条指标和按 provider 汇总。
- 新增轻量 fixture：`ocr_eval_cases.json` 和 `ocr_eval_predictions.json`，使用占位图片路径，不依赖真实图片。
- 新增 `backend/tests/test_ocr_evaluation.py`，覆盖空白归一化、完全匹配、轻微 OCR 差异、关键术语召回、provider 汇总、缺失 prediction 和 error prediction。
- 新增 `docs/OCR_EVAL.md`，说明评估集格式、prediction 格式、指标、局限和后续 provider 对比方式。

验证结果：

- `cd backend && python -m compileall app` 通过。
- `cd backend && python -m unittest tests.test_ocr_evaluation` 通过，`Ran 6 tests OK`。
- `cd backend && python -m unittest discover tests` 通过，`Ran 102 tests OK`。

边界：

- 当前评估只是文本级初步评估，不覆盖数学公式语义、几何图结构或版面理解。
- 未建立真实大规模数学题图片评估集。
- 未新增外部依赖，未修改 OCRService provider 选择逻辑。

## 2026-06-06 第二十一轮：OCR Provider 抽象与部署成本控制基础

目标：

- 让 Draft recognize 主流程不再直接依赖百度 OCR 具体实现。
- 新增内部统一 OCRService 和 OCR Provider 接口。
- 将现有百度 OCR 封装为默认 `BaiduOcrProvider`，但不改变识别逻辑。
- 为后续 RapidOCR / PaddleOCR / Pix2Text / 百度 fallback 打基础。

结果：

- 新增 `OCRResult` 和 `OcrProvider`，作为 OCR 内部统一结果对象和 provider 协议。
- 新增 `BaiduOcrProvider`，通过 fake legacy engine 测试确认只包装既有 `ocr_engine.py` 返回，不真实调用百度 API。
- 新增 `OCRService`，按 `OCR_PROVIDER` 选择 provider；默认 `baidu`。
- 未知 provider 返回明确失败：`unsupported_provider` 和 `unsupported_ocr_provider:<provider>`。
- Draft recognize 改为调用 `draft_ocr_service`，OCRRun 记录实际 provider，日志增加 `ocr_provider`。
- legacy `/api/v1/recognize` 保持调用既有 `ocr_engine.ocr_service`，未纳入本轮改造。

验证结果：

- `cd backend && python -m unittest tests.test_ocr_provider` 通过，`Ran 4 tests OK`。
- `cd backend && python -m unittest tests.test_draft_pipeline.DraftPipelineTests.test_draft_pipeline_recognize_is_lightweight_and_save_to_bank_sets_metadata_pending` 通过。
- `cd backend && python -m compileall app` 通过。
- `cd backend && python -m unittest discover tests` 通过，`Ran 96 tests OK`。

边界：

- 未接入 RapidOCR、PaddleOCR、Pix2Text 或其他本地 OCR。
- 未启用 OCR fallback 链。
- 未修改数据库模型、迁移、前端、PaperRenderModel、PaperPreview 或 legacy `/api/v1/recognize`。
- 本轮没有解决 OCR 成本问题，只建立后续切换基础。

## 2026-06-06 第二十点六轮：Draft LLM 非思考模式 + JSON 输出稳定化

目标：

- 根据 DeepSeek 官方文档调整第二十点六轮目标：不采用 `reasoning_effort="low"` 降成本，改为 Draft LLM 默认关闭 thinking 并启用 JSON output。
- 不修改 PaperRenderModel、PaperPreview、数据库模型、前端、legacy `/api/v1/recognize` 或 Draft fallback 状态机。

结果：

- `NLPService.analyze()` 调用 OpenAI SDK 时传入 `extra_body={"thinking": {"type": "disabled"}}`，默认 thinking mode 为 `disabled`，可通过 `LLM_THINKING_MODE` 配置。
- 启用 `response_format={"type": "json_object"}`，并在 system/user prompt 中明确 JSON 要求和 JSON 输出样例。
- Prompt 角色从“高中数学助教”调整为“高中数学 OCR 文本清洗与结构化工具”，强调不解题、不证明、不分析、不输出推理过程，只修正 OCR、只规范 LaTeX、只返回 JSON。
- max_tokens 改为 `LLM_MAX_TOKENS` 可配置，默认 `2048`；timeout 改为 `LLM_TIMEOUT_SECONDS` 可配置，默认 `45` 秒。
- 未传入 `reasoning_effort`，避免 DeepSeek low/medium 映射为 high 带来的无效降成本方案。
- 保留第二十点五轮安全摘要日志字段；`finish_reason=length` 且 content 为空时，错误 detail 使用 `deepseek_length_exhausted_empty_content`。
- Draft fallback 状态机保持不变：LLM 失败仍返回 `draft_ready + partial_success=True`。

验证结果：

- `cd backend && python -m unittest tests.test_llm` 通过。
- `cd backend && python -m unittest tests.test_draft_pipeline.DraftPipelineTests.test_draft_recognize_records_empty_content_invalid_response` 通过。
- `cd backend && python -m compileall app` 通过。
- `cd backend && python -m unittest discover tests` 通过，`Ran 92 tests OK`。

边界：

- 本轮未直接把 max_tokens 升到 6000。
- 本轮未把 reasoning_content 当 corrected_text 使用。
- 本轮未执行真实复杂椭圆题在线复测，仍建议下一步用复杂椭圆题重新验收。

## 2026-06-06 第二十点五轮：Draft LLM 空响应诊断增强

目标：

- 暂停第二十一轮新功能，只诊断并修复 Draft 识别链路中复杂 OCR 文本触发 DeepSeek empty content 时缺少可观测性的问题。
- 不修改 PaperRenderModel、PaperPreview、数据库模型、Alembic 迁移、前端或 legacy `/api/v1/recognize` 主流程。

结果：

- `NLPService.analyze()` 新增 DeepSeek 响应安全摘要，记录 response 类型、id、model、choices 数、finish_reason、message role、content 长度和截断预览、refusal、reasoning_content、tool_calls、usage token、输入长度、配置模型、timeout 和截断后的 raw response preview。
- empty content、空 choices、缺 choices、非 JSON、缺 `corrected_text`、字段结构非法等分支改为输出安全摘要日志，不再打印完整 response、完整 non-JSON 内容或完整 result。
- empty content 的 `detail` 增强为包含 `choices_count`、`finish_reason`、`content_len`、`completion_tokens` 的可区分错误信息。
- Draft fallback 状态机保持不变：LLM 失败仍返回 `draft_ready + partial_success=True`，并保留 warning 与 LLMRun 错误信息。
- 新增后端测试覆盖 DeepSeek 响应异常结构、安全摘要截断和 Draft empty content fallback 记录。

验证结果：

- `cd backend && python -m unittest tests.test_llm` 通过。
- `cd backend && python -m unittest tests.test_draft_pipeline.DraftPipelineTests.test_draft_recognize_records_empty_content_invalid_response` 通过。
- `cd backend && python -m compileall app` 通过。
- `cd backend && python -m unittest discover tests` 通过，`Ran 90 tests OK`。

边界：

- 本轮未恢复 `response_format={"type": "json_object"}`，需先用复杂椭圆题复现并根据 finish_reason / usage / raw_response_preview 判断。
- 本轮不阻止 partial_success Draft 保存入库，不改变 Draft 主流程。
- 本轮不是对所有 DeepSeek 空响应的彻底根治，只增强诊断能力和错误区分。

## 2026-06-06 第二十轮：PaperRenderModel + 作业模板预览 MVP

目标：

- 为已有试卷增加学生版 A4 作业预览入口。
- 后端将 Paper / PaperItem 转换为 PaperRenderModel，前端只负责展示。
- 仅支持内置 `homework` 模板、`student` 版本、`A4`、按 `question_type` 分组、按 `position` 排序。
- 支持 `answer_area_mode=none` 和 `after_each_question`。

结果：

- 新增 `POST /api/v1/papers/{paper_id}/render-model`。
- 新增独立 `paper_render.py` schema 和 `paper_render_service.py` service，未把渲染模型塞入既有 Paper schema/service。
- RenderModel 归一化历史知识点数据为 `{ label, score }` 结构。
- 学生版响应不返回答案或解析快照。
- 题型快照为空时归入 `unknown / 未分类`。
- 新增 `PaperPreview.vue`，以 A4 视觉样式渲染作业预览，并复用共享 `renderMarkdown.ts`。
- `PaperPanel.vue` 仅增加预览入口、请求状态和答题区模式配置。
- 更新 API、STATUS、DECISIONS、KNOWN_ISSUES 文档。

验证结果：

- `cd backend && python -m unittest tests.test_paper_render` 通过。
- `cd backend && python -m compileall app` 通过。
- `cd backend && python -m unittest discover tests` 通过，`Ran 82 tests OK`。
- `cd frontend && npm run test:stage3-contract` 通过。
- `cd frontend && npm run build` 通过，仅有 Vite chunk size warning。

边界：

- 未做数据库迁移、新表或 Paper / PaperItem 模型修改。
- 未做 PDF / DOCX 导出。
- 未做模板编辑器、自动分页、拖拽排序、知识点排序、难度排序或复杂答题卡。
- 未修改 `/api/v1/recognize`，未切换 Draft/Paper 主流程。

## 2026-06-05 第十九轮性能收口补丁：性能日志可观测性

目标：

- 只补充性能日志可观测性，不新增功能。
- 检查 Draft recognize 主链路 `[DraftRecognizePerf]` 是否覆盖 LLM 成功、LLM fallback 和 OCR 失败路径。
- 将后台元数据评估 `[QuestionMetadataPerf]` 从总耗时拆分为 load、prompt、api、parse、db 和 total 阶段耗时。

结果：

- 确认 Draft recognize 在 OCR 失败路径和 LLM 成功 / fallback 路径都会输出 `[DraftRecognizePerf]`，日志只包含耗时、模型、文本长度、fallback 状态、原因和失败阶段。
- `NLPService.analyze(..., include_metadata=True)` 内部返回 `_perf` 阶段耗时，供后台任务日志使用；不记录 API key、完整 prompt 或完整题目正文。
- `evaluate_question_metadata_task()` 输出 `load_ms`、`prompt_ms`、`api_ms`、`parse_ms`、`db_ms`、`total_ms`、模型、状态、题型、难度和错误。
- DeepSeek metadata 失败日志将 timeout、invalid JSON、API 类错误归一为 `timeout`、`invalid_json`、`api_error`。
- 新增后端测试覆盖 metadata 阶段耗时日志字段，以及 OCR 失败时 Draft recognize 性能日志字段。

验证结果：

- `cd backend && python -m compileall app` 通过。
- `cd backend && python -m unittest discover tests` 通过。

边界：

- 未修改前端。
- 未修改数据库模型或迁移。
- 未做排序、模板、导出、答题区域、重新评估按钮、轮询、WebSocket、Celery / Redis。
- 未删除或重构 legacy recognize。

## 2026-06-04 第十九轮性能收口：元数据后台补全与性能日志

目标：

- 将题型/难度评估从同步 Draft recognize 主链路拆出，降低录入等待时间。
- 保存入题库后后台补全题型与五星难度元数据。
- 增加 Draft recognize 和后台元数据评估性能日志。
- 不做模板、排序、导出、答题区域、智能组卷、WebSocket、自动轮询、Celery / Redis 或大重构。

结果：

- `NLPService.analyze()` 默认轻量返回 `corrected_text` 和 `knowledge_tags`，显式 `include_metadata=True` 时才解析题型与难度。
- 新增 `evaluate_question_metadata()` 供后台元数据评估使用。
- `Question` 新增 `metadata_status`、`metadata_error`、`metadata_started_at`、`metadata_finished_at` nullable 字段。
- 新增 Alembic 迁移 `20260604_0005_question_metadata_status.py`。
- Draft recognize 不再把题型/难度写入 Draft；返回字段保留为可空兼容字段。
- save-to-bank 创建 Question 时设置 `metadata_status=pending`，通过 FastAPI `BackgroundTasks` 调用后台任务。
- 后台任务内部新建 DB session，成功写入题型/难度并标记 `ready`，失败标记 `failed`，不影响保存入题库请求。
- PaperItem 仅在 Question 元数据 ready 且已有难度时保存题型/难度快照；否则快照为空。
- `BankPanel.vue` 根据 `metadata_status` 展示“元数据评估中”“难度评估失败”“未评估”或五星难度。
- 增加 `[DraftRecognizePerf]` 和 `[QuestionMetadataPerf]` 日志，记录耗时、模型、文本长度、fallback 或错误状态。
- `backend/.env.example` 增加 `DEEPSEEK_TIMEOUT_SECONDS` 和 `DEEPSEEK_METADATA_TIMEOUT_SECONDS` 示例配置。
- 更新 API、STATUS、DECISIONS、KNOWN_ISSUES 文档。

验证结果：

- 已先运行 `python -m unittest tests.test_llm tests.test_draft_pipeline tests.test_paper_mvp` 和 `node ./tests/paper-mvp-contract.test.mjs`，在功能缺失时按预期失败。
- 实现后定向后端测试通过，`Ran 38 tests OK`。
- 实现后前端 Paper MVP 契约测试通过。
- 完整验证命令结果见 `docs/STATUS.md` 最新验证结果。

边界：

- 未改变 Draft 状态机。
- 未删除或重构 legacy recognize。
- 未做排序、筛选、模板、导出、答题区域、智能组卷、重新评估按钮、WebSocket、自动轮询或 Celery / Redis。
- 后台任务依赖当前后端进程，服务重启可能丢失正在执行的元数据评估任务。

## 2026-06-04 第十九轮：LLM 题型与五星难度元数据

目标：

- 扩展 LLM analyze 输出契约，增加题型和五星难度元数据。
- 将题型与难度保存到 Question，并在 Draft recognize、Question API 和题库前端最小展示。
- 不做排序、模板、导出、答题区域、智能组卷或大规模重构。

结果：

- `backend/app/services/llm.py` 兼容 `knowledge_tags` 和旧 `tags`，新增 `question_type` 和 `difficulty` 解析。
- `difficulty` 缺失或非法时不阻断 `corrected_text` 主流程，非法 difficulty 返回 fallback warning。
- `Draft` 新增 nullable 题型与难度字段，避免把 `current_content` 扩展成复杂元数据载体。
- `Question` 新增题型、难度、置信度、理由、评估模型和评估时间字段。
- `PaperItem` 新增可选题型与难度快照字段。
- Draft recognize 返回题型与难度；save-to-bank 保存到 Question。
- Question 列表和详情返回题型与难度。
- `BankPanel.vue` 最小展示题型和五星难度；`PaperPanel.vue` 最小展示 PaperItem 快照题型和难度。
- 更新 API、STATUS、DECISIONS、KNOWN_ISSUES 文档。

验证结果：

- 已先运行 `python -m unittest tests.test_llm`、`python -m unittest tests.test_draft_pipeline`、`python -m unittest tests.test_paper_mvp` 和 `node ./tests/paper-mvp-contract.test.mjs`，在功能缺失时按预期失败。
- 实现后上述定向测试均已通过。
- 已运行 `python -m compileall app`，通过。
- 已运行 `python -m unittest discover tests`，通过，`Ran 68 tests OK`。
- 已运行 `npm run build`，通过，仅有 Vite chunk size warning。
- 已运行 `npm run test:auth-contract`，通过。
- 已运行 `npm run test:stage3-contract`，通过。
- 默认 `alembic upgrade head` 因当前本地 SQLite 数据库只读失败；改用临时 SQLite 数据库运行 `alembic upgrade head; alembic current`，通过，当前 `20260604_0004 (head)`。

边界：

- 未做按难度排序或筛选。
- 未做按知识点排序。
- 未做组卷模板、自定义模板、PDF / DOCX 导出、答题区域或智能组卷。
- 未改变 Draft flow 状态机。
- 未删除 legacy recognize。
- 用户编辑题目后不会自动重新评估题型或难度。

## 2026-06-03 第十八轮：前端组卷入口 MVP

目标：

- 在不改后端 Paper API 主逻辑、不改 Draft flow、不改 legacy recognize 的前提下，接入前端最小组卷入口。
- 支持从题库选择题目、创建试卷、查看试卷列表、查看试卷详情。
- 不做 PDF / Word 导出、智能组卷、拖拽排序、复杂排版、打印样式优化或大规模前端重构。

结果：

- `BankPanel.vue` 新增题目勾选、已选数量、创建试卷按钮和最小创建弹窗。
- 创建试卷调用 `POST /api/v1/papers`，items 由已选题目生成，score 当前统一为 `0`。
- 新增 `PaperPanel.vue`，支持 `GET /api/v1/papers` 列表和 `GET /api/v1/papers/{paper_id}` 详情。
- 试卷详情展示 position、score、content_snapshot、answer_snapshot、analysis_snapshot、knowledge_tags_snapshot。
- 题目内容、答案、解析继续复用 `frontend/src/utils/renderMarkdown.ts`。
- `Dashboard.vue` 新增独立“组卷”菜单入口，未改动上传、识别、保存入库流程。
- 新增 `frontend/tests/paper-mvp-contract.test.mjs`，并纳入 `npm run test:stage3-contract`。
- 更新 STATUS、DECISIONS、KNOWN_ISSUES 文档。

验证结果：

- 已先运行 `cd frontend && node ./tests/paper-mvp-contract.test.mjs`，在功能缺失时按预期失败。
- 实现后运行 `cd frontend && node ./tests/paper-mvp-contract.test.mjs`，通过。
- 已运行 `cd frontend && npm run build`，通过，仅有 Vite chunk size warning。
- 已运行 `cd frontend && npm run test:auth-contract`，通过。
- 已运行 `cd frontend && npm run test:stage3-contract`，通过，包含 Paper MVP 前端契约检查。

边界：

- 未修改后端 Paper API 主逻辑。
- 未修改 Draft flow。
- 未修改 legacy recognize。
- 未做导出、智能组卷、拖拽排序、分值编辑、复杂试卷排版或打印样式优化。
- 未执行真实浏览器登录和手动创建试卷流程；本轮仅完成代码构建和前端契约验证。

## 2026-05-27 第十七轮：组卷 MVP 后端最小竖切

目标：

- 新增后端最小组卷能力。
- 不重构 Draft flow、legacy recognize 或题库保存逻辑。
- 不做前端、PDF/Word 导出、智能组卷算法或大规模重构。

结果：

- 新增 `Paper` 和 `PaperItem` 数据模型，支持试卷草稿和题目条目。
- `PaperItem` 创建时保存题目快照；如存在 `QuestionRevision`，优先使用最新 revision 内容。
- 新增 `POST /api/v1/papers`、`GET /api/v1/papers`、`GET /api/v1/papers/{paper_id}`。
- 新增 paper service 和 Pydantic schema。
- 新增 `backend/tests/test_paper_mvp.py` 覆盖创建、详情、列表隔离、非法题目、重复题目、position 顺序、快照不随题库修改变化。
- 更新 API、STATUS、DECISIONS、KNOWN_ISSUES 文档。

验证结果：

- 已运行 `cd backend && python -m compileall app`，通过。
- 已运行 `cd backend && python -m unittest tests.test_paper_mvp`，通过，`Ran 9 tests OK`。
- 已运行 `cd backend && python -m unittest discover tests`，通过，`Ran 62 tests OK`。

边界：

- 未修改前端。
- 未修改 `Dashboard.vue`。
- 未删除或重构 `/api/v1/recognize`。
- 未修改 Draft 主流程。
- 未做智能组卷、导出、拖拽排序或自动配比。

## 2026-05-27 第十六轮：阶段性收口、文档去重与 release checkpoint

目标：

- 只做文档去重、状态口径统一和 release checkpoint。
- 检查 README、API、两个 Draft smoke 文档、STATUS、DECISIONS、KNOWN_ISSUES、WORKLOG 是否存在过期或矛盾口径。
- 明确 `docs/API_SMOKE_DRAFT_FLOW.md` 和 `docs/API_SMOKE_DRAFT_PIPELINE.md` 的关系。
- 不修改业务代码，不删除 legacy recognize，不做前端/后端重构。

结果：

- README 和 STATUS 已更新到第十六轮 release checkpoint：当前项目可启动、可验证、可继续开发，但不是生产可用。
- 当前主路径统一为 Dashboard Draft flow：`POST /api/v1/assets`、`POST /api/v1/drafts`、`POST /api/v1/drafts/{draft_id}/recognize`、`POST /api/v1/drafts/{draft_id}/save-to-bank`。
- `POST /api/v1/recognize` 和 `runLegacyRecognition()` 继续保留为 legacy / 兼容入口，不作为 Dashboard 当前主路径。
- `docs/API_SMOKE_DRAFT_FLOW.md` 标记为当前推荐 smoke 文档，负责主路径理解、异常契约、legacy 边界和人工/API smoke 验收。
- `docs/API_SMOKE_DRAFT_PIPELINE.md` 标记为脚本化 smoke 补充文档，负责 `scripts/smoke_draft_pipeline.ps1` 的执行参数和脚本断言说明。
- `docs/DECISIONS.md` 新增保留两个 smoke 文档并明确主次的决策。
- `docs/KNOWN_ISSUES.md` 已将 Draft 异常契约、Dashboard UI 状态、legacy 审计和 smoke 文档关系标为阶段性收口，同时保留非生产完成态、legacy 退场、批量 PDF、多页 Draft、真实第三方全量在线验证等风险。
- 未修改业务代码。

验证结果：

- `cd frontend && npm run test:auth-contract` 通过。
- `cd frontend && npm run test:stage3-contract` 通过。
- `cd frontend && npm run build` 通过，仅有 Vite chunk size warning。
- `cd backend && python -m compileall app` 通过。
- `cd backend && python -m unittest discover tests` 通过，`Ran 53 tests OK`。

边界：

- 未修改 `Dashboard.vue`。
- 未修改后端业务代码。
- 未删除 `/api/v1/recognize`。
- 未删除 `runLegacyRecognition()`。
- 未修改数据库模型或迁移文件。
- 未引入新依赖。
- 未做批量 PDF 或多页 Draft 功能。

## 2026-05-27 第十五轮：legacy recognize 引用审计与清理计划

目标：

- 审计 `runLegacyRecognition()`、`POST /api/v1/recognize`、Draft recognize 和 `save-to-bank` 相关引用。
- 确认 Dashboard 主上传流程仍走 Draft 主路径。
- 仅做 legacy 兼容注释和文档旧口径同步，不删除 legacy 入口。

结果：

- `confirmCropAndUpload()` 和 `uploadFullImage()` 仍调用 `runRecognition(file)`。
- `runRecognition(file)` 仍按 `POST /api/v1/assets`、`POST /api/v1/drafts`、`POST /api/v1/drafts/{draft_id}/recognize` 走 Draft 主路径。
- `runLegacyRecognition()` 仍存在并调用 `POST /api/v1/recognize`，但当前上传按钮和主上传流程不引用它；已增加 legacy 兼容注释。
- 后端 `POST /api/v1/recognize` 仍存在，未修改业务行为；已增加 legacy 兼容注释。
- `backend/tests/test_draft_pipeline.py` 覆盖 Draft 主路径和异常契约。
- `backend/tests/test_failure_paths.py` 仍覆盖 legacy `/api/v1/recognize` 失败路径。
- 已修正 `docs/API.md` 和 `docs/API_SMOKE_DRAFT_PIPELINE.md` 中旧的主路径口径。
- 已在 `docs/DECISIONS.md` 记录 legacy recognize 先审计标注、后续小步退场的策略。

验证结果：

- `cd frontend && npm run test:auth-contract` 通过。
- `cd frontend && npm run test:stage3-contract` 通过。
- `cd frontend && npm run build` 通过，仅有 Vite chunk size warning。
- `cd backend && python -m compileall app` 通过。
- `cd backend && python -m unittest discover tests` 通过，`Ran 53 tests OK`。

边界：

- 未删除 `runLegacyRecognition()`。
- 未删除 `/api/v1/recognize`。
- 未修改前端主流程。
- 未修改后端业务行为。
- 未修改数据库模型或迁移文件。

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
