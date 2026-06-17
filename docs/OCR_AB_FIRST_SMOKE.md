# OCR A/B First Smoke Summary

日期：2026-06-17

## 执行范围

- 输入目录：`D:\math_knowledge_system\data\manual_smoke\ocr_images`
- 图片数量：3
- 图片文件：
  - `smoke_ocr_001_interval_choice.png`
  - `smoke_ocr_002_parallel_line_blank.png`
  - `smoke_ocr_003_ellipse_solution.png`
- Providers：`baidu, rapidocr`
- LLM：未启用，命令未带 `--with-llm`
- 本地完整报告：`backend/reports/ocr_ab/ocr_ab_first_smoke.md`
- 本地结构化结果：`backend/reports/ocr_ab/ocr_ab_first_smoke.json`
- parser fix 后完整报告：`backend/reports/ocr_ab/ocr_ab_first_smoke_parser_fixed.md`
- parser fix 后结构化结果：`backend/reports/ocr_ab/ocr_ab_first_smoke_parser_fixed.json`
- parser fix 后 rapidocr-only 报告：`backend/reports/ocr_ab/rapidocr_smoke_after_parser_fix.md`
- parser fix 后 rapidocr-only JSON：`backend/reports/ocr_ab/rapidocr_smoke_after_parser_fix.json`

说明：本文件只记录摘要，不粘贴完整 OCR 原文。本地完整报告和 JSON 结果属于真实评测产物，保留在已忽略目录中，不提交。

## 运行结果摘要

第二十八点五轮首次运行时，RapidOCR 因缺少 `onnxruntime` 未能产出 OCR 文本。第二十八点七轮补齐运行依赖并修复 RapidOCR 3.8.4 返回结构解析后，重新运行结果如下：

| 图片 | baidu | baidu 耗时 | baidu 文本长度 | baidu 风险提示 | rapidocr | rapidocr 耗时 | rapidocr 文本长度 | rapidocr 风险提示 |
| --- | --- | ---: | ---: | --- | --- | ---: | ---: | --- |
| `smoke_ocr_001_interval_choice.png` | 成功 | 1320 ms | 74 | `choice_options_incomplete` | 成功 | 2824 ms | 43 | 无 |
| `smoke_ocr_002_parallel_line_blank.png` | 成功 | 930 ms | 326 | `choice_options_incomplete` | 成功 | 2523 ms | 87 | `choice_options_incomplete` |
| `smoke_ocr_003_ellipse_solution.png` | 成功 | 1430 ms | 291 | `choice_options_incomplete` | 成功 | 2134 ms | 95 | 无 |

## 初步观察

- Baidu OCR 在 3 张 smoke 图片上均成功返回文本，耗时约 0.9 到 1.4 秒。
- RapidOCR 在 3 张 smoke 图片上均成功返回文本，耗时约 2.1 到 2.8 秒。
- RapidOCR 的 `unsupported result format` 已由第二十八点七轮解析器修复解决。
- RapidOCR 文本长度明显短于 Baidu，不能直接认定识别质量可用；需要人工对照原图和完整报告判断是否漏题、漏选项或漏版面内容。
- Baidu 3 张均触发 `choice_options_incomplete`；RapidOCR 仅第二张触发该提示，但这不等于另外两张一定完整，只说明当前启发式未触发。

## 边界

- 未启用 LLM，因此本轮不评价 LLM 清洗、保真整理或知识点标签结果。
- 未修改默认 `OCR_PROVIDER`，默认仍为 `baidu`。
- 未修改 Draft recognize API、legacy `/api/v1/recognize`、前端或数据库模型。
- 未提交 `backend/reports/ocr_ab/ocr_ab_first_smoke.md` 和 `backend/reports/ocr_ab/ocr_ab_first_smoke.json`。
- 未提交 parser fix 后生成的 `backend/reports/ocr_ab/rapidocr_smoke_after_parser_fix.*` 和 `backend/reports/ocr_ab/ocr_ab_first_smoke_parser_fixed.*`。

## 后续建议

- 人工逐题查看 parser fix 后完整报告和原图，重点核对 RapidOCR 是否漏掉选项、条件、公式或解答步骤。
- 如果继续评估 RapidOCR，应保持不带 `--with-llm`，先单独比较 OCR 层输出。
