# MVP Smoke Checklist

本文档用于本地手动 smoke，不用于自动化测试。真实图片由用户放在本地目录，不提交到 Git。

## 图片放置位置

```text
data/manual_smoke/ocr_images/
```

约定文件名：

```text
smoke_ocr_001_interval_choice.png
smoke_ocr_002_parallel_line_blank.png
smoke_ocr_003_ellipse_solution.png
```

可选地将人工记录或 provider 输出草稿放在本地目录：

```text
data/manual_smoke/predictions/
```

上述目录已加入 `.gitignore`。

## 样例 1：区间选择题

文件：`smoke_ocr_001_interval_choice.png`

元信息：

- 类型：选择题
- 内容：倾斜角取值范围，含直线方程、距离符号、π 区间选项
- `formula_density`: `high`
- `has_diagram`: `false`
- `image_quality`: `clean_pdf`

检查项：

- [ ] 能上传
- [ ] 同一张 smoke 图片重复上传时，系统复用已有素材并继续创建 Draft
- [ ] 能创建 Draft
- [ ] 能 recognize
- [ ] 能看到 OCR/LLM 后的文本
- [ ] 能展开“识别调试信息”，比较原始 OCR 文本和 LLM 清洗文本
- [ ] 如果 A/B/C/D 选项缺失，能看到“识别风险提示”
- [ ] 存在识别风险提示时，保存入题库前会弹出确认
- [ ] 用户确认后仍可保存入题库
- [ ] A/B/C/D 选项没有被 LLM 删除或改写
- [ ] 能手动编辑草稿
- [ ] 能保存到题库
- [ ] 能从题库创建试卷
- [ ] 能进入试卷预览
- [ ] 能打印或浏览器另存为 PDF
- [ ] 出错时有可理解提示

## 样例 2：平行直线填空题

文件：`smoke_ocr_002_parallel_line_blank.png`

元信息：

- 类型：填空题
- 内容：两条直线平行，求实数 m
- `formula_density`: `medium`
- `has_diagram`: `false`
- `image_quality`: `clean_pdf`

检查项：

- [ ] 能上传
- [ ] 同一张 smoke 图片重复上传时，系统复用已有素材并继续创建 Draft
- [ ] 能创建 Draft
- [ ] 能 recognize
- [ ] 能看到 OCR/LLM 后的文本
- [ ] 能展开“识别调试信息”，比较原始 OCR 文本和 LLM 清洗文本
- [ ] 公式变量和指数没有被 LLM 改写，例如 `m^2y + 6` 不应被改成 `my + b`
- [ ] 能手动编辑草稿
- [ ] 能保存到题库
- [ ] 能从题库创建试卷
- [ ] 能进入试卷预览
- [ ] 能打印或浏览器另存为 PDF
- [ ] 出错时有可理解提示

## 样例 3：椭圆解答题

文件：`smoke_ocr_003_ellipse_solution.png`

元信息：

- 类型：解答/证明题
- 内容：椭圆方程、焦点、面积最大值、两问证明
- `formula_density`: `high`
- `has_diagram`: `false`
- `image_quality`: `clean_pdf`

检查项：

- [ ] 能上传
- [ ] 同一张 smoke 图片重复上传时，系统复用已有素材并继续创建 Draft
- [ ] 能创建 Draft
- [ ] 能 recognize
- [ ] 能看到 OCR/LLM 后的文本
- [ ] 能展开“识别调试信息”，比较原始 OCR 文本和 LLM 清洗文本
- [ ] 焦点编号、线段名和证明命题没有被 LLM 改写，例如 `AF1` 不应被改成 `AF2`
- [ ] `|F1A|·|F1B|/|AB|` 不应被改写成其他不同命题
- [ ] 能手动编辑草稿
- [ ] 能保存到题库
- [ ] 能从题库创建试卷
- [ ] 能进入试卷预览
- [ ] 能打印或浏览器另存为 PDF
- [ ] 出错时有可理解提示

## 记录建议

每次手动 smoke 建议记录：

- 测试日期和操作者
- 使用的图片文件名
- OCR 是否成功
- 原始 OCR 文本是否已经偏离原图
- LLM 是否成功，是否出现 `partial_success`
- LLM 清洗文本是否相对 OCR 原文改写了题意
- 是否出现 `quality_warnings`，尤其是选择题选项缺失和选项顺序异常
- 存在风险提示时保存入题库是否弹出确认
- 主要 OCR 错误，例如公式、符号、换行、选项、中文漏识别
- 主要 LLM 保真问题，例如删选项、替换变量、改焦点编号、改证明命题
- 是否成功保存入题库
- 是否成功创建试卷和预览
- 浏览器打印或另存为 PDF 是否可用
- 需要后续修复的 bug

## 当前边界

- 当前 OCR 默认仍是 `baidu`。
- 本地 OCR 尚未接入。
- 当前样例来自 PDF 截图，不覆盖真实拍照噪声、倾斜、阴影、手写批注或低清晰度场景。
- 自动化测试不读取这些真实图片。
- 识别风险提示只是保存前校验，不代表 OCR 已修复双栏选项漏识别。
- 本地 smoke 的导出验证用浏览器打印或另存为 PDF；服务端 PDF 导出属 Docker 部署栈能力，验收见 `MVP_RELEASE_CHECKLIST`；DOCX 尚未实现。
