# OCR Evaluation

## 目标

第二十二轮先建立 OCR 评估集和评估指标基础，而不是直接接入 RapidOCR、PaddleOCR 或 Pix2Text。

原因：

- 先有可重复评估标准，再比较不同 OCR provider，避免凭一次人工观感切换方案。
- 当前百度 OCR 成本问题需要后续解决，但替换 OCR 引擎前必须知道质量、耗时和失败率如何比较。
- 本轮评估是离线工具，只比较已有 `predicted_text` 与人工标准答案，不调用真实 OCR provider。

## Eval Case JSON

文件示例：`backend/tests/fixtures/ocr_eval_cases.json`

字段：

- `case_id`：样本 ID。
- `image_path`：图片路径。当前可以是占位路径，单元测试不要求真实存在。
- `expected_text`：人工标注的标准 OCR 文本。
- `category`：题目类别，例如 `algebra`、`geometry`、`function`、`choice`、`proof`。
- `difficulty`：可选难度，建议 1-5。
- `required_terms`：关键术语或公式片段列表，用于粗略衡量关键内容召回。
- `notes`：可选说明。

## Prediction JSON

文件示例：`backend/tests/fixtures/ocr_eval_predictions.json`

字段：

- `case_id`：关联 eval case。
- `provider`：输出来源，例如 `baidu`、`rapidocr`、`paddleocr`、`pix2text`。
- `predicted_text`：该 provider 已生成的 OCR 文本。
- `latency_ms`：离线记录的识别耗时，单位毫秒。
- `error`：可选错误信息；有错误时仍会生成评估记录，但会计入 error 统计。

## 当前指标

`backend/app/services/ocr_evaluation.py` 提供：

- `normalize_ocr_text(text)`：压缩多余空白、换行和制表符。
- `evaluate_ocr_prediction(expected_text, predicted_text, required_terms)`：评估单条预测。
- `evaluate_ocr_batch(cases, predictions)`：按 provider 汇总离线预测结果。

指标含义：

- `exact_match`：原始文本完全一致。
- `normalized_exact_match`：归一化空白后完全一致。
- `similarity_ratio`：基于 `difflib.SequenceMatcher` 的文本相似度。
- `length_delta`：预测文本长度减标准文本长度。
- `required_terms_total`：关键术语总数。
- `required_terms_hit`：预测文本命中的关键术语数量。
- `required_terms_recall`：关键术语召回率。
- `error`：prediction 错误或缺失 prediction 的明确标记。

## 局限

当前指标只是文本级初步评估，不是最终数学语义评估。

明确不能覆盖：

- 数学公式语义等价，例如 `x^2-1` 与 `(x-1)(x+1)`。
- 几何图形、辅助线、坐标系、图中文字位置关系。
- 题目版面结构、分栏、表格、选项排版。
- OCR 后 LLM 清洗、纠错和 LaTeX 规范化的整体效果。

## 后续用法

后续接入本地 OCR provider 时，可以按以下流程比较：

1. 准备真实高中数学题图片，但不要把大图片提交进 Git。
2. 人工标注 `expected_text`，生成 eval case JSON。
3. 分别运行 baidu / rapidocr / paddleocr / pix2text，保存各自 prediction JSON。
4. 使用 `evaluate_ocr_batch()` 离线比较文本相似度、关键术语召回、错误数和耗时。
5. 再结合人工抽检决定 provider 默认值和 fallback 策略。

真实评估图片后续可以放在本地目录或对象存储中，Git 仓库只保留轻量 JSON、脚本和文档。

## OCR Provider A/B Smoke 脚本

第二十八轮新增手工评测脚本：

`backend/scripts/evaluation/compare_ocr_providers.py`

用途：

- 用同一批图片分别运行 `baidu`、`rapidocr` 或指定 provider。
- 输出 Markdown 报告，必要时额外输出 JSON 结果。
- 默认只运行 OCR 和 `quality_warnings`，不调用 LLM。
- 只有显式传入 `--with-llm` 时才调用现有 LLM 清洗服务。
- 某个 provider、某张图片或 LLM 调用失败时，只记录失败信息，不中断整批评测。

从 `backend/` 目录运行：

```bash
python scripts/evaluation/compare_ocr_providers.py \
  --input static/uploads_test \
  --providers baidu,rapidocr \
  --output reports/ocr_ab/ocr_ab_smoke.md
```

Windows PowerShell 示例：

```powershell
python scripts/evaluation/compare_ocr_providers.py `
  --input static/uploads_test `
  --providers baidu,rapidocr `
  --output reports/ocr_ab/ocr_ab_smoke.md
```

可选 JSON 输出：

```bash
python scripts/evaluation/compare_ocr_providers.py \
  --input static/uploads_test \
  --providers baidu,rapidocr \
  --output reports/ocr_ab/ocr_ab_smoke.md \
  --json-output reports/ocr_ab/ocr_ab_smoke.json
```

只评测单个 provider：

```bash
python scripts/evaluation/compare_ocr_providers.py \
  --input static/uploads_test \
  --providers rapidocr \
  --output reports/ocr_ab/rapidocr_smoke.md
```

带 LLM 清洗：

```bash
python scripts/evaluation/compare_ocr_providers.py \
  --input static/uploads_test \
  --providers baidu,rapidocr \
  --output reports/ocr_ab/ocr_ab_smoke_with_llm.md \
  --with-llm
```

输入规则：

- `--input` 可以是单张图片，也可以是目录。
- 目录模式只收集 `.jpg`、`.jpeg`、`.png`、`.webp`。
- 图片按文件名排序后执行，保证结果可复跑。

报告规则：

- Markdown 报告包含运行信息、汇总表和每张图片的 provider 详情。
- 每条结果保留 `manual_conclusion` 和 `notes` 空字段，供人工复核后填写。
- `manual_conclusion` 建议值：`usable`、`partially_usable`、`unusable`、`need_crop`、`need_manual_fix`。
- `backend/reports/ocr_ab/` 已加入 `.gitignore`，真实 smoke 报告默认不提交；如后续需要入库，应先人工确认图片、文本和第三方输出中没有敏感内容。
