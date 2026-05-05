# 鉴权生产化改造设计

历史设计稿说明：

- 本文档主要用于保留阶段 1 到阶段 3 之间的设计演进背景。
- 其中部分“当前状态”描述已经被后续实现覆盖。
- 当前状态、当前发布门禁和当前验收结论以 [README.md](/d:/math_knowledge_system/README.md)、[docs/STATUS.md](/d:/math_knowledge_system/docs/STATUS.md) 与 [docs/auth-acceptance-checklist.md](/d:/math_knowledge_system/docs/auth-acceptance-checklist.md) 为准。

## 1. 背景与阶段目标

当前仓库的鉴权能力只覆盖了最小可交付链路：用户表、密码哈希、JWT access token、`/api/v1/auth/token` 登录、`/api/v1/auth/me` 会话校验，以及一个匿名开放的 `/api/v1/auth/register`。这套实现可以支撑本地演示和单管理员交付，但不满足“可长期生产使用”的账户治理要求。

阶段 1 的目标不是重做整套鉴权，而是先把当前策略收口，并给出一份与现有代码对齐的生产化设计，确保后续阶段可以沿着正式方案演进。

## 2. 当前现状与主要问题

### 2.1 当前代码现状

- 后端鉴权入口位于 `backend/app/api/v1/auth.py`。
- 用户模型位于 `backend/app/models/user.py`，当前字段只有 `username`、`email`、`hashed_password`、`role`、`is_active`。
- 当前管理员初始化依赖脚本 `backend/app/scripts/create_admin.py`。
- 前端登录页位于 `frontend/src/views/Login.vue`，当前只接入登录，不存在正式的后台用户管理界面。
- 前端 token 存储位于 `frontend/src/utils/auth.js`，当前直接写入 `localStorage`。
- 启动逻辑位于 `backend/app/main.py`；当前已将正式 schema 演进路径收口为 Alembic，运行时建表与补列只保留为显式受限兼容模式。

### 2.2 与产品规则冲突的点

- 当前后端匿名开放 `POST /api/v1/auth/register`，任何人都可以直接创建账号，这与“当前阶段只允许管理员创建账号，禁止匿名公开注册”的产品规则直接冲突。
- 当前登录标识仍然是 `username`，尚未切换为手机号，也没有为短信验证码预留正式模型和接口。
- 前端登录页之前存在“注册新账号”“忘记密码”类入口暗示，但系统并没有对应的生产化流程。

### 2.3 当前实现的生产风险

#### 只有 access token

- 当前只有 access token，没有 refresh token、会话续期、设备级会话管理、主动失效机制。
- 令牌一旦签发，只能依赖过期时间自然失效，不利于风控、登出治理、密码重置后的会话清理。

#### token 存在 localStorage

- 前端当前通过 `frontend/src/utils/auth.js` 将 token 保存在 `localStorage`。
- 这会放大 XSS 风险，一旦页面脚本被注入，token 很容易被读取和滥用。
- 后续生产化阶段应演进为 refresh token + HttpOnly Cookie 或更严格的会话承载方案。

#### SQLite

- 当前默认数据库是 SQLite，适合单机开发和轻量演示，不适合长期生产并发写入、备份治理、运维审计和后续扩展。
- 用户、角色、审计日志、会话等鉴权核心数据最终应迁移到正式生产数据库，建议以 PostgreSQL 为目标。

#### AUTO_CREATE_TABLES 与运行时补列

- 当前 `backend/app/main.py` 只有在非 production 且显式设置 `ALLOW_RUNTIME_SCHEMA_MUTATIONS=true` 时，才允许 `AUTO_CREATE_TABLES` 与 `ensure_legacy_question_columns(...)` 生效。
- production 环境无条件禁止运行时 schema 变更。
- 运行时建表与补列只作为本地开发或受限兼容窗口的兜底，不再作为正式迁移方案。

## 3. 阶段 1 的收口策略

### 3.1 匿名注册收口

- 保留 `/api/v1/auth/register` 路径作为兼容壳，但引入 `PUBLIC_SIGNUP_ENABLED` feature flag。
- 默认 `PUBLIC_SIGNUP_ENABLED=false`。
- 当开关关闭时，匿名请求 `POST /api/v1/auth/register` 明确返回 `403`，错误信息为“当前环境未开放公开注册，请联系管理员创建账号”。

### 3.2 兼容策略说明

- 本阶段不直接删除 `/api/v1/auth/register`，原因是当前仓库后续一定会开放公开自助注册，直接移除会让未来再次引入同一路径时缺少平滑演进位点。
- 当前采用“保留接口路径 + 默认拒绝 + feature flag 控制”的兼容策略。
- 后续阶段可以把该路径迁移到正式的公开注册流程，包括手机号、密码策略、验证码、限流和审计等能力，而不是再次新增一套并行接口。

## 4. 用户模型设计方向

当前 `User` 模型不足以支撑生产化治理，后续应演进为以下方向：

### 4.1 核心身份字段

- `id`
- `phone`：唯一、规范化存储，未来作为登录标识
- `phone_verified_at`：为未来短信验证预留
- `display_name`：展示名
- `password_hash`
- `must_change_password`
- `password_changed_at`
- `status`：`active` / `disabled` / `pending_password_change`
- `is_superuser` 或通过角色系统表达超级管理员能力

### 4.2 账户治理字段

- `created_by`
- `updated_by`
- `created_at`
- `updated_at`
- `disabled_at`
- `disabled_reason`
- `last_login_at`
- `last_login_ip`

### 4.3 首次登录与重置密码策略

- 管理员创建账号后，可配置首次登录强制改密；落库上通过 `must_change_password` 与 `status=pending_password_change` 共同表达。
- 管理员重置密码后，用户下次登录必须修改密码；同时刷新 `must_change_password=true`，并在用户完成改密后写入新的 `password_changed_at`。

### 4.4 兼容迁移原则

- 阶段 2/3 不直接粗暴替换 `username`；会先增加 `phone` 等正式字段，再完成数据迁移与登录逻辑切换。
- 在迁移窗口内，可以保留 `username` 作为兼容字段，但新逻辑应逐步以手机号为主。

## 5. 角色与权限模型

当前 `role` 只有单个字符串字段，只能表达非常粗粒度的身份，扩展性不足。生产化方向如下：

### 5.1 角色模型

- `roles`：阶段 2 先落地最小角色集 `super_admin`、`admin`、`user`
- `permissions`：权限定义表，例如 `user:create`、`user:disable`、`user:reset_password`
- `role_permissions`：角色与权限关系表
- `user_roles`：用户与角色关系表

### 5.2 当前阶段建议

- 阶段 1 继续兼容现有 `role` 字段，避免一次性改动过大。
- 阶段 2 引入正式 RBAC 表结构，同时保留 `role` 到 RBAC 的兼容映射。
- 阶段 2 先实现最小角色集，不先扩展 `editor`、`teacher` 一类业务角色。

### 5.3 本产品最少需要覆盖的权限

- `user:create`
- `user:update`
- `user:disable`
- `user:enable`
- `user:reset_password`
- `role:assign`
- `role:view`
- `session:revoke`

## 6. 会话模型方向

当前只有无状态 access token。生产化方向建议引入显式会话模型：

- `auth_sessions`
- `refresh_tokens` 或 refresh token 哈希
- `device_info`
- `ip_address`
- `user_agent`
- `created_at`
- `expires_at`
- `revoked_at`
- `revoke_reason`

会话治理目标：

- 支持 refresh token 轮换
- 支持密码重置后批量失效旧会话
- 支持管理员手动踢出会话
- 支持审计最近登录设备

阶段 1 不实现这些能力，但设计上必须为后续落地留好空间。

## 7. API 草案

### 7.1 阶段 1 保留/收口

- `POST /api/v1/auth/token`
  - 当前继续保留
  - 现阶段仍使用账号 + 密码登录
- `GET /api/v1/auth/me`
  - 当前继续保留
- `POST /api/v1/auth/register`
  - 当前默认拒绝
  - 由 `PUBLIC_SIGNUP_ENABLED` 控制

### 7.2 后续管理员账户管理 API

- `POST /api/v1/admin/users`
  - 管理员创建用户
  - 可配置首次登录强制改密
- `PATCH /api/v1/admin/users/{user_id}/status`
  - 禁用/启用用户
- `PATCH /api/v1/admin/users/{user_id}/roles`
  - 调整角色
- `POST /api/v1/admin/users/{user_id}/reset-password`
  - 管理员重置密码
  - 重置后用户下次登录必须修改密码

### 7.3 后续用户自助 API

- `POST /api/v1/auth/change-password`
  - 已登录用户修改密码
- `POST /api/v1/auth/register`
  - 未来公开注册入口，受 feature flag 与风控控制
- `POST /api/v1/auth/send-phone-code`
  - 暂不实现，但接口路径应预留为未来短信验证码扩展点
- `POST /api/v1/auth/verify-phone-code`
  - 暂不实现，为后续接入预留

### 7.4 登录标识演进

- 阶段 1 不修改现有登录接口的表单字段，避免引入完整新体系。
- 阶段 2 起新增手机号登录语义，并逐步把 `username` 迁移为兼容字段。

## 8. 数据库迁移方案

### 8.1 迁移工具

- 引入 Alembic 作为正式迁移体系。
- 所有用户、角色、会话相关变更必须通过迁移脚本落地。

### 8.2 迁移顺序

1. 建立迁移骨架，冻结当前基线。
2. 为 `users` 表新增手机号、状态、审计字段。
3. 新增 `roles`、`permissions`、`user_roles`、`role_permissions`。
4. 新增 `auth_sessions`、`refresh_tokens`。
5. 根据新模型改造服务层与 API。
6. 生产环境禁止运行时 schema 变更，并将兼容路径收敛为显式受限模式。

### 8.3 发布要求

- 迁移脚本先于应用发布执行。
- 迁移必须可回滚或至少具备明确回退预案。
- 不再接受“应用启动时自动补列”的方式处理鉴权表结构。

## 9. 前端交互流

### 9.1 当前阶段

- 登录页只展示登录入口。
- 页面明确说明“账号由管理员创建”。
- 不展示公开注册入口。
- 不展示没有后端能力支撑的“忘记密码”自助入口。

### 9.2 后续管理员流

- 管理端用户列表页
- 创建用户弹窗或页面
- 用户启用、禁用、角色管理
- 管理员重置密码

### 9.3 后续自助流

- 公开注册页受 feature flag 控制
- 手机号输入与格式校验
- 密码强度与弱密码校验
- 短信验证码流程在后续阶段接入

## 10. 分阶段实施计划

### 阶段 1：策略收口与设计冻结

- 关闭匿名公开注册
- 删除前端公开注册暗示
- 输出生产化设计文档
- 增加最小验证

### 阶段 2：账户模型与管理员用户管理

- 引入正式迁移体系
- 扩展用户表
- 增加管理员创建用户、启用或禁用、角色管理、重置密码 API
- 前端补管理员用户管理入口

### 阶段 3：密码与会话生产化

- 引入密码复杂度与弱密码校验
- 增加用户修改密码
- 增加 refresh token、会话表、会话撤销
- 优化 token 存储策略

### 阶段 4：公开注册与短信扩展点

- 在 `PUBLIC_SIGNUP_ENABLED=true` 时开放正式公开注册能力
- 以手机号作为主登录标识
- 接入短信验证码能力
- 增加注册风控、限流和审计

## 11. 本阶段结论

阶段 1 应当以“先收口，再演进”为原则。当前最关键的冲突不是功能不够多，而是匿名开放注册已经违反产品规则。先通过 feature flag 默认关闭公开注册、移除前端错误暗示、冻结生产化设计，再进入后续结构性改造，能避免在错误策略上继续累积实现成本。
## 2026-03-24 Public Signup Governance Clarification

- 当前阶段的目标不是把公开注册提升为正式默认策略，而是把现有 demo/staging 能力边界表达准确。
- 前端公开注册入口、注册页表单可见性和 `/register` 路由可达性，都必须由 `/api/v1/auth/capabilities.public_signup_enabled` 统一驱动。
- capability 获取失败时，前端按安全关闭态处理，避免在未知状态下误导用户进入公开注册流程。
- 正式开放公开注册仍需补齐防刷、审计、身份验证等治理能力，本阶段不扩展到这些实现。
