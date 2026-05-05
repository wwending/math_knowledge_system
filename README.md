# Math Knowledge System

当前项目已完成第二轮修复收口，状态定位为：可启动、可验证、可继续开发。不要把当前状态表述为生产可用。

当前主链路仍是 `POST /api/v1/recognize`。`assets`、`drafts`、`ocr_runs`、`llm_runs` 等对象已经建模，用作正式流水线预留，但尚未形成主前端闭环。`/upload_pdf`、`/assets`、draft 流水线目前未接入主前端。

## 当前验证结果

第二轮修复后的本地验证结果：

| 范围 | 命令 | 结果 |
| --- | --- | --- |
| frontend | `npm run build` | 通过，仅有 Vite chunk size warning |
| frontend | `npm run test:auth-contract` | 通过 |
| frontend | `npm run test:stage3-contract` | 通过 |
| backend | `python -m compileall app` | 通过 |
| backend | `python -m unittest discover tests` | 通过，`Ran 36 tests OK` |

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
- `assets/drafts/ocr_runs/llm_runs` 是已建模但未前端闭环的正式流水线预留。
- `/upload_pdf`、`/assets`、draft 流水线目前未接入主前端。
- 真实第三方失败场景尚未形成系统化在线验证矩阵。
- 当前验证证明项目可启动、可验证、可继续开发，不代表生产可用。

## 下一阶段优先级

下一阶段不要做大重构，优先处理：

- 前端中文乱码。
- 主链路决策：继续以 `/api/v1/recognize` 为主，还是切换到 draft 流水线。
- mock/legacy 文件清理。
- 后端测试稳定性。
