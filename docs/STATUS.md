# STATUS

## 2026-05-05 项目文档收口状态

当前项目进入“可启动、可验证、可继续开发”的状态。该结论不等于生产可用，也不表示所有正式流水线已经闭环。

## 当前结论

- 当前主链路仍是 `POST /api/v1/recognize`。
- `assets/drafts/ocr_runs/llm_runs` 是已建模但未前端闭环的正式流水线预留。
- `/upload_pdf`、`/assets`、draft 流水线目前未接入主前端。
- 后端启动和管理员初始化前必须先执行 `alembic upgrade head`。
- `backend/.env` 是本地文件，不应提交；示例配置使用 `backend/.env.example`。

## 第二轮验证结果

| 范围 | 命令 | 状态 |
| --- | --- | --- |
| frontend | `npm run build` | 通过，仅有 Vite chunk size warning |
| frontend | `npm run test:auth-contract` | 通过 |
| frontend | `npm run test:stage3-contract` | 通过 |
| backend | `python -m compileall app` | 通过 |
| backend | `python -m unittest discover tests` | 通过，`Ran 36 tests OK` |

依赖收口：

- `backend/requirements.txt` 已补齐 `passlib[bcrypt]`。
- `frontend/package.json` 已显式声明 `@element-plus/icons-vue`。
- README 已修正管理员初始化路径为 `app.scripts.create_admin`。
- README 已明确 `alembic upgrade head` 是硬前置。

## 当前未闭合边界

- 前端中文乱码仍需优先处理。
- 主链路仍需决策：继续以 `/api/v1/recognize` 为主，还是切到 draft 流水线。
- mock/legacy 文件需要清理，但不应在下一阶段做大重构。
- 后端测试已通过本轮验证，但稳定性仍需持续关注。
- 真实第三方失败场景仍缺少系统化在线验证矩阵。

## 下一阶段口径

下一阶段以收敛和稳定为主，不新增规划之外的大模块，不做大重构。优先级为：前端中文乱码、主链路决策、mock/legacy 文件清理、后端测试稳定性。
