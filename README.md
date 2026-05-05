# Math Knowledge System

当前仓库已完成鉴权生产化改造的阶段 3 收口，前后端统一切到手机号登录、`access token + refresh session` 会话体系。公开注册能力仍然保留，但只定义为 demo/staging 可开启能力，由后端 `PUBLIC_SIGNUP_ENABLED` 与 `/api/v1/auth/capabilities` 统一驱动；正式环境默认不开放。

详细鉴权基线见 [docs/auth-backend-stage2.md](/d:/math_knowledge_system/docs/auth-backend-stage2.md)，发布前人工验收见 [docs/auth-acceptance-checklist.md](/d:/math_knowledge_system/docs/auth-acceptance-checklist.md)。

## 当前真相源

- [README.md](/d:/math_knowledge_system/README.md)：启动方式、最小回归测试、发布前最小门禁、当前能力边界。
- [docs/STATUS.md](/d:/math_knowledge_system/docs/STATUS.md)：当前阶段状态、当前发布门禁、当前文档职责边界。
- [docs/auth-acceptance-checklist.md](/d:/math_knowledge_system/docs/auth-acceptance-checklist.md)：发布前必须执行的人工检查项。
- [docs/KNOWN_ISSUES.md](/d:/math_knowledge_system/docs/KNOWN_ISSUES.md)：当前已知未解决边界与风险。
- [docs/DECISIONS.md](/d:/math_knowledge_system/docs/DECISIONS.md)：为什么采用当前治理方案。
- [docs/WORKLOG.md](/d:/math_knowledge_system/docs/WORKLOG.md)：按时间记录做了什么，不承载当前真相。
- [docs/DELIVERY_2026-03-19.md](/d:/math_knowledge_system/docs/DELIVERY_2026-03-19.md)：历史快照，不代表当前发布结论。
- [docs/auth-production-plan.md](/d:/math_knowledge_system/docs/auth-production-plan.md)：历史设计稿，用于理解演进背景，不作为当前状态或发布门禁依据。

## 当前鉴权行为

- 登录入口：`POST /api/v1/auth/login`
- 兼容旧入口：`POST /api/v1/auth/token`
- 会话续期：`POST /api/v1/auth/refresh`
- 当前用户：`GET /api/v1/auth/me`
- 自助改密：`POST /api/v1/auth/change-password`
- 登出：`POST /api/v1/auth/logout`
- 管理员用户管理：
  - `GET /api/v1/admin/users`
  - `POST /api/v1/admin/users`
  - `PATCH /api/v1/admin/users/{id}/status`
  - `PATCH /api/v1/admin/users/{id}/role`
  - `POST /api/v1/admin/users/{id}/reset-password`
- 公开注册：
  - 路由保留为 `POST /api/v1/auth/register`
  - 是否开放由 `PUBLIC_SIGNUP_ENABLED` 控制
  - 前端登录页入口与 `/register` 可达性由 `GET /api/v1/auth/capabilities` 驱动
  - demo/staging 可按需开启，正式环境默认关闭
- 自助找回密码：
  - 当前不开放
  - 前后端统一提示“联系管理员重置”
  - 已预留短信相关能力开关，但默认关闭

## 环境变量

后端建议在 `backend/.env` 配置：

```env
APP_ENV=development
DATABASE_URL=sqlite:///./math_knowledge.db
SECRET_KEY=请替换为至少 32 位的真实密钥
CORS_ALLOW_ORIGINS=http://localhost:5173

ACCESS_TOKEN_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_DAYS=14
REFRESH_TOKEN_COOKIE_NAME=refresh_token
REFRESH_TOKEN_COOKIE_PATH=/
AUTH_STRICT_SECURITY=false
SECURE_TRANSPORT_MODE=insecure_http
ALLOW_CROSS_SITE_REFRESH_COOKIE=false
REFRESH_TOKEN_COOKIE_SECURE=false
REFRESH_TOKEN_COOKIE_SAMESITE=lax

PUBLIC_SIGNUP_ENABLED=false
SMS_CODE_LOGIN_ENABLED=false
SMS_PASSWORD_RECOVERY_ENABLED=false
PASSWORD_RECOVERY_MODE=admin_contact

LOGIN_RATE_LIMIT_WINDOW_SECONDS=900
LOGIN_RATE_LIMIT_MAX_ATTEMPTS=5
LOGIN_RATE_LIMIT_BLOCK_SECONDS=1800

ALLOW_RUNTIME_SCHEMA_MUTATIONS=false
AUTO_CREATE_TABLES=false
AUTO_APPLY_LEGACY_QUESTION_COMPAT=false
```

严格模式要求：

- `APP_ENV=production`
- 或显式设置 `AUTH_STRICT_SECURITY=true`
- `SECRET_KEY` 不能使用默认值，且长度至少 32 位
- `CORS_ALLOW_ORIGINS` 不能为 `*`
- `REFRESH_TOKEN_COOKIE_NAME` 不能为空
- `REFRESH_TOKEN_COOKIE_PATH` 必须以 `/` 开头
- `REFRESH_TOKEN_COOKIE_SECURE=true`
- `SECURE_TRANSPORT_MODE` 必须为 `direct_https` 或 `trusted_proxy_tls`
- `REFRESH_TOKEN_COOKIE_SAMESITE` 默认只允许 `lax` 或 `strict`
- 若使用 `REFRESH_TOKEN_COOKIE_SAMESITE=none`，必须同时配置：
  - `ALLOW_CROSS_SITE_REFRESH_COOKIE=true`
  - `REFRESH_TOKEN_COOKIE_SECURE=true`
  - `SECURE_TRANSPORT_MODE=direct_https` 或 `trusted_proxy_tls`
- 正式建表必须走 Alembic，不依赖运行时 schema 兜底

前端可选环境变量：

```env
VITE_API_BASE_URL=http://127.0.0.1:8000
VITE_API_V1_PREFIX=/api/v1
VITE_STATIC_URL_PREFIX=/static
```

## 初始化管理员

1. 安装依赖

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r backend\requirements.txt
```

2. 执行数据库迁移

```powershell
cd backend
..\.\venv\Scripts\python.exe -m alembic upgrade head
cd ..
```

3. 初始化管理员

```powershell
.\.venv\Scripts\python.exe -m backend.app.scripts.create_admin --phone 13800000000 --password "AdminPass123!" --display-name "Super Admin"
```

说明：

- 管理员脚本会创建或升级该账号为 `super_admin`
- 新创建用户统一通过管理员用户管理界面或管理员 API 创建
- 如需演示公开注册，可在 demo/staging 环境将 `PUBLIC_SIGNUP_ENABLED=true`
- 正式环境默认不开放公开注册，也不开放短信找回

## 启动方式

后端：

```powershell
uvicorn --app-dir backend app.main:app --reload
```

前端：

```powershell
cd frontend
npm install
npm run dev
```

## 迁移流程

新增数据库结构时必须：

1. 先在 `backend/app/models` 增加正式模型
2. 再在 `backend/alembic/versions` 增加迁移脚本
3. 本地执行 `alembic upgrade head`
4. 运行最小回归测试与最小人工验收后再发布

运行时兼容边界：

- production 环境无条件禁止运行时 schema 变更
- 非 production 环境只有在 `ALLOW_RUNTIME_SCHEMA_MUTATIONS=true` 时，`AUTO_CREATE_TABLES` 与 `AUTO_APPLY_LEGACY_QUESTION_COMPAT` 才允许生效
- `AUTO_CREATE_TABLES` 与 `AUTO_APPLY_LEGACY_QUESTION_COMPAT` 只是本地开发或受限兼容窗口的兜底，不是正式部署路径

本阶段新增的正式迁移：

- `backend/alembic/versions/20260319_0001_auth_production_baseline.py`
- `backend/alembic/versions/20260320_0002_auth_audit_and_rate_limit.py`

## 最小回归测试矩阵

| 风险类别 | 必跑命令 | 主要覆盖 |
| --- | --- | --- |
| 前端 capability 与注册关闭态 | `npm run test:auth-contract` | `public_signup_enabled` 单一真相源、`/register` 守卫、capability 失败降级 |
| 前端会话与管理员入口契约 | `npm run test:stage3-contract` | 登录/refresh/logout/change-password 契约、管理员用户管理入口与提示文案 |
| 前端可交付构建 | `npm run build` | 打包可成功完成，交付物可生成 |
| 后端迁移链、严格安全、限流、审计 | `python -m unittest backend.tests.test_auth_stage3 -v` | fresh DB + Alembic、严格配置硬约束、登录限流、审计事件 |
| 后端管理员治理与会话流 | `python -m unittest backend.tests.test_auth_system -v` | refresh/logout、管理员创建用户、强制改密、禁用/角色边界、会话失效 |
| 后端失败路径语义 | `python -m unittest backend.tests.test_failure_paths -v` | 未登录/无效 token/过期 token、OCR/LLM 失败与 `partial_success` 语义 |

说明：

- 后端测试必须在已安装 `backend/requirements.txt` 的 Python 环境中执行，不要用未安装依赖的裸解释器。
- `backend.tests.test_auth_stage3` 与 `backend.tests.test_auth_system` 都会验证迁移后的数据库行为，不允许以 `create_all` 代替正式迁移链。
- `backend.tests.test_failure_paths` 主要是 stub/monkeypatch 级验证，证明本地失败分支语义，不等于真实第三方在线异常已全量验完。

## 最小发布门禁

发布前按以下顺序执行，任一步失败即阻断发布：

1. 在前端目录执行：

```powershell
npm run test:auth-contract
npm run test:stage3-contract
npm run build
```

2. 在已安装后端依赖的 Python 环境执行：

```powershell
python -m unittest backend.tests.test_auth_stage3 -v
python -m unittest backend.tests.test_auth_system -v
python -m unittest backend.tests.test_failure_paths -v
```

3. 在目标预发布环境执行 Alembic：

```powershell
cd backend
..\.\venv\Scripts\python.exe -m alembic upgrade head
cd ..
```

4. 按 [docs/auth-acceptance-checklist.md](/d:/math_knowledge_system/docs/auth-acceptance-checklist.md) 完成最小人工 smoke：
   - 管理员登录
   - `me` / refresh / logout
   - 管理员创建用户并验证强制改密
   - 禁用用户后旧会话失效
   - demo/staging 如开启公开注册，验证 capability 驱动；未开启时验证关闭态

## 阻断发布条件

以下任一情况成立，直接阻断发布：

- 任一必跑命令失败
- 目标环境未先执行 `alembic upgrade head`
- 目标环境依赖运行时 schema 兜底而不是正式迁移
- 最小人工 smoke 未通过
- 当前真相源文档仍存在相互冲突的交付结论
- 将 demo/staging 的公开注册能力误写成正式环境默认策略

## 回滚边界

- 前端问题优先回滚前端静态资源
- 后端逻辑问题且数据库结构未破坏时，优先回滚应用版本
- 若必须回滚迁移，先确认 `auth_audit_logs` 与 `login_rate_limits` 是否有需要保留的数据，再执行 `alembic downgrade`
- 不要通过手工删表、删列或临时改表替代正式迁移回滚

## 当前能力边界

- 公开注册仍不是正式默认策略，只是 demo/staging 可开启能力
- 正式开放公开注册仍缺少防刷、审计和身份验证能力
- 真实第三方失败场景在线烟雾测试尚未系统完成
- 当前发布门禁是“当前 demo 阶段最小可执行门禁”，不是企业级 CI 流水线
