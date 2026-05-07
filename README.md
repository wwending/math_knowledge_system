# Math Knowledge System

当前项目已完成第七轮后端旁路正式流水线最小竖切，状态定位为：可启动、可验证、可继续开发。不要把当前状态表述为生产可用。

当前主链路仍是 `POST /api/v1/recognize`。Draft 流水线已经具备后端旁路接口，但 `Dashboard.vue` 尚未切换到 Draft 流水线；`/api/v1/recognize` 未删除、未重构，仍是当前 MVP 主入口。

## 当前验证结果

第七轮后端旁路正式流水线最小竖切后的本地验证结果：

| 范围 | 命令 | 结果 |
| --- | --- | --- |
| frontend | `npm run build` | 通过，仅有 Vite chunk size warning |
| frontend | `npm run test:auth-contract` | 通过 |
| frontend | `npm run test:stage3-contract` | 通过 |
| backend | `python -m compileall app` | 通过 |
| backend | `python -m unittest discover tests` | 通过，`Ran 38 tests OK` |

## 后端旁路 Draft 流水线

第七轮新增后端旁路正式流水线接口：

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

边界：

- Draft 流水线目前是后端旁路能力。
- 当前前端主链路仍然是 `/api/v1/recognize`。
- `Dashboard.vue` 尚未切换到 Draft 流水线。
- `/api/v1/recognize` 未删除、未重构，仍是当前 MVP 主入口。
- 当前不表述为生产可用，也不表述为完整多页 PDF 或批量 draft 能力已完成。

依赖与配置收口：

- `backend/requirements.txt` 已补齐 `passlib[bcrypt]`。
- `frontend/package.json` 已显式声明 `@element-plus/icons-vue`。
- `backend/.env` 是本地文件，不应提交。
- 示例配置使用 [backend/.env.example](/d:/math_knowledge_system/backend/.env.example)。

## 启动前置

后端启动和管理员初始化之前，`alembic upgrade head` 是硬前置。不要依赖运行时 `create_all` 或兼容补表替代正式迁移链。

后端依赖安装：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r backend\requirements.txt
```

创建本地后端配置：

```powershell
Copy-Item backend\.env.example backend\.env
```

执行迁移：

```powershell
cd backend
..\.venv\Scripts\python.exe -m alembic upgrade head
```

初始化管理员：

```powershell
cd backend
..\.venv\Scripts\python.exe -m app.scripts.create_admin --phone 13800000000 --password "AdminPass123!" --display-name "Super Admin"
```

说明：

- 管理员初始化路径为 `app.scripts.create_admin`。
- 管理员脚本会创建或升级该账号为 `super_admin`。
- 新用户优先通过管理员界面或管理员 API 创建。
- 公开注册只作为 demo/staging 可开能力，由 `PUBLIC_SIGNUP_ENABLED` 控制；正式环境默认不开放。

## 启动方式

后端：

```powershell
cd backend
..\.venv\Scripts\python.exe -m alembic upgrade head
..\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

前端：

```powershell
cd frontend
npm install
npm run dev
```

## 最小验证

前端：

```powershell
cd frontend
npm run test:auth-contract
npm run test:stage3-contract
npm run build
```

后端：

```powershell
cd backend
..\.venv\Scripts\python.exe -m compileall app
..\.venv\Scripts\python.exe -m unittest discover tests
```

后端验证必须使用已安装 `backend/requirements.txt` 的 Python 环境。

## 当前能力边界

- 当前主链路是 `/api/v1/recognize`。
- Draft 流水线已有后端旁路最小竖切，但尚未接入主前端。
- `/upload_pdf`、`/assets`、draft 流水线目前不是主前端闭环。
- 真实第三方失败场景尚未形成系统化在线验证矩阵。
- 当前验证证明项目可启动、可验证、可继续开发，不代表生产可用。

## 下一阶段优先级

下一阶段不要做大重构，优先处理：

- 前端中文乱码。
- API smoke 文档或前端接入方案评估。
- mock/legacy 文件清理。
- 后端测试稳定性。
