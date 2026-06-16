# MVP Demo Flow

本文档用于本地演示一次 MVP 使用闭环：本地 smoke 图片上传，Draft 识别和编辑，保存入题库，从题库创建试卷，打开试卷预览，并通过浏览器打印或另存为 PDF。

## 前置条件

- 后端依赖已安装，数据库迁移已执行到最新版本。
- 前端依赖已安装。
- 已有可登录账号，或已按 README 初始化测试账号。
- 本地 smoke 图片放在 `data/manual_smoke/ocr_images/`。
- 当前 OCR 默认仍是 `baidu`，本地 OCR 尚未接入。
- 当前 smoke 图片来自本地 PDF 截图，真实样本集尚未建立。
- 服务端 PDF/DOCX 导出尚未实现，当前导出方案优先使用浏览器打印或另存为 PDF。

## 本地 Smoke 图片

用户手动准备 3 张 PDF 截图数学题图片，不提交到 Git：

```text
data/manual_smoke/ocr_images/
  smoke_ocr_001_interval_choice.png
  smoke_ocr_002_parallel_line_blank.png
  smoke_ocr_003_ellipse_solution.png
```

如目录不存在，可在本地创建：

```powershell
New-Item -ItemType Directory -Force data/manual_smoke/ocr_images
```

## 启动后端

```powershell
cd backend
python -m uvicorn app.main:app --reload
```

后端默认地址：

```text
http://127.0.0.1:8000
```

## 启动前端

```powershell
cd frontend
npm run dev
```

前端默认地址：

```text
http://127.0.0.1:5173
```

## Demo 步骤

1. 打开前端页面并登录，或使用当前本地测试账号登录。
2. 进入题目录入入口。
3. 上传 `data/manual_smoke/ocr_images/` 下的一张 smoke 图片。
4. 确认上传后创建 Draft。
5. 执行 recognize，等待 OCR + LLM 返回结果。
6. 检查 OCR/LLM 后的题目文本和知识点标签。
7. 如有错字、公式或排版问题，手动编辑草稿内容。
8. 点击保存入题库。
9. 进入题库，选择已保存题目并创建试卷。
10. 进入组卷中心，打开试卷详情。
11. 点击预览作业，生成试卷预览。
12. 点击“打印/导出 PDF”，使用浏览器打印或另存为 PDF。

## 验收口径

- Draft 主流程能从上传走到 `draft_ready`。
- 用户能在保存前看到并编辑识别结果。
- 保存入题库后，题目能被选择并创建试卷。
- 试卷预览能打开，内容来自 PaperRenderModel。
- 浏览器打印或另存为 PDF 能作为当前 MVP 导出方案。
- 出错时前端应展示可理解提示。

## 非目标

- 不接入 RapidOCR、PaddleOCR、Pix2Text 或其他本地 OCR。
- 不扩展 OCR 评估集。
- 不提交真实 smoke 图片。
- 不调用真实 OCR API 做自动化测试。
- 不修改 Draft recognize 主流程。
- 不修改 legacy `/api/v1/recognize`。
- 不实现服务端 PDF/DOCX 导出。
