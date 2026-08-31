# Auth Production Baseline

## 2026-08-31 Username/Public Signup Governance (#147)

- 当前登录主标识改为用户名，历史手机号继续兼容登录；新建账号不再要求手机号或邮箱。
- 用户管理全部能力仅 `super_admin` 可调用；`admin` 不再拥有用户管理权限。
- 公开注册开关已持久化，数据库为初始化后的唯一事实来源；新安装默认开启。
- 所有密码设置入口统一为 6～64 个可打印 ASCII 字符且不能全为空格；首次登录强制改密状态已从产品流程移除。
- 匿名注册具备按可信 IP 的成功/失败限流及安全审计。下文阶段 3 的手机号主标识、环境变量开关和强制改密描述仅保留为历史基线，不再代表当前行为。

## 2026-03-24 Public Signup Capability Governance Update

- 前端只通过统一 capability 状态路径读取 `public_signup_enabled`，不再由登录页、注册页、路由守卫各自分散判断。
- capability 状态路径负责能力获取、失败降级、字段归一化和必要缓存。
- capability=false 与 capability 获取失败在 UI 上都按安全关闭态处理，但内部状态仍区分 `ready + disabled` 与 `error + closed`。
- `/register` 只有在 capability 已确认且为 `true` 时才允许进入可提交注册表单态。
- 公开注册由超级管理员通过持久化开关治理；关闭态按安全边界处理。
- 匿名注册已具备可信客户端 IP 的成功/失败限流与安全审计；不提供短信、邮箱或第三方身份验证。

本文记录当前仓库在阶段 3 完成后的鉴权与账户治理基线。虽然文件名延续 `stage2`，内容已补充阶段 3 的前端接入、安全治理和验收收口。

## 目标边界

- 公开注册与超级管理员代创建账号并存；普通 `admin` 不具备用户管理权限
- 公开注册状态由数据库持久化，`PUBLIC_SIGNUP_ENABLED` 仅供首次迁移继承
- 登录主标识使用用户名，历史手机号继续兼容
- 登录后支持 refresh 会话续期
- 新建用户和超级管理员重置密码后不进入强制改密状态；用户仍可主动改密
- 当前不开放短信验证码登录或短信找回密码，但已预留开关和能力位

## 数据结构

### 用户表 `users`

关键字段：

- `phone`
- `display_name`
- `role`
- `status`
- `must_change_password`
- `last_login_at`
- `password_changed_at`
- `phone_verified_at`
- `created_by`

当前状态语义：

- `active`
- `disabled`
- `pending_password_change`

### 会话表 `auth_sessions`

- refresh token 以哈希形式持久化
- access token 为短期 JWT
- refresh token 默认通过 HttpOnly Cookie 传输
- refresh 时轮换 refresh token
- 用户被禁用、管理员重置密码、用户自助改密后会撤销旧会话

### 阶段 3 新增表

#### 审计日志 `auth_audit_logs`

覆盖以下事件：

- `auth.login.success`
- `auth.login.failure`
- `admin.user.created`
- `admin.user.disabled`
- `admin.user.enabled`
- `admin.user.role.changed`
- `admin.user.password.reset`
- `auth.password.changed`

审计字段包含：

- 事件类型
- 成功/失败结果
- 操作人
- 目标用户
- 目标手机号
- IP
- User-Agent
- 附加上下文

#### 登录失败限流 `login_rate_limits`

- 同时按手机号和 IP 维度计数
- 在固定窗口内累计失败次数
- 达到阈值后进入封禁期
- 成功登录后清理该手机号/IP 的失败状态

## 接口基线

### 公共鉴权接口

- `GET /api/v1/auth/capabilities`
- `POST /api/v1/auth/login`
- `POST /api/v1/auth/token`
- `POST /api/v1/auth/refresh`
- `POST /api/v1/auth/logout`
- `GET /api/v1/auth/me`
- `POST /api/v1/auth/change-password`
- `POST /api/v1/auth/register`

`/auth/capabilities` 返回当前环境的认证能力开关；以默认配置为例：

- `public_signup_enabled=false`
- `password_recovery_mode=admin_contact`
- `sms_code_login_enabled=false`
- `sms_password_recovery_enabled=false`

### 管理员接口

- `GET /api/v1/admin/users`
- `GET /api/v1/admin/users/{id}`
- `POST /api/v1/admin/users`
- `PATCH /api/v1/admin/users/{id}/status`
- `PATCH /api/v1/admin/users/{id}/role`
- `POST /api/v1/admin/users/{id}/reset-password`

限制：

- 管理员不能通过管理员接口修改自己的角色
- 管理员不能通过管理员接口修改自己的启停状态
- 管理员不能通过管理员接口给自己重置密码
- 非 `super_admin` 不能管理或授予 `super_admin`
- 状态接口当前只允许 `active` 和 `disabled`

## 前端会话行为

- 不再使用 `localStorage` 单 token 持久化
- access token 存在 `sessionStorage`
- refresh token 存在 HttpOnly Cookie
- 页面刷新或 access token 失效时，前端会优先尝试 `/auth/refresh`
- 路由守卫会读取 `/auth/me`，并根据 `must_change_password` 强制跳转改密页
- 登录页是否展示公开注册入口由 `/auth/capabilities.public_signup_enabled` 决定
- `/register` 路由进入前会再次校验 `/auth/capabilities.public_signup_enabled`
- 当能力关闭时，前端统一展示“联系管理员创建账号 / 忘记密码联系管理员”

## 安全配置

新增关键配置：

- `APP_ENV`
- `AUTH_STRICT_SECURITY`
- `SECURE_TRANSPORT_MODE`
- `ALLOW_CROSS_SITE_REFRESH_COOKIE`
- `LOGIN_RATE_LIMIT_WINDOW_SECONDS`
- `LOGIN_RATE_LIMIT_MAX_ATTEMPTS`
- `LOGIN_RATE_LIMIT_BLOCK_SECONDS`
- `SMS_CODE_LOGIN_ENABLED`
- `SMS_PASSWORD_RECOVERY_ENABLED`
- `PASSWORD_RECOVERY_MODE`

严格模式触发条件：

- `APP_ENV=production` 时自动启用
- 非 production 环境可通过 `AUTH_STRICT_SECURITY=true` 显式启用
- shared/staging/demo 不会因环境名自动进入严格模式

安全传输部署声明：

- `SECURE_TRANSPORT_MODE=direct_https`
- `SECURE_TRANSPORT_MODE=trusted_proxy_tls`
- `SECURE_TRANSPORT_MODE=insecure_http`
- 上述值会在启动时做大小写归一化和合法值校验；拼写错误会直接拒绝启动
- 这是部署声明，不是应用自动证明的事实

严格模式校验：

- `SECRET_KEY` 不能使用默认值
- `SECRET_KEY` 长度至少 32 位
- `CORS_ALLOW_ORIGINS` 不能为 `*`
- `REFRESH_TOKEN_COOKIE_NAME` 不能为空
- `REFRESH_TOKEN_COOKIE_PATH` 必须以 `/` 开头
- `REFRESH_TOKEN_COOKIE_SECURE` 必须为 `true`
- `SECURE_TRANSPORT_MODE` 不能为 `insecure_http`
- `REFRESH_TOKEN_COOKIE_SAMESITE` 默认只允许 `lax` 或 `strict`
- 若显式声明 `ALLOW_CROSS_SITE_REFRESH_COOKIE=true`，则可允许 `REFRESH_TOKEN_COOKIE_SAMESITE=none`
- 允许 `SameSite=none` 时仍必须满足 `REFRESH_TOKEN_COOKIE_SECURE=true`
- 允许 `SameSite=none` 时仍必须满足 `SECURE_TRANSPORT_MODE=direct_https` 或 `trusted_proxy_tls`

开发 / 测试环境放宽口径：

- 默认可保持 `AUTH_STRICT_SECURITY=false`
- 默认可使用 `SECURE_TRANSPORT_MODE=insecure_http`
- `REFRESH_TOKEN_COOKIE_SECURE=false` 可用于本地 HTTP 调试
- `REFRESH_TOKEN_COOKIE_SAMESITE` 可暂时使用 `none` 以支持特殊联调，但仍必须是 `lax`、`strict`、`none` 之一

严格模式认证 Cookie 基线：

- refresh token 始终通过 `HttpOnly Cookie` 传输
- 严格模式要求 `Secure=true`
- 严格模式默认要求 `SameSite` 显式为 `lax` 或 `strict`
- 只有显式声明跨站 refresh cookie 场景时才允许 `SameSite=none`
- 上述约束在应用启动阶段校验，不满足时服务直接拒绝启动

## 迁移

当前正式迁移版本：

- `20260319_0001_auth_production_baseline.py`
- `20260320_0002_auth_audit_and_rate_limit.py`

原则：

- 新增表或列必须走 Alembic
- 不再依赖运行时自动补列来完成新的鉴权改造
- production 环境无条件禁止运行时 schema 变更
- 非 production 环境只有在 `ALLOW_RUNTIME_SCHEMA_MUTATIONS=true` 时，`AUTO_CREATE_TABLES` 与兼容补列开关才允许生效
- `AUTO_CREATE_TABLES` 与兼容补列开关仅作为本地开发或受限兼容窗口手段，不应作为生产流程

## 公开注册与短信找回的后续增强项

最小还需补齐：

- 更完整的公开注册风控、审计与环境策略
- 短信验证码发送服务
- 验证码存储、过期控制和校验
- 短信发送频控与防刷
- 找回密码专用审计事件
- 短信通道失败告警与运维配置
