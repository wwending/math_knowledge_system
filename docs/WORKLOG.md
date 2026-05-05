# WORKLOG

日期：2026-04-20  
说明：测试与交付治理收口

## 10. 固定最小回归测试集与发布门禁

原因：

- 现有仓库已经有前端契约测试、后端关键单测和人工验收清单，但入口分散，发布前依赖人工记忆。
- README、STATUS、验收清单之间同时承担“当前真相源”职责，容易在交付口径上互相覆盖。

结果：

- 在 [README.md](/d:/math_knowledge_system/README.md) 固定了当前最小回归测试矩阵。
- 在 [README.md](/d:/math_knowledge_system/README.md) 与 [docs/auth-acceptance-checklist.md](/d:/math_knowledge_system/docs/auth-acceptance-checklist.md) 固定了发布前命令顺序、人工 smoke 和失败即阻断条件。
- 明确后端门禁依赖已安装 `backend/requirements.txt` 的 Python 环境，不再默认裸解释器可直接执行。

## 11. 固定文档职责边界并清理过时交付结论

原因：

- 当前最容易误导后续维护的，不是测试不存在，而是历史快照和当前状态混写。
- `access token + refresh session` 已经是当前事实，但部分文档仍保留“只有 access token”的旧结论。

结果：

- [docs/STATUS.md](/d:/math_knowledge_system/docs/STATUS.md) 改为只保留当前状态、当前门禁和当前未闭合边界。
- [docs/KNOWN_ISSUES.md](/d:/math_knowledge_system/docs/KNOWN_ISSUES.md) 删除已失真的会话结论，保留真正仍未解决的风险。
- [docs/DECISIONS.md](/d:/math_knowledge_system/docs/DECISIONS.md) 新增发布门禁与文档职责边界两条治理决策。
- 历史快照与历史设计稿继续保留，但不再作为当前发布判断依据。

日期：2026-03-24  
说明：数据库迁移治理收口修复

## 9. 收紧数据库 schema 正式路径与兼容路径边界

原因：

- Alembic 已经引入，但应用启动和测试初始化仍保留 `create_all` 与运行时补列旁路。
- 这会让“正式迁移成功”和“运行时兜底成功”同时成立，导致部署、验收和环境切换时行为分叉。

结果：

- 新增 `ALLOW_RUNTIME_SCHEMA_MUTATIONS` 作为数据库治理专用显式边界。
- production 环境无条件禁止运行时 schema 变更。
- 非 production 环境也只有在显式允许时，`AUTO_CREATE_TABLES` 与 `AUTO_APPLY_LEGACY_QUESTION_COMPAT` 才允许生效。
- `backend/tests/test_auth_stage3.py` 改为 fresh DB + `upgrade_database(db_url)` 后再跑最小 auth smoke。
- `docs/DELIVERY_2026-03-19.md` 继续保留为历史快照，不再代表当前数据库迁移治理结论。

日期：2026-03-19  
说明：未保留精确时分，以下按今天的处理顺序记录。

## 1. 先收配置，去掉对 `cwd` 的隐式依赖

原因：

- 原来的路径解析和启动方式对当前工作目录敏感，容易出现“能在某个目录跑，换个目录就不行”的问题
- 今天的目标不是继续堆脚本，而是先把启动与路径规则收敛

结果：

- 配置统一收敛到 `backend/app/core/config.py`
- `STATIC_DIR / UPLOAD_DIR / PDF_TEMP_DIR / DATABASE_URL` 改为按后端目录解析
- 运行时目录创建放到应用启动侧
- 从仓库根目录启动后端成为稳定方式，`cwd` 依赖基本消除

## 2. 修 `Question` 旧契约，保证老库能继续读写

原因：

- 现有库与当前代码对 `questions` 表字段预期不完全一致
- 如果不先做兼容，今天其它链路即使接通，也会在老数据或老库结构上出问题

结果：

- 增加了启动时的兼容补列逻辑
- 老库缺 `content / knowledge_tags / origin_image` 时可补齐
- 今天选择的是兼容修复，不是引入正式迁移体系

## 3. 接前端真实 JWT 登录

原因：

- 前端还保留假 token 时，今天所有“真实链路是否可用”的结论都不成立
- 登录必须先切到真实接口，后面的会话、鉴权、跳转和错误提示才有意义

结果：

- 登录页改为调用真实 `/api/v1/auth/token`
- 本地 token 存储、请求附带、`401` 清理和路由守卫形成一条线
- 登录失败、缺 token、无效 token、过期 token 的用户提示同步收口

## 4. 统一图片 URL

原因：

- 题库、历史、识别结果各自处理图片地址，会导致前后端约定松散
- 老数据仍保留 `origin_image`，新接口又需要稳定给前端可直接消费的地址

结果：

- 后端开始统一返回 `image_url`
- 前端改为统一解析图片地址
- 兼容期仍保留对 `origin_image` 的读取，避免一次性打断旧数据

## 5. 收口 OCR / LLM 失败路径

原因：

- 今天真正的交付风险不在“正向能不能跑”，而在失败时是否会崩、是否会误导用户、是否会留下脏数据

结果：

- OCR 全失败时不再伪装成功，也不再落库
- OCR 成功但 LLM 失败时改为 `partial_success`
- 这种情况下页面保留 OCR 原文，并给出 warning
- 文件保存失败、数据库保存失败继续归类为内部错误，不和第三方失败混在一起

## 6. 完成人工浏览器验收

原因：

- 只看接口代码不足以说明前端真实交互是否闭环
- 今天必须确认登录、上传、结果展示和会话处理在浏览器里是真的通的

结果：

- 今日人工浏览器验收已完成
- 已确认真实 JWT 登录可用
- 已确认正向页面链路可走通
- 已确认失败时前端不会直接退化成空白页或假成功

## 7. 确认真实第三方成功返回

原因：

- 如果百度 OCR 和 LLM 只是 stub 通，今天的交付状态不能写成主链路可用

结果：

- 已确认百度 OCR 真能返回
- 已确认 LLM 真能返回
- 因此今天可以客观写明：正向主链路已通过到真实第三方成功返回

## 8. 明确今天没有做完的部分

原因：

- 交付文档必须留下清晰边界，避免后续把“没系统验证”误读成“已经没问题”

结果：

- 真实第三方失败场景的在线烟雾测试被明确保留为后续项
- 已知风险集中在第三方异常、部署差异、静态资源策略和迁移体系缺失
- 今天的交付定位被定为“可提交、可交接、可继续补烟雾测试”，而不是“已经全量验收完毕”
