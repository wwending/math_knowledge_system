# STATUS

## 2026-04-20 Testing And Delivery Governance Status

- 已明确当前最小回归测试集，并固定为发布前必跑命令。
- 已将发布前验证流程固定为“前端契约与构建 -> 后端关键单测 -> Alembic 迁移 -> 最小人工 smoke”。
- 已明确 README / STATUS / WORKLOG / DECISIONS / KNOWN_ISSUES 的职责边界。
- `docs/DELIVERY_2026-03-19.md` 继续保留为历史快照，不代表当前发布结论。
- `docs/auth-production-plan.md` 继续保留为历史设计稿，不代表当前状态或当前门禁。

## 当前状态

- 当前鉴权基线是手机号登录、`access token + refresh session` 会话体系。
- 公开注册仍只定义为 demo/staging 可开启能力，不是正式环境默认策略。
- 正式 schema 演进唯一可信路径仍是 Alembic。
- 当前发布门禁目标是“demo 阶段最小可执行且足够严格”，不是复杂 CI 流水线。

## 当前真相源职责

- [README.md](/d:/math_knowledge_system/README.md)：启动方式、最小回归测试、发布门禁、当前能力边界。
- [docs/STATUS.md](/d:/math_knowledge_system/docs/STATUS.md)：当前阶段状态与当前门禁结论。
- [docs/auth-acceptance-checklist.md](/d:/math_knowledge_system/docs/auth-acceptance-checklist.md)：发布前人工 smoke。
- [docs/KNOWN_ISSUES.md](/d:/math_knowledge_system/docs/KNOWN_ISSUES.md)：当前已知未解决风险。
- [docs/DECISIONS.md](/d:/math_knowledge_system/docs/DECISIONS.md)：采用当前方案的原因。
- [docs/WORKLOG.md](/d:/math_knowledge_system/docs/WORKLOG.md)：时间线记录，不承载当前真相。

## 当前最小发布门禁

### 必跑自动化命令

- `npm run test:auth-contract`
- `npm run test:stage3-contract`
- `npm run build`
- `python -m unittest backend.tests.test_auth_stage3 -v`
- `python -m unittest backend.tests.test_auth_system -v`
- `python -m unittest backend.tests.test_failure_paths -v`

### 必做发布前动作

- 在目标预发布环境执行 `alembic upgrade head`
- 完成最小人工 smoke：
  - 管理员登录
  - `me` / refresh / logout
  - 管理员创建用户并验证强制改密
  - 禁用用户后旧会话失效
  - capability 驱动的公开注册关闭态或开启态验证

### 失败即阻断发布

- 任一必跑命令失败
- 未先执行 Alembic 迁移
- 依赖运行时 schema 兜底替代正式迁移
- 人工 smoke 未通过
- 当前真相源文档之间仍存在冲突

## 当前未闭合边界

- 真实第三方失败场景的在线烟雾测试尚未系统完成。
- `backend.tests.test_failure_paths` 证明的是本地失败分支语义，不等于真实第三方异常已全量在线验证。
- 后端门禁依赖已准备好的 Python 依赖环境；当前仓库没有把这一步自动化为 CI。
- 公开注册仍缺少正式开放所需的防刷、审计和身份验证能力。
