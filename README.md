- Math Knowledge System

  一个面向高中数学错题管理的 OCR + LLM 知识点识别系统。

  当前状态：**v0.1 Release Candidate**。自动化检查已建立，真实百度 OCR + LLM 的至少 5 题人工 smoke 完成前，不视为正式发布。

  本项目支持用户上传数学题图片或 PDF，通过 OCR 提取题目文本，再调用大语言模型对 OCR 结果进行清洗、公式规范化和知识点标签识别，最终形成可编辑、可保存、可检索、可组卷的数学题库。

  ## 项目背景

  在高中数学错题整理场景中，学生或老师经常需要从试卷、练习册、截图中手动录入题目，并按照知识点进行分类。传统方式存在几个问题：

  - 手动录入效率低，尤其是包含公式、图形和复杂排版的题目；
  - OCR 识别结果容易出现数学符号错误、格式混乱；
  - 错题缺少结构化知识点标签，后续复习和组卷不方便；
  - 识别结果如果直接入库，错误数据会污染题库。

  因此，本项目设计了一个“上传 → OCR → LLM 清洗 → 草稿确认 → 保存入题库 → 组卷”的完整流程，重点解决数学题目从非结构化图片到结构化题库数据的转换问题。

  ## 功能特性

  ### 题目识别流程

  - 支持上传数学题图片；
  - 支持 PDF 页面转图片后识别；
  - 调用 OCR 服务提取原始题目文本；
  - 调用 LLM 对 OCR 文本进行纠错、公式规范化和知识点识别；
  - 支持识别结果进入 Draft 草稿态，用户确认后再保存入题库；
  - 避免未确认的 OCR/LLM 结果直接污染正式题库。

  ### 题库管理

  - 保存识别后的题目内容；
  - 记录题目对应的知识点标签；
  - 支持历史题目查看；
  - 支持题目内容编辑；
  - 为后续复习、筛选和组卷提供数据基础。

  ### 组卷能力

  - 支持从题库中选择题目生成试卷；
  - 保存试卷题目快照，避免后续题库题目修改影响历史试卷；
  - 为后续 Paper Preview / 试卷导出功能预留结构。

  ### 数学公式渲染

  - 前端支持 Markdown + LaTeX 渲染；
  - 对 LLM 输出中的公式分隔符进行统一规范化；
  - 支持行内公式和块级公式展示。

  ### 鉴权与用户隔离

  - 支持用户登录与 Token 鉴权；
  - 题目数据按用户进行隔离；
  - 管理员账号可用于开发和调试。

  ## 技术栈

  ### 前端

  - Vue 3
  - Vite
  - Element Plus
  - Axios
  - markdown-it
  - markdown-it-mathjax3
  - PDF.js / Cropper 相关组件

  ### 后端

  - FastAPI
  - SQLAlchemy
  - SQLite
  - Pydantic
  - Alembic
  - Python-Jose / Passlib
  - PyMuPDF
  - OCR 服务
  - OpenAI Compatible API / DeepSeek API

  ### 工程与测试

  - RESTful API
  - JWT 鉴权
  - 数据库迁移
  - 单元测试
  - Smoke Test
  - 前后端契约测试

  ## 系统流程

  ```text
  用户上传图片 / PDF 单页
          |
          v
  创建 Source Asset
          |
          v
  创建 Draft 草稿
          |
          v
  百度 OCR 识别原始文本
          |
          v
  LLM 清洗题目、规范公式、识别知识点
          |
          v
  用户检查并确认 Draft
          |
          v
  保存入题库
          |
          v
  题库管理 / 组卷 / 预览
  ```

  ## MVP Demo 与 Smoke

  - MVP 使用闭环 Demo 流程见：`docs/DEMO_FLOW.md`
  - 本地手动 smoke checklist 见：`docs/MVP_SMOKE_CHECKLIST.md`
  - v0.1 发布验收与签字清单见：`docs/MVP_RELEASE_CHECKLIST.md`
  - 本地 smoke 图片约定放在：`data/manual_smoke/ocr_images/`
  - 当前导出方案优先使用 PaperPreview 的浏览器打印或另存为 PDF；服务端 PDF/DOCX 导出尚未实现。

  生产路线固定使用“百度 OCR + DeepSeek/兼容 LLM + Draft 人工确认”。`OCR_PROVIDER=baidu` 是生产默认值。RapidOCR 代码只作为历史实验能力保留，不属于 v0.1 交付范围；除非真实客户需求或成本数据要求重新评估，否则不再继续迁移或比较本地 OCR。

  ## 核心设计

  ### 1. Draft 草稿机制

  本项目没有让 OCR 和 LLM 的输出直接进入正式题库，而是先进入 Draft 草稿态。

  这样设计的原因是：

  - OCR 结果可能存在错字、漏字、公式识别错误；
  - LLM 输出可能为空、格式异常或知识点标签不准确；
  - 用户需要在正式保存前确认题目内容；
  - 正式题库应该只保存经过确认的数据。

  Draft 流程使系统从“识别即入库”升级为“识别结果可审核后入库”，提高了数据质量和系统可靠性。

  ### 2. OCRRun / LLMRun 可观测记录

  系统在识别过程中记录 OCR 和 LLM 的运行结果，方便后续定位问题。

  例如：

  - OCR 是否返回空文本；
  - LLM 是否返回空内容；
  - LLM 输出是否符合 JSON 结构；
  - 当前 Draft 为什么失败；
  - 用户看到的结果来自 OCR 还是 LLM。

  这使系统在面对真实外部 API 异常时更容易调试，而不是只给用户一个模糊的“识别失败”。

  ### 3. 试卷题目快照

  组卷功能中，试卷题目会保存当时的题目快照。

  这样即使原题库中的题目后来被修改，已经生成的试卷内容也不会被破坏。这是为了保证历史试卷的稳定性和可追溯性。

  ## 本地运行

  ### 1. 克隆项目

  ```bash
  git clone https://github.com/wwending/math_knowledge_system.git
  cd math_knowledge_system
  ```

  ### 2. 启动后端

  ```bash
  cd backend
  python -m venv venv
  ```

  Windows PowerShell：

  ```powershell
  .\venv\Scripts\Activate.ps1
  python -c "import sys; print(sys.executable); print(sys.prefix)"
  python -m pip -V
  ```

  Linux / macOS：

  ```bash
  source venv/bin/activate
  ```

  安装依赖：

  ```bash
  python -m pip install -r requirements.txt
  ```

  从示例创建本地 `.env`：

  ```powershell
  Copy-Item .env.example .env
  ```

  Linux / macOS 使用 `cp .env.example .env`。随后编辑 `.env`，至少替换 `SECRET_KEY`，配置百度 OCR 与 DeepSeek/兼容 LLM 的真实密钥，并保持 `OCR_PROVIDER=baidu`。`.env.example` 中的占位值只用于说明字段，不能直接用于生产；`.env` 不得提交到 Git。

  执行数据库迁移：

  ```bash
  alembic upgrade head
  ```

  启动 FastAPI：

  ```bash
  python -m uvicorn app.main:app --reload
  ```

  后端默认运行在：

  ```text
  http://127.0.0.1:8000
  ```

  API 文档地址：

  ```text
  http://127.0.0.1:8000/docs
  ```

  ### 3. 启动前端

  ```bash
  cd frontend
  npm ci
  npm run dev
  ```

  前端默认运行在：

  ```text
  http://127.0.0.1:5173
  ```

  ## 常用接口

  | 功能         | 方法 | 路径                                     |
  | ------------ | ---- | ---------------------------------------- |
  | 健康检查     | GET  | `/api/v1/healthz`                        |
  | 用户登录     | POST | `/api/v1/auth/token`                     |
  | 获取当前用户 | GET  | `/api/v1/auth/me`                        |
  | 上传资源     | POST | `/api/v1/assets`                         |
  | 创建草稿     | POST | `/api/v1/drafts`                         |
  | 识别草稿     | POST | `/api/v1/drafts/{draft_id}/recognize`    |
  | 查看草稿     | GET  | `/api/v1/drafts/{draft_id}`              |
  | 保存入题库   | POST | `/api/v1/drafts/{draft_id}/save-to-bank` |
  | 查看历史题目 | GET  | `/api/v1/history`                        |
  | 创建试卷     | POST | `/api/v1/papers`                         |
  | 查看试卷详情 | GET  | `/api/v1/papers/{paper_id}`              |

  ## 项目结构

  ```text
  math_knowledge_system/
  ├── backend/
  │   ├── app/
  │   │   ├── api/              # API 路由
  │   │   ├── core/             # 配置、数据库、安全相关代码
  │   │   ├── models/           # SQLAlchemy 数据模型
  │   │   ├── schemas/          # Pydantic 请求/响应模型
  │   │   ├── services/         # OCR、LLM 等业务服务
  │   │   └── main.py           # FastAPI 入口
  │   ├── tests/                # 后端测试
  │   └── requirements.txt
  │
  ├── frontend/
  │   ├── src/
  │   │   ├── components/       # 前端组件
  │   │   ├── views/            # 页面视图
  │   │   ├── utils/            # Markdown / LaTeX 渲染工具
  │   │   └── main.ts
  │   └── package.json
  │
  ├── docs/                     # 项目文档
  └── README.md
  ```

  ## 测试

  后端测试必须使用 `backend/venv`：

  ```powershell
  cd backend
  .\venv\Scripts\Activate.ps1
  python -m compileall app
  python -m pytest
  python -m unittest discover tests
  ```

  前端契约测试与构建：

  ```bash
  cd frontend
  npm ci
  npm run test:stage3-contract
  npm run build
  ```

  ## 当前状态

  当前为 `v0.1 Release Candidate`，已具备：

  - 图片上传与 OCR 识别；
  - LLM 清洗与知识点识别；
  - Draft 草稿流程；
  - 识别结果保存入题库；
  - 题目历史记录展示；
  - Markdown / LaTeX 公式渲染；
  - 用户鉴权与数据隔离；
  - 组卷 MVP 后端能力；
  - 基础测试、前端契约验证与 GitHub Actions CI。

  发布前仍需人工完成：

  - 至少 5 张真实数学题图片的百度 OCR + LLM 全流程 smoke；
  - OCR/LLM 失败、风险二次确认、重复保存保护、用户数据隔离与组卷快照核对；
  - Paper Preview 浏览器打印或另存 PDF 验收；
  - 发布负责人在 `docs/MVP_RELEASE_CHECKLIST.md` 中签字确认。

  ## 客户反馈后评估

  v0.1 交付后停止无边界开发。以下方向不处于开发中，只有收到真实客户需求和优先级确认后才评估：

  - 按知识点筛选、错题复习计划和更精细的题目结构化字段；
  - 题库删除/回收站、Draft 历史恢复以及私有/共享/群组题库；
  - 服务端 PDF/DOCX 导出、复杂排版和移动端体验优化；
  - RapidOCR、PaddleOCR、Pix2Text 或其他 OCR 方案重新评估。

  ## 项目亮点

  - 将 OCR、LLM、题库和组卷流程串成完整业务闭环；
  - 使用 Draft 状态机降低错误识别结果直接入库的风险；
  - 对真实外部 API 异常进行可观测性设计；
  - 支持数学公式的规范化与前端渲染；
  - 通过题目快照保证历史试卷稳定性；
  - 具备前后端分离、鉴权、数据库建模、接口测试等完整 Web 工程实践。
