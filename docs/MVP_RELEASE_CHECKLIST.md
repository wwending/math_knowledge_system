# v0.1 MVP Release Checklist

本清单用于 `v0.1 Release Candidate` 的发布验收。自动化测试只使用 mock / fake，不调用真实百度 OCR、DeepSeek 或其他网络 API；真实识别质量必须由发布负责人手工验证。

## 1. 交付范围

生产主流程固定为：

```text
上传 → 百度 OCR → LLM 清洗 → Draft 确认 → 保存题库 → 组卷 → Paper Preview
```

- 生产默认 OCR：百度 OCR（`OCR_PROVIDER=baidu`）。
- LLM：DeepSeek 或兼容 OpenAI API 的服务。
- Draft 人工确认是正式入库前的必要步骤。
- RapidOCR 仅保留为历史实验代码，不属于 v0.1 交付范围。除非真实客户需求或成本数据要求重新评估，否则不再继续迁移或比较本地 OCR。
- 当前导出方式为 Paper Preview 中的浏览器打印或另存为 PDF；不包含服务端 PDF / DOCX 导出。

## 2. 自动检查

后端必须使用项目本地虚拟环境：

```powershell
cd backend
.\venv\Scripts\Activate.ps1
python -c "import sys; print(sys.executable); print(sys.prefix)"
python -m pip -V
python -m compileall app
python -m pytest
python -m unittest discover tests
```

期望 Python 路径为 `backend\venv\Scripts\python.exe`。

前端：

```powershell
cd frontend
npm ci
npm run test:stage3-contract
npm run build
```

发布前 Git 检查：

```powershell
git diff --check
git status -sb
```

## 3. 本地启动

后端：

```powershell
cd backend
.\venv\Scripts\Activate.ps1
Copy-Item .env.example .env
python -m pip install -r requirements.txt
alembic upgrade head
python -m uvicorn app.main:app --reload
```

前端（新终端）：

```powershell
cd frontend
npm ci
npm run dev
```

- 后端：`http://127.0.0.1:8000`
- API 文档：`http://127.0.0.1:8000/docs`
- 前端：`http://127.0.0.1:5173`

## 4. 环境变量检查

从 `backend/.env.example` 复制本地 `.env`，不要提交 `.env`。发布负责人逐项确认：

- [ ] `APP_ENV` 与部署环境一致。
- [ ] `DATABASE_URL` 指向预期数据库，且已执行 `alembic upgrade head`。
- [ ] `SECRET_KEY` 已替换为至少 32 位的安全随机值；示例值不得用于生产。
- [ ] `CORS_ALLOW_ORIGINS` 只包含实际前端来源。
- [ ] `OCR_PROVIDER=baidu`。
- [ ] `BAIDU_API_KEY` 与 `BAIDU_SECRET_KEY` 已在部署环境安全配置，未写入 Git。
- [ ] `DEEPSEEK_API_KEY` 已在部署环境安全配置，未写入 Git。
- [ ] 超时、Cookie、安全传输和注册开关符合部署环境。
- [ ] 生产环境未启用运行时 schema 变更。

## 5. 至少 5 张真实数学题图片 Smoke

真实图片、OCR 原文和完整报告不得提交到 Git。下表不预填通过结果；未执行项必须保持“待人工验证”。建议覆盖选择、填空、解答、公式密集、拍照噪声或复杂版面。

| # | 图片/题型（本地标识） | 上传 | 百度 OCR | LLM 清洗 | Draft 核对/编辑 | 保存题库 | 组卷/预览 | 结果 | 备注 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 待填写 | 待人工验证 | 待人工验证 | 待人工验证 | 待人工验证 | 待人工验证 | 待人工验证 | 待人工验证 | |
| 2 | 待填写 | 待人工验证 | 待人工验证 | 待人工验证 | 待人工验证 | 待人工验证 | 待人工验证 | 待人工验证 | |
| 3 | 待填写 | 待人工验证 | 待人工验证 | 待人工验证 | 待人工验证 | 待人工验证 | 待人工验证 | 待人工验证 | |
| 4 | 待填写 | 待人工验证 | 待人工验证 | 待人工验证 | 待人工验证 | 待人工验证 | 待人工验证 | 待人工验证 | |
| 5 | 待填写 | 待人工验证 | 待人工验证 | 待人工验证 | 待人工验证 | 待人工验证 | 待人工验证 | 待人工验证 | |

每题需人工比对原图、OCR 原文、LLM 清洗文本和最终 Draft，重点检查公式、变量、上下标、焦点编号、证明命题、选项数量及顺序。

## 6. 异常与保护验收

| 场景 | 验收标准 | 状态 | 备注 |
| --- | --- | --- | --- |
| OCR 失败/空文本 | Draft 不产生伪造内容；界面给出可理解提示；失败信息可追踪 | 待人工验证 | |
| LLM 超时/空内容/非法 JSON | 保留 OCR fallback，标记 `partial_success` 并提示人工核对 | 待人工验证 | |
| 识别质量风险 | 选项不完整、文本过短或 OCR/LLM 差异明显时展示风险提示 | 待人工验证 | |
| 风险二次确认 | 存在风险提示时，保存前弹出确认；取消后可继续编辑 | 待人工验证 | |
| 重复素材上传 | 同一用户重复上传同一图片时复用素材并允许新建 Draft | 待人工验证 | |
| 重复保存保护 | 已保存 Draft 再次保存返回 409，且不重复创建题目或 revision | 待人工验证 | |
| 用户数据隔离 | 普通用户不能读取或组卷其他用户题目；错误响应不泄露他人数据 | 待人工验证 | |
| 组卷快照 | 建卷后修改题库原题，既有 PaperItem 内容保持创建时快照 | 待人工验证 | |
| Paper Preview | 学生版可预览，且不返回答案与解析快照 | 待人工验证 | |
| 浏览器打印/另存 PDF | 预览可打印或另存 PDF，关键题目内容不缺失 | 待人工验证 | |

## 7. 已知非阻塞问题

- Vite 构建可能报告大于 500 kB 的 chunk warning；构建成功时记录但不在 v0.1 做大规模拆包。
- pytest 在部分受限 Windows 环境可能报告 `.pytest_cache` 无写权限 warning；测试通过时不影响结论。
- OCR 对公式、双栏选项、复杂版面和低质量拍照仍可能漏识别，必须依靠 Draft 人工确认。
- LLM 仍可能超时、返回空内容或改变数学语义；`partial_success` 和调试信息不能替代人工核对。
- 重复保存当前返回 409，不返回既有保存结果。
- `SourceAsset.sha256` 是全局唯一约束；不同用户上传完全相同文件仍是已知隔离边界。
- Paper Preview 不支持正式排版引擎级自动分页，当前仅使用浏览器打印/另存 PDF。
- 后台题型/难度任务依赖当前后端进程，进程重启可能丢失执行中的任务。

## 8. 发布签字

| 项目 | 填写内容 |
| --- | --- |
| 发布负责人 | 待填写 |
| 测试负责人 | 待填写 |
| 测试日期 | 待填写 |
| 自动检查结果 | 待填写 |
| 5 题真实 smoke 结果 | 待人工验证 |
| 最终结论（通过/不通过） | 待人工验证 |
| 备注/阻塞项 | 待填写 |

只有自动检查通过、至少 5 题真实 smoke 完成并由负责人确认后，才可合并发布 PR 并创建 `v0.1.0` 标签。
