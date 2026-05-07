# WORKLOG

## 2026-05-07 第六轮：记录主链路决策

目标：

- 只更新文档。
- 记录主链路选择 C：短期继续 `/api/v1/recognize`，长期逐步迁移到 `assets/drafts/ocr_runs/llm_runs` 正式流水线。
- 明确下一阶段只做最小正式流水线后端竖切，不硬切现有前端。

结果：

- [docs/DECISIONS.md](/d:/math_knowledge_system/docs/DECISIONS.md) 已新增主链路渐进式迁移决策。
- [docs/STATUS.md](/d:/math_knowledge_system/docs/STATUS.md) 已更新当前结论、未闭合边界和下一阶段口径。
- [docs/KNOWN_ISSUES.md](/d:/math_knowledge_system/docs/KNOWN_ISSUES.md) 已将“主链路决策尚未完成”更新为“正式流水线最小后端竖切尚未实现”。

边界：

- 当前主链路仍是 `/api/v1/recognize`。
- `/upload_pdf`、`/assets`、drafts 当前不是主前端闭环。
- 不删除 `/recognize`。
- 不现在硬切 `Dashboard.vue`。
- 不做 OCR/LLM provider 抽象、异步队列、批量 PDF、多页 draft 管理。

## 2026-05-05 第三轮：项目文档收口

目标：

- 只更新文档和示例配置文件。
- 记录第二轮修复结果。
- 明确当前能力边界，避免夸大完成度。

结果：

- [README.md](/d:/math_knowledge_system/README.md) 已收口启动、迁移、管理员初始化、最小验证和能力边界。
- [docs/STATUS.md](/d:/math_knowledge_system/docs/STATUS.md) 已更新当前状态为“可启动、可验证、可继续开发”。
- [docs/KNOWN_ISSUES.md](/d:/math_knowledge_system/docs/KNOWN_ISSUES.md) 已更新当前未闭合风险。
- [docs/DECISIONS.md](/d:/math_knowledge_system/docs/DECISIONS.md) 已补充第三轮文档口径决策。
- [backend/.env.example](/d:/math_knowledge_system/backend/.env.example) 已创建为后端本地配置示例。

第二轮验证记录：

- `frontend npm run build` 通过，仅有 Vite chunk size warning。
- `frontend npm run test:auth-contract` 通过。
- `frontend npm run test:stage3-contract` 通过。
- `backend python -m compileall app` 通过。
- `backend python -m unittest discover tests` 通过，`Ran 36 tests OK`。
- `backend/requirements.txt` 已补齐 `passlib[bcrypt]`。
- `frontend/package.json` 已显式声明 `@element-plus/icons-vue`。
- README 已修正管理员初始化路径。
- README 已明确 `alembic upgrade head` 是硬前置。
- README 已标注 `/upload_pdf`、`/assets`、draft 流水线目前未接入主前端。
- `backend/.env` 是本地文件，不应提交。

## 2026-04-20 测试与交付治理收口

结果：

- 固定最小回归测试集和发布前门禁。
- 明确 README / STATUS / WORKLOG / DECISIONS / KNOWN_ISSUES 的职责边界。
- 历史快照和历史设计稿继续保留，但不作为当前状态依据。

## 2026-03-24 数据库迁移治理收口

结果：

- 明确正式 schema 演进以 Alembic 为唯一可信路径。
- production 环境禁止运行时 schema 变更。
- 非 production 环境也只有显式开启兼容开关时才允许运行时 schema 兜底。

## 2026-03-19 主链路修复与验收

结果：

- 收敛后端配置和路径解析。
- 接入真实 JWT 登录。
- 统一图片 URL 返回。
- 收口 OCR / LLM 失败路径。
- 完成人工浏览器验收。
- 明确真实第三方失败场景尚未系统化验证。
