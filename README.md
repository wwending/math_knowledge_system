# Math Knowledge System

当前仓库已完成鉴权生产化改造的阶段 3 收口，前后端统一切到手机号登录、`access token + refresh session` 会话体系。公开注册能力仍然保留，但作为 demo/staging 可开启能力，由后端 `PUBLIC_SIGNUP_ENABLED` 与 `/api/v1/auth/capabilities` 统一驱动；正式环境默认不应开放。

详细鉴权基线说明见 [docs/auth-backend-stage2.md](/d:/math_knowledge_system/docs/auth-backend-stage2.md)，验收步骤见 [docs/auth-acceptance-checklist.md](/d:/math_knowledge_system/docs/auth-acceptance-checklist.md)。

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
# production 自动启用严格模式；shared/staging/预发可显式打开严格模式
AUTH_STRICT_SECURITY=false
# direct_https / trusted_proxy_tls / insecure_http
SECURE_TRANSPORT_MODE=insecure_http
# 仅在必须支持跨站 refresh cookie 时显式打开
ALLOW_CROSS_SITE_REFRESH_COOKIE=false
# 非严格模式可为 false；严格模式必须为 true
REFRESH_TOKEN_COOKIE_SECURE=false
# 非严格模式可用 lax/strict/none；严格模式默认只允许 lax/strict
REFRESH_TOKEN_COOKIE_SAMESITE=lax

PUBLIC_SIGNUP_ENABLED=false
# demo/staging 可切为 true 验证公开注册；正式环境默认保持 false
SMS_CODE_LOGIN_ENABLED=false
SMS_PASSWORD_RECOVERY_ENABLED=false
PASSWORD_RECOVERY_MODE=admin_contact

LOGIN_RATE_LIMIT_WINDOW_SECONDS=900
LOGIN_RATE_LIMIT_MAX_ATTEMPTS=5
LOGIN_RATE_LIMIT_BLOCK_SECONDS=1800

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
- `SECURE_TRANSPORT_MODE` 必须为 `direct_https` 或 `trusted_proxy_tls`，不能为 `insecure_http`
- `REFRESH_TOKEN_COOKIE_SAMESITE` 默认只允许 `lax` 或 `strict`
- 若必须使用 `REFRESH_TOKEN_COOKIE_SAMESITE=none`，则必须同时配置：
  - `ALLOW_CROSS_SITE_REFRESH_COOKIE=true`
  - `REFRESH_TOKEN_COOKIE_SECURE=true`
  - `SECURE_TRANSPORT_MODE=direct_https` 或 `trusted_proxy_tls`
- 必须通过 Alembic 迁移建表，不依赖运行时自动补列

非严格模式说明：

- 默认开发环境可继续使用 `SECURE_TRANSPORT_MODE=insecure_http`
- 本地 HTTP 联调时允许 `REFRESH_TOKEN_COOKIE_SECURE=false`
- 特殊联调时允许 `REFRESH_TOKEN_COOKIE_SAMESITE=none`
- `SECURE_TRANSPORT_MODE` 仍必须是合法值：`direct_https`、`trusted_proxy_tls`、`insecure_http`

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
4. 运行测试和最小验收后再发布

本阶段新增的正式迁移：

- `backend/alembic/versions/20260319_0001_auth_production_baseline.py`
- `backend/alembic/versions/20260320_0002_auth_audit_and_rate_limit.py`

## 发布与回滚建议

发布前：

1. 先备份数据库
2. 在预发布环境执行 `alembic upgrade head`
3. 校验管理员登录、创建用户、强制改密、refresh、登出和审计日志
4. 确认严格模式环境的 `SECRET_KEY`、`CORS_ALLOW_ORIGINS`、`SECURE_TRANSPORT_MODE` 和 Cookie 配置正确
   - 至少确认 `REFRESH_TOKEN_COOKIE_SECURE=true`
   - 至少确认 `SECURE_TRANSPORT_MODE` 为 `direct_https` 或 `trusted_proxy_tls`
   - 默认确认 `REFRESH_TOKEN_COOKIE_SAMESITE` 为 `lax` 或 `strict`
   - 若显式使用 `REFRESH_TOKEN_COOKIE_SAMESITE=none`，同步确认 `ALLOW_CROSS_SITE_REFRESH_COOKIE=true`

发布时：

1. 先发布后端并执行迁移
2. 再发布前端
3. 完成 smoke test 后开放流量

回滚建议：

1. 若是前端问题，优先回滚前端静态资源
2. 若是后端逻辑问题且数据库结构未破坏，可先回滚应用版本
3. 若必须回滚迁移，先确认新表 `auth_audit_logs`、`login_rate_limits` 是否有需要保留的审计数据，再执行 `alembic downgrade`
4. 不要通过删除列或手工改表替代正式迁移回滚

## 阶段 3 验证命令

后端测试：

```powershell
.\.venv\Scripts\python.exe -m unittest backend.tests.test_auth_stage3 -v
```

前端契约与构建：

```powershell
cd frontend
npm run test:auth-contract
npm run test:stage3-contract
npm run build
```

## Public Signup Governance Update (2026-03-24)

- 前端公开注册入口、`/register` 路由可达性和关闭态提示，统一由 `GET /api/v1/auth/capabilities` 驱动。
- capability 未确认前，登录页和注册页都按安全关闭态处理，不向用户呈现“可注册”的可见状态。
- capability 获取失败与 capability=false 在 UI 上都保持关闭态，但内部状态与测试意图会继续区分两者。
- 公开注册仅为 demo/staging 可开启能力，不是正式环境默认策略。
- 当前仍缺少正式开放公开注册所需的防刷、审计和身份验证能力。
