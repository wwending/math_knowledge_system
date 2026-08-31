# Auth Acceptance Checklist

用于当前 demo/staging 阶段发布前的最小人工验收，不替代自动化测试。

## 1. 环境与迁移

- 已在目标环境执行 `alembic upgrade head`
- 正式发布环境未启用运行时 schema 变更
- 非 production 环境若启用 `AUTO_CREATE_TABLES` 或 `AUTO_APPLY_LEGACY_QUESTION_COMPAT`，已显式确认 `ALLOW_RUNTIME_SCHEMA_MUTATIONS=true`，且该环境不作为正式部署验收依据
- 数据库中存在 `auth_sessions`
- 数据库中存在 `auth_audit_logs`
- 数据库中存在 `login_rate_limits`

## 2. 发布前必跑命令

- 已执行 `npm run test:auth-contract`
- 已执行 `npm run test:stage3-contract`
- 已执行 `npm run build`
- 已在安装后端依赖的 Python 环境执行 `python -m unittest backend.tests.test_auth_stage3 -v`
- 已在安装后端依赖的 Python 环境执行 `python -m unittest backend.tests.test_auth_system -v`
- 已在安装后端依赖的 Python 环境执行 `python -m unittest backend.tests.test_failure_paths -v`

## 3. 配置硬边界

- 严格模式环境已确认 `SECRET_KEY` 已替换且长度满足要求
- 严格模式环境已确认 `CORS_ALLOW_ORIGINS` 不是 `*`
- 严格模式环境已确认 `REFRESH_TOKEN_COOKIE_SECURE=true`
- 严格模式环境已确认 `SECURE_TRANSPORT_MODE` 为 `direct_https` 或 `trusted_proxy_tls`
- 严格模式环境默认确认 `REFRESH_TOKEN_COOKIE_SAMESITE` 为 `lax` 或 `strict`
- 若严格模式环境使用 `REFRESH_TOKEN_COOKIE_SAMESITE=none`，已确认 `ALLOW_CROSS_SITE_REFRESH_COOKIE=true`
- `REFRESH_TOKEN_COOKIE_PATH` 以 `/` 开头且 `REFRESH_TOKEN_COOKIE_NAME` 非空

## 4. 最小人工 Smoke

- 管理员可使用手机号 + 密码登录
- 登录成功后 `GET /api/v1/auth/me` 返回当前用户信息
- refresh 成功后会话可继续使用
- 登出后 refresh session 被撤销，重新访问受保护页面需要重新登录
- 管理员可创建新用户
- 新用户若被标记为强制改密，首次登录后必须先完成改密
- 改密完成前不能继续访问受保护业务页面
- 管理员禁用用户后，该用户旧会话失效且再次登录会收到明确提示

## 5. Public Signup 边界

- 当数据库公开注册状态为关闭时，登录页不展示公开注册入口
- 当数据库公开注册状态为关闭时，直接访问 `/register` 不会进入可提交注册表单
- 当 capability 获取失败时，前端按安全关闭态处理
- 已验证用户管理中的持久化开关即时驱动登录页入口与 `/register` 路由 capability
- 对外说明没有把 demo/staging 可开启能力写成正式环境默认策略

## 6. 阻断条件

以下任一项成立，直接阻断发布：

- 必跑命令有失败项
- Alembic 迁移未执行或执行失败
- 手工 smoke 未通过
- 当前环境配置违反严格安全硬约束
- 文档仍存在相互冲突的发布结论
## Issue #147 验收补充（2026-08-31）

- 分别以 `admin` 与 `super_admin` 登录：前者无用户管理入口且直接调用全部用户管理 API 为 `403`；后者可完整管理。
- 关闭公开注册后，在已打开的注册页提交仍为 `403`；重新读取 capability 为关闭。开启操作必须二次确认。
- 注册用户名覆盖首尾空白、NFC、大小写敏感、保留名、纯下划线、历史手机号冲突与并发重复；昵称选填并默认用户名。
- 匿名注册验证每 IP 每小时最多 5 个成功、每 10 分钟最多 20 个失败，窗口到期恢复；核对成功与限流拒绝审计不含密码。
- 验证历史手机号账号仍能登录；匿名注册、代创建、重置和主动改密均接受相同的 6～64 可打印 ASCII 密码规则。
- 页面不再出现首次登录强制改密选项或跳转；重置密码仍撤销目标用户会话。
