# STATUS

## 2026-03-24 Auth Strict Security Guardrails Status

- 已将认证安全要求从“生产环境文档约定”收紧为“启动时严格模式硬约束”。
- `APP_ENV=production` 会自动启用严格模式；shared/staging/预发可通过 `AUTH_STRICT_SECURITY=true` 显式启用。
- `SECURE_TRANSPORT_MODE` 已作为部署声明建模，启动时只接受 `direct_https`、`trusted_proxy_tls`、`insecure_http`。
- 严格模式下拒绝 `SECURE_TRANSPORT_MODE=insecure_http`。
- 严格模式下默认拒绝 `REFRESH_TOKEN_COOKIE_SAMESITE=none`；仅在显式声明 `ALLOW_CROSS_SITE_REFRESH_COOKIE=true` 时允许例外。
- 允许 `SameSite=none` 的严格模式场景仍要求 `REFRESH_TOKEN_COOKIE_SECURE=true` 且安全传输模式不是 `insecure_http`。

## 2026-03-24 Public Signup Capability Governance Status

- 已将公开注册入口治理收口为“后端 capability 决定前端展示与 `/register` 可达性”。
- capability=false 与 capability 获取失败在 UI 上都按安全关闭态处理。
- capability 获取失败仍会在内部状态、路由提示和测试意图中保留可观测区分。
- 公开注册当前只定义为 demo/staging 可开启能力，不是正式环境默认策略。
- 正式开放公开注册所需的防刷、审计和身份验证能力仍未落地。

日期：2026-03-19

## 当前结论

本轮交付已经完成兼容修复、正向链路接通和主要失败路径收口，适合今晚整理提交并做后续交接。

当前最准确的状态描述是：

- 正向链路已通过到“真实 JWT 登录 -> 真实百度 OCR 返回 -> 真实 LLM 返回 -> 页面展示”
- 失败路径已完成代码层修复，并有 stub 条件下的验证
- 真实第三方失败场景的在线烟雾测试尚未系统完成

## 已完成

- 配置收敛到 `settings`，路径解析不再依赖运行时 `cwd`
- 静态目录、上传目录、PDF 临时目录、SQLite 路径统一按后端目录解析
- `Question` 旧契约兼容修复已落地，启动时可补齐缺失旧列
- 前端已接入真实 JWT 登录，不再使用假 token
- 前端请求、会话校验、`401` 清理与路由拦截已统一
- 后端统一返回 `image_url`，前端已统一消费图片地址
- OCR 全失败不落库
- OCR 成功但 LLM 失败时返回 `partial_success`，保留 OCR 原文
- 登录失败、缺 token、无效 token、过期 token 的提示语义已收口
- 图片丢失时前端已提供展示层占位兜底

## 已验证

### 真实人工 / 真实第三方

- 今日人工浏览器验收已完成
- 已确认真实 JWT 登录可用
- 已确认真实百度 OCR 真能返回
- 已确认真实 LLM 真能返回
- 已确认正向链路能从登录走到识别结果展示

### stub 条件下

- `backend/tests/test_failure_paths.py` 已用于验证失败路径返回语义
- 这部分验证覆盖鉴权失败、OCR 失败、LLM 失败、部分成功等分支
- 该组验证基于 `patch / monkeypatch`，不等于真实第三方在线验证

## 未完成

- 真实第三方失败场景的在线烟雾测试未系统完成
- 尚未对“错密钥 / 超时 / 断网 / 三方异常结构 / 三方限流”形成完整在线验收矩阵
- 尚未建立正式数据库迁移体系
- 尚未做多部署环境的一致性验证

## 风险

- 当前最大风险不是正向链路，而是未系统验证的真实第三方失败场景
- `Question` 旧契约目前依赖运行时补列，适合兼容交付，不等于长期迁移方案
- 静态资源缺失时只做前端展示兜底，不会自动补回文件
- 部署时如果 `STATIC_URL_PREFIX`、反向代理路径或 CORS 配置不一致，可能出现环境差异问题
- 当前鉴权只有 access token，缺少 refresh token 与更细粒度会话治理
