# Auth Acceptance Checklist

## 2026-03-24 Public Signup Capability Governance Addendum

- 登录页公开注册入口只允许由 `/api/v1/auth/capabilities.public_signup_enabled` 驱动。
- capability 未确认前，登录页不得出现“可注册”的可见状态。
- capability 未确认前，`/register` 页面不得渲染可提交注册表单。
- 当 `PUBLIC_SIGNUP_ENABLED=false` 时，登录页不展示注册入口，直接访问 `/register` 会被拦回登录页或保持关闭态。
- 当 capability 获取失败时，前端按安全关闭态处理，但测试与内部状态仍要保留“获取失败”可观测性。
- 公开注册仅为 demo/staging 可开启能力，不是正式环境默认策略。
- 当前仍缺少正式开放公开注册所需的防刷、审计和身份验证能力。

用于阶段 3 上线前验收。

## 1. 迁移执行

- 已在目标环境执行 `alembic upgrade head`
- production 环境未启用运行时 schema 变更
- 非 production 环境若启用 `AUTO_CREATE_TABLES` 或 `AUTO_APPLY_LEGACY_QUESTION_COMPAT`，已显式确认 `ALLOW_RUNTIME_SCHEMA_MUTATIONS=true`，且该环境不作为正式部署验收依据
- 数据库中存在 `auth_sessions`
- 数据库中存在 `auth_audit_logs`
- 数据库中存在 `login_rate_limits`

## 2. 初始化管理员

- 已通过 `create_admin` 脚本创建或升级初始管理员
- 初始管理员可使用手机号 + 密码登录
- 严格模式环境已确认 `SECRET_KEY` 已替换，`CORS_ALLOW_ORIGINS` 不是 `*`
- 严格模式环境已确认 `REFRESH_TOKEN_COOKIE_SECURE=true`
- 严格模式环境已确认 `SECURE_TRANSPORT_MODE` 为 `direct_https` 或 `trusted_proxy_tls`
- 严格模式环境默认确认 `REFRESH_TOKEN_COOKIE_SAMESITE` 为 `lax` 或 `strict`
- 若严格模式环境使用 `REFRESH_TOKEN_COOKIE_SAMESITE=none`，已确认 `ALLOW_CROSS_SITE_REFRESH_COOKIE=true`
- `REFRESH_TOKEN_COOKIE_PATH` 以 `/` 开头且 `REFRESH_TOKEN_COOKIE_NAME` 非空

## 3. 管理员创建用户

- 管理员可在前端后台用户管理页创建新用户
- 新用户手机号唯一校验生效
- 密码策略生效：
  - 不能纯数字
  - 弱密码会被拒绝
- 创建后用户可立即登录

## 4. 手机号登录

- 登录页只接受手机号 + 密码
- 登录页明确提示：
  - 当 `PUBLIC_SIGNUP_ENABLED=true` 时展示公开注册入口
  - 当 `PUBLIC_SIGNUP_ENABLED=false` 时提示联系管理员创建账号
  - 忘记密码请联系管理员
- 登录成功后能获取当前用户信息

## 5. 首次强制改密

- 管理员创建用户时勾选强制改密后，用户首次登录成功
- 登录后立即跳转到改密页
- 未完成改密前不能继续访问受保护业务页面
- 改密成功后能正常进入系统

## 6. 禁用用户

- 管理员可禁用用户
- 被禁用用户再次登录会收到明确提示
- 已登录会话会被撤销
- 用户列表中能明确看到“已禁用，无法登录”

## 7. 角色管理

- 管理员可修改普通用户角色
- 非 `super_admin` 不能授予或管理 `super_admin`
- 管理员不能修改自己的角色

## 8. 管理员重置密码

- 管理员可为其他用户重置密码
- 重置后旧会话失效
- 勾选强制改密时，用户下次登录后必须先改密
- 前后端都提示当前不开放自助找回，需联系管理员

## 9. Refresh 会话

- 登录成功后浏览器获得 refresh cookie
- refresh cookie 带 `HttpOnly`
- 严格模式环境 refresh cookie 带 `Secure`
- 严格模式环境默认 refresh cookie 的 `SameSite` 为 `lax` 或 `strict`
- 若严格模式环境显式允许跨站 refresh cookie，则 `SameSite=none` 也必须同时满足 `ALLOW_CROSS_SITE_REFRESH_COOKIE=true` 与安全传输模式非 `insecure_http`
- access token 失效后，前端可通过 `/auth/refresh` 自动恢复会话
- refresh 失败时会清理本地会话并跳回登录页

## 10. 登出

- 用户点击退出登录后，前端清理 access token
- 后端撤销当前 refresh session
- 再次访问受保护页面需要重新登录

## 11. 审计日志

- 数据库中能看到登录成功/失败审计
- 数据库中能看到创建用户审计
- 数据库中能看到禁用/启用审计
- 数据库中能看到角色变更审计
- 数据库中能看到重置密码审计
- 数据库中能看到用户自助修改密码审计

## 12. 登录失败限流

- 连续输错密码达到阈值后，登录接口返回 `429`
- `Retry-After` 响应头存在
- 成功登录后，对应手机号/IP 的失败状态会清理

## 13. 未来扩展位

- `/api/v1/auth/capabilities` 返回公开注册和短信能力开关
- `PUBLIC_SIGNUP_ENABLED=false`
- `SMS_CODE_LOGIN_ENABLED=false`
- `SMS_PASSWORD_RECOVERY_ENABLED=false`
- 正式环境默认不展示公开注册入口和短信找回入口
- demo/staging 可通过 `PUBLIC_SIGNUP_ENABLED=true` 开启公开注册，并要求前端入口与 `/register` 路由都跟随 capability
