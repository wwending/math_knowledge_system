# DECISIONS

说明：本文件按时间倒序记录决策。较早决策中的“当前主链路”等表述保留为当时历史事实；如与顶部较新决策冲突，以较新决策和 `docs/STATUS.md` 当前 checkpoint 为准。

## 决策 38：后端可观测性采用请求编号 + 双通道日志，测试证据本地落盘 + CI artifact

结论：

- 每个请求由 `RequestContextMiddleware`（纯 ASGI）分配或透传 `X-Request-ID`（非法入参替换为新 id），经 loguru `contextualize` 使既有全部 `logger.*` 调用自动携带编号，零调用点改动；响应头回传编号，请求结束写 `[Access] method/path/status/elapsed_ms` 行。
- 日志双通道：stderr + 滚动文件（rotation 10MB × retention 10、`enqueue=True`、`backtrace/diagnose=false`）；stdlib 与 uvicorn 日志经 InterceptHandler 汇入同一 sink。本地 `LOG_DIR=logs`（即 `backend/logs`，gitignore），生产 `LOG_DIR=/data/logs` 复用现有 `/data` 挂载，不新增 volume；`docker compose logs` 保持可用。
- 未捕获异常统一由全局 handler 返回 `500 {"detail": <中文提示>, "request_id": ...}` 并附响应头，完整堆栈带编号进日志文件；`/healthz` 增加 SQLite `SELECT 1`、`app_env`、`git_sha`，数据库故障返回 503 使容器 HEALTHCHECK 如实变红。
- 前端在识别调试面板条件渲染 `ocr_error`（error）/`llm_error`（warning），5xx 提示语附带请求编号；`backend/pytest.ini` 固定 `testpaths=tests` 与 `addopts=-q --tb=short -ra`；CI backend job 生成 JUnit XML 并以官方 SHA 固定的 upload-artifact v4.6.2 上传（`if: always()`）；`scripts/run_local_checks.ps1` 一键执行 compileall → pytest → 前端 contract → build，输出 tee 到 gitignored 的 `test_evidence/<时间戳>/` 并写 summary.txt。

原因：

- Issue #26 的核心痛点是报错无法溯源、测试证据无处可找。request_id 是把前端现象与后端堆栈关联起来的最小机制；文件日志解决“终端一关证据即失”；`diagnose=false` 防止 loguru 把变量值（可能含提示词/密钥片段）内联进日志。
- `/healthz` 引入 DB 检查是因为静态 200 无法暴露数据层故障；503 让 `docker compose ps` 直接可见。
- 本决策显式修订决策 31 “不改变 pytest 配置”的边界：`testpaths` 从根上消除根目录散落脚本破坏测试发现的历史故障模式（决策 31 的起因），`addopts` 统一人读与 CI 的报告格式。

边界：

- 不新增任何 Python/npm 依赖（loguru 已有）；不改动 OCR/LLM 业务逻辑；不触碰 `api/v1/endpoints.py`。
- Nginx access log 暂不加 `$request_id` 格式；`ocr_runs`/`llm_runs` 暂不做管理查询界面；compose 不自定义 json-file retention——均记入 KNOWN_ISSUES 作为可选后续。
- `/healthz` 从静态 200 变为 DB 检查语义属预期行为变化，已确认消费方（backend/web HEALTHCHECK、nginx 代理）均按非 2xx 视为不健康。

日期：2026-08-23

## 决策 37：题目图片只经鉴权接口服务，uploads 移出公开 static 挂载

结论：

- 题目相关图片字节只能通过 `GET /api/v1/questions/{question_id}/image` 读取；接口复用 `require_active_user` 并在 Question 层做所有权校验（404/403 语义与题目详情一致），以 `FileResponse` 流式返回磁盘文件。
- 所有权校验挂在 Question 上而不是 SourceAsset 上：`source_assets.sha256` 全局唯一去重，不同用户可能通过各自的 Question 引用同一 asset 行与同一份磁盘文件，asset 只是共享字节仓库。
- `UPLOAD_DIR` 默认值与生产布局改为公开 `/static` 挂载之外的独立目录（本地 `backend/uploads`、生产 `/data/uploads`），启动时 fail-closed 校验 uploads 不落在 `STATIC_DIR` 内；`deploy.sh` 负责把旧 `${DATA_ROOT}/static/uploads` 一次性迁移到新位置。
- API 返回的 `image_url` 改为指向鉴权端点；前端经全局 axios 实例（携带 Authorization、复用 401 refresh 重试）预取为 Blob 并以 object URL 渲染，组件卸载时释放。

原因：

- 公开 `/static/uploads` 使任何持有 URL 者绕过用户数据隔离读取图片字节，与 “User ownership/data isolation checks are security boundaries” 不变量冲突。
- cookie 会话方案会把图片鉴权语义扩散进静态服务层，短时签名 URL 方案引入额外密钥与时钟依赖；Blob 预取在现有 JWT 架构下改动最小。代价是失去浏览器自动缓存，后续可用 ETag/Cache-Control 找回。

边界：

- `/static` 挂载本身保留给非敏感资源（PDF.js 等前端资产）；`pdf_temp` 目录的公开可达性是遗留风险，单独记录于 `KNOWN_ISSUES.md`。
- 无数据模型变更、无新增 Alembic 迁移；历史 `origin_image` 值（裸文件名及遗留 `/static/uploads/...` 前缀）由后端解析层兼容。

日期：2026-08-23

## 决策 36：Control Checkout 与每 Issue 可写 worktree 分离

结论：

- `D:\math_knowledge_system` 固定为本地 Control Checkout，只用于管理、参考和只读 analysis/review/audit，不承载正常可写 Issue 实现。
- 每个可写 feature、fix、refactor、test、docs、chore、security 或 deploy Issue 使用一条 Issue-numbered branch、一个 linked dedicated worktree 和一个 Codex；同一 worktree 不允许并发 repository/file writers。
- 开始写入前必须核对 Issue、专用路径、branch/HEAD、worktree 映射、工作状态、无关改动和 ownership；发现未知或外部状态时 fail safe 停止，不用破坏性 Git 操作自行修复。
- 使用薄的本地 launcher 完成显式 base 解析、branch/worktree 安全 create-or-reuse，并通过新的 `codex exec -C <dedicated-worktree>` 进程启动 Worker；仅在旧 Codex shell 中 `cd` 到 sibling worktree 不等价于重新建立 Worker workspace/sandbox ownership。
- launcher 必须显式接收并验证 primary Control Checkout，拒绝 linked worktree 之间的祖先/后代路径重叠，并将按 repository/worktree identity 区分的 OS 独占文件 lease 与完整 Worker 进程树的生命周期耦合，确保不存在“旧 Worker 仍存活但 ownership 已可用”的状态；不同 worktree 的 lease 相互独立。

原因：

- 仅用 branch 不能隔离共享 checkout 的 index 和 working tree。一次真实并发 Codex 事故已造成 branch、index 与 working-tree 相互干扰的明确风险，因此工作空间本身也必须隔离。
- Control Codex 无法把 sibling worktree 变成自身新的可信写入根，因此自动 handoff 必须创建一个启动时就以 Task Worktree 为 workspace 的 Worker 进程；launcher 只负责 provision、isolate、launch、observe，不负责实现 Issue。

边界：

- linked worktree 只隔离各 checkout 的 `HEAD`、index 和 working files，不是 VM/container 安全边界；repository objects、refs、remotes 和多数 configuration 仍共享，相关变更必须保持克制。
- 完整预检、launcher 参数、hotfix 与安全退役流程由 `docs/ENGINEERING_WORKFLOW.md` 定义；Windows kill-on-close Job Object 与 supervisor-owned per-worktree lease 只是执行既有 ownership 规则的本地进程级原语，不是 locking service。本决策不引入 daemon、持久队列/数据库、远程 runner、自动 merge 或自动清理。
- Worker 使用 `workspace-write`、自动审批复核和仅指向 shared Git common-dir 的附加写目录；不默认使用 unrestricted/dangerous 模式，也不修改全局 Codex 安全配置。linked worktree 共享 Git 状态的风险仍由 branch/worktree 映射检查和 Worker 规则约束。

日期：2026-08-20（V2/V2.1 launcher 与 lease、V2.2 进程树生命周期耦合补充；原决策于 2026-08-19 建立）

## 决策 35：正常开发采用 Issue-first 与 PR 自动追溯门禁

结论：

- 正常 feature、fix、refactor、test、docs、chore、security 和 deploy 工作必须先有真实 GitHub Issue，再进入包含 Issue number 的任务分支与 PR 发布流程。
- 每个正常 PR 必须使用 GitHub closing keyword 关联当前仓库 Issue，默认使用 `Closes #123`，使合并后自动关闭 Issue。
- 独立的 `PR traceability` CI 检查会验证 closing reference、目标存在且不是 PR，并要求至少一个有效 Issue 早于 PR 创建。
- 此规则自治理 PR 合并后向前生效，不追溯重命名历史分支，也不重写已合并 PR 或批量补造 Issue。

原因：

- Issue、branch、commit 和 PR 分别承载需求根、实现空间、变更历史与审查合并单元；统一关联后可以从需求追溯到交付。
- 仅靠文档约定容易遗漏，最小只读 CI 门禁能在不引入 PAT、第三方 bot 或运行时服务的前提下稳定执行规则。

边界：

- 当前只接受本仓库 `#<number>` 形式的 Issue，不引入跨仓库追踪。
- main ruleset 是否把新 check 设为 required 由仓库管理员另行授权配置，本决策不自动修改 ruleset。

日期：2026-08-18

## 决策 34：试卷草稿编辑采用原子全量状态保存并保持题库快照隔离

结论：

- 使用 `PATCH /api/v1/papers/{paper_id}` 原子保存标题、描述和有序 items；仅 owner 的 `draft` 可编辑，跨用户资源继续按不存在处理。
- payload 区分已有 PaperItem 与从 Question 新增的 item。已有条目可修改当前试卷文本快照；新增条目的基础快照和元数据必须由服务端读取最新 QuestionRevision，客户端不能提交知识点、题型、难度或 revision id。
- 后端按 items 数组顺序重新生成连续 `position`，使用临时位置和分阶段 flush 避免 `(paper_id, position)` 交换时的瞬时唯一约束冲突。
- 删除、增加、排序和内容修改在同一事务内完成。试卷编辑绝不写 Question 或 QuestionRevision。
- Paper detail/list、预览和 PDF 继续以保存后的 Paper/PaperItem / PaperRenderModel 为唯一数据链，不创建第二套导出数据源。

原因：

- 全量草稿保存使前端可安全取消本地修改，也能在任一校验失败时避免半保存状态。
- 试卷是历史输出，题库是可继续演进的来源；两者必须通过 snapshot 边界解耦。

边界：

- 不新增数据库字段或迁移，不引入拖拽依赖；当前排序交互使用上移/下移。
- 学生版 render/PDF 继续不返回答案或解析，试卷详情仍保存并返回 owner 可编辑的答案/解析快照。

日期：2026-08-18

## 决策 33：正式 PDF 输出采用 PaperRenderModel + 内部 Gotenberg

结论：

- 正式打印输出链路固定为 `Paper -> PaperRenderModel -> controlled printable HTML -> Gotenberg Chromium -> PDF`。
- Browser preview 与 PDF 共享 `PaperRenderModel` 业务数据源；PDF renderer 不重新查询题目或复制分组、排序、编号逻辑。
- 浏览器只调用认证后的 Paper PDF API，不再用 `window.print()` 承担最终 PDF 生成，也不能提交任意 HTML 或 URL。
- Gotenberg 使用固定 Chromium-only 镜像，只加入 Compose 内部网络，不映射宿主机端口；禁用 JavaScript、`downloadFrom` 和公私网 HTTP(S) 子资源，并限制并发/队列；PDF 请求即时生成、即时返回，不持久化。
- 当前只开放 A4 portrait 默认 profile，但 PDF abstraction 已表达 paper size、orientation 和四边 margin。
- Markdown 原始 HTML、远程资源和危险 LaTeX 命令不进入可执行渲染面；服务端使用离线 MathML 表达常用数学公式。

原因：

- 将预览业务模型与最终输出媒介分层，未来增加 A3、landscape、页边距 profile、教师版时不需要重构 Paper 数据链路。
- FastAPI 到内部 Gotenberg 是当前资源约束下最短、可 mock、可部署的服务端 PDF 生产链路。
- 服务端控制 HTML 和 Chromium 目标，可以避免暴露通用 HTML/URL-to-PDF 接口带来的 SSRF 与任意内容执行风险。

边界：

- 本轮不实现 A3 UI、教师版、答案解析、booklet/imposition 或实体打印机控制。
- PDF 文件不能可靠强制物理打印机开启 duplex；后续只能实现 duplex-aware page layout / imposition 策略。

日期：2026-08-09

## 决策 32：v0.1 采用 Nginx + 单 FastAPI 容器的单机部署

结论：

- 浏览器只访问 Nginx Web 容器；Nginx 提供 Vue dist，并代理 `/api/`、`/static/` 和 `/healthz`。
- FastAPI 容器不向公网映射 `8000`，使用 Python 3.11 slim、非 root 用户和 1 个 Uvicorn worker。
- SQLite、上传文件和 PDF 临时目录通过 `/data` 映射到 `/srv/math-knowledge/data`，不依赖临时容器层。
- schema 只由部署脚本显式运行 `alembic upgrade head`；生产运行时 schema 变更开关保持关闭。
- 第一阶段只支持 IP + 指定 HTTP 端口的 RC smoke；正式 HTTPS 由外部可信 TLS 终止层提供，不在仓库中保存证书。
- 数据库备份使用 SQLite Backup API，不用普通文件复制假设在线数据库一致。

原因：

- v0.1 需要在不扩大业务与基础设施范围的前提下获得可重复部署、迁移、健康检查和备份能力。
- 单机 SQLite 与单 worker 符合当前负载和状态边界，也避免引入 PostgreSQL、Redis、Celery 或 Kubernetes。

边界：

- 不改变 OCR、LLM、Draft、题库、组卷或 legacy recognize 业务逻辑。
- 不宣称已完成目标 Linux 服务器、真实外部服务或正式 HTTPS 验收。

日期：2026-08-05

## 决策 31：自动化测试与手工调试脚本分目录管理

结论：

- 后端自动化测试统一放在 `backend/tests/`，或未来明确约定的测试目录中。
- 手工 API / LLM / 第三方服务调试脚本放在 `backend/scripts/manual/`。
- 手工脚本文件名不使用 `test_*.py`，避免被 pytest 自动收集。
- 手工脚本可以依赖本地 `.env` 和真实第三方配置，但不能作为自动化测试的一部分。

原因：

- 根目录历史 `test_deepseek.py` 是手工调试脚本，因命名符合 pytest 默认收集规则，导致 `python -m pytest` 失败。
- 自动化测试应可离线、可重复，不依赖真实 DeepSeek API key、外部网络或真实 LLM 响应。
- 保留手工脚本的调试意图，同时让自动化测试边界清晰。

边界：

- 本决策不改变 pytest 配置。
- 本决策不恢复已废弃的 `correct_text` 接口。
- 本决策不修改 LLM 服务主逻辑。

日期：2026-06-16

## 决策 30：OCR Provider 支持配置切换，RapidOCR 作为本地实验 Provider

结论：

- Draft OCR Provider 支持通过 `OCR_PROVIDER=baidu` / `OCR_PROVIDER=rapidocr` 切换。
- `baidu` 仍是默认和稳定 provider，保护既有 Draft 识别流程。
- `rapidocr` 作为本地 OCR 实验 provider 接入，不改变 Draft recognize API、前端或数据库模型。
- RapidOCR 依赖为可选依赖，默认 requirements 不强制安装；仅当配置为 `rapidocr` 并执行识别时才延迟导入。
- OCRService 按 provider 名称缓存 provider 实例，RapidOCR provider 内部缓存本地 engine，避免每次识别重复初始化。

原因：

- 百度 OCR 后续部署成本较高，需要先打通本地 OCR provider 的工程切换能力。
- 当前目标是验证 provider 可切换，不是立即证明 RapidOCR 识别质量优于百度。
- 可选依赖和默认 baidu 能避免未安装 rapidocr 时破坏现有稳定流程。

边界：

- 不删除 `BaiduOcrProvider`。
- 不启用 OCR fallback 链。
- 不修改 legacy `/api/v1/recognize`、前端、数据库模型或 Draft API 契约。
- RapidOCR 的数学公式、版面和双栏选项识别能力需要后续真实题图评估。

日期：2026-06-16

## 决策 29：LLM 清洗必须采用保真整理模式，并暴露 OCR/LLM 可回溯信息

结论：

- Draft LLM 文本清洗定位为“高中数学 OCR 文本保真整理器”，不是解题老师、题目改写器或补题工具。
- LLM prompt 必须明确禁止猜题、补题、改题意、替换变量/点名/线段名/焦点编号、删除看似残缺的选项或将一个数学表达式改写成另一个数学表达式。
- Draft detail 响应应提供可选 `recognition_debug`，让用户能比较 OCR 原文和 LLM 清洗文本。
- `recognition_debug` 优先复用已有 `OCRRun`、`LLMRun`、`Draft.current_content`，不为了调试字段新增迁移。

原因：

- 本地 smoke 暴露了公式可能被误改、选项可能丢失、椭圆题命题可能被 LLM 改写的问题。
- 在无法确定错误来自 OCR 还是 LLM 前，继续切换 OCR provider 会扩大变量，不能稳定定位根因。
- 高中数学题中变量、焦点编号、线段名、选项和表达式都是题意的一部分，LLM 自行“合理化”会造成严重题意篡改。

边界：

- 本决策不表示 OCR 准确率已提升。
- 本决策不接入 RapidOCR、PaddleOCR、Pix2Text 或云 fallback。
- 本决策不改变 legacy `/api/v1/recognize`、OCRService provider 选择逻辑、BaiduOcrProvider 或数据库模型。

日期：2026-06-16

## 决策 28：先建立 OCR 评估集，再接入本地 OCR provider

结论：

- 在接入 RapidOCR、PaddleOCR、Pix2Text 或其他本地 OCR provider 前，先建立 OCR eval case、prediction 和文本级评估指标。
- 本轮评估只使用已有 `predicted_text` 离线计算，不调用真实 OCR provider。
- 评估指标先覆盖 exact match、normalized exact match、文本相似度、长度差、关键术语召回、错误数和耗时汇总。
- 真实图片样本后续可以放在本地或对象存储，不把大图片提交进 Git。

原因：

- 直接切换 OCR provider 容易变成凭感觉比较，无法稳定判断识别质量、耗时和失败率。
- 百度 OCR 成本问题需要解决，但质量评估标准应先于 provider 替换。
- 当前项目处理高中数学题，公式、图形和版面问题复杂，必须明确文本级指标的边界。

边界：

- 当前指标不是数学公式语义评估。
- 不覆盖几何图、版面结构或 OCR 后 LLM 清洗质量。
- 不修改 Draft recognize、legacy `/api/v1/recognize`、数据库模型、前端或 OCRService provider 选择逻辑。

日期：2026-06-16

## 决策 27：Draft OCR 引擎改为 Provider 模式，百度仍为默认 provider

结论：

- Draft recognize 不再直接绑定百度 OCR 引擎实例，改为通过 `OCRService` 调用 `OcrProvider`。
- Provider 内部统一返回 `OCRResult`，便于后续接入本地 OCR、云 OCR fallback 和可观测性字段。
- 现有百度 OCR 逻辑仅封装为 `BaiduOcrProvider`，不改变 `ocr_engine.py` 的识别逻辑、错误口径或文本拼接方式。
- `OCR_PROVIDER` 默认 `baidu`；当前实际只支持 `baidu`。
- `OCR_FALLBACK_PROVIDER` 仅作为配置预留，本轮不启用 fallback 链。
- legacy `/api/v1/recognize` 保持继续调用既有 `ocr_engine.ocr_service`，不纳入本轮改造。

原因：

- 未来部署在低配服务器时，需要为 RapidOCR / PaddleOCR / Pix2Text 等本地 OCR 和百度云 fallback 留出切换点。
- 先抽象 Provider 可以降低供应商锁定风险，但不在本轮扩大为 OCR 引擎替换或成本优化。
- 保持百度为默认 provider 可以保护当前 Draft 识别行为和验收基线。

边界：

- 不接入本地 OCR。
- 不新增数据库字段或迁移。
- 不修改 PaperRenderModel、PaperPreview 或前端主页面。
- 不删除百度 OCR。
- 不改变 legacy `/api/v1/recognize`。

日期：2026-06-06

## 决策 26：PaperRenderModel 由后端生成，前端只负责展示

结论：

- 新增 `POST /api/v1/papers/{paper_id}/render-model`，由后端将 Paper / PaperItem 快照转换为稳定 PaperRenderModel。
- PaperRenderModel 独立放在 `backend/app/schemas/paper_render.py` 和 `backend/app/services/paper_render_service.py`，避免扩大既有 Paper schema/service 职责。
- 当前只支持 `homework` 模板、`student` 版本、`A4`、按 `question_type` 分组、按 `position` 排序。
- 学生版响应层面不返回答案或解析快照，前端不承担隐藏敏感字段的责任。
- 前端新增 `PaperPreview.vue` 负责 A4 视觉展示，并复用共享 Markdown / LaTeX 渲染工具。
- 后续 PDF / DOCX 导出应优先复用 PaperRenderModel，而不是重新读取 PaperItem 并各自拼装结构。

原因：

- 预览、PDF、DOCX 的核心内容结构应保持一致，避免不同导出通道各自实现排序、分组、题型兜底和答题区逻辑。
- 后端生成模型可以统一权限、学生版字段裁剪和历史数据归一化。
- 前端只做展示可以降低后续模板扩展和导出接入的分叉风险。

边界：

- 不新增数据库表，不修改 Paper / PaperItem 模型，不做数据库迁移。
- 不做 PDF / DOCX 导出。
- 不做自定义模板、模板编辑器、自动分页、拖拽排序、知识点排序、难度排序或复杂答题卡。
- 不修改 Draft flow 或 legacy `/api/v1/recognize`。

日期：2026-06-06

## 决策 25：题型与难度元数据改为保存后后台补全

结论：

- 交互式 `POST /api/v1/drafts/{draft_id}/recognize` 优先保证 OCR、`corrected_text` 和知识点标签快速返回。
- 题型和五星难度作为增强元数据，不再阻塞 Draft recognize 主链路。
- `POST /api/v1/drafts/{draft_id}/save-to-bank` 创建 `Question` 后将 `metadata_status` 设为 `pending`。
- 当前使用 FastAPI `BackgroundTasks` 调用后台任务补全 `question_type`、`difficulty_level`、`difficulty_label`、`difficulty_confidence`、`difficulty_reason`、`difficulty_model` 和 `difficulty_evaluated_at`。
- 后台任务内部新建 DB session，不复用请求 session。
- 后台任务失败只更新 `metadata_status=failed` 和 `metadata_error`，不回滚已经保存入题库的结果。
- 当前不引入 Celery / Redis；未来如果部署并发压力或任务可靠性要求提高，再迁移到真正任务队列。

原因：

- 用户录入题目时更关心 `corrected_text` 主结果，题型和难度是后续题库/组卷增强能力。
- 同步 recognize 同时承担 OCR、洗稿、知识点、题型和难度评估会让交互等待变长。
- 使用 `BackgroundTasks` 可以在当前架构内完成最小性能收口，不扩大基础设施复杂度。

边界：

- 不改变 Draft 状态机。
- 不删除 legacy recognize。
- 不做自动轮询、WebSocket、重新评估按钮、智能组卷、模板、导出或答题区域。
- 后台任务依赖当前后端进程，服务重启可能丢失正在执行的元数据评估任务。

日期：2026-06-04

## 决策 24：LLM 洗稿阶段同时生成题型与五星难度元数据

结论：

- LLM analyze 从“文本清洗 + 知识点标签”扩展为“题目结构化分析”。
- `corrected_text` 仍是主结果，继续优先保障识别和保存流程。
- `question_type` 和 `difficulty` 是增强结果；`difficulty` 缺失或非法时不阻断 Draft recognize。
- 后端兼容旧 `tags` 字段，并将其归一为 `knowledge_tags`。
- Draft 使用独立 nullable 字段暂存题型与难度，避免把 `current_content` 从正文结果扩展成复杂元数据载体。
- Question 保存最终题型与难度；PaperItem 保存可选题型与难度快照。

五星评分标准：

- 1星：基础识记题，直接套概念或公式即可完成。
- 2星：基础应用题，单一知识点，一到两步计算。
- 3星：中等综合题，涉及两类知识点或多步推理。
- 4星：较难综合题，需要分类讨论、复杂计算或较强转化能力。
- 5星：压轴难题，需要抽象建模、创新构造或高综合能力。

原因：

- 后续按题型、知识点、难度组卷需要题库层稳定保存元数据。
- 难度评估来自 LLM，可信度低于 `corrected_text`，因此不能让增强字段失败影响主识别流程。
- PaperItem 快照可以保持已创建试卷的题型和难度展示稳定。

边界：

- 不做按难度排序、按知识点排序、组卷模板、PDF / DOCX 导出、答题区域或智能组卷。
- 不改变 Draft flow 状态机。
- 不删除 legacy recognize。
- 用户编辑题目后不会自动重新评估题型或难度。

日期：2026-06-04

## 决策 23：前端组卷入口采用 BankPanel 选题 + PaperPanel 展示

结论：

- 在 `BankPanel.vue` 中增加最小选题和创建试卷入口。
- 新增 `PaperPanel.vue` 作为试卷列表和试卷详情的独立展示组件。
- `Dashboard.vue` 新增独立“组卷”菜单入口，避免组卷 UI 干扰题目录入、Draft 保存入库、题库查看和历史记录。
- 前端继续沿用现有 axios 全局 token 注入，不新增统一 API 层或状态管理。

原因：

- 本轮目标是前端组卷入口 MVP，不是前端结构重构。
- 题库选题最贴近现有题库列表，放在 `BankPanel.vue` 能减少跨组件状态复杂度。
- 试卷列表和详情是独立展示职责，拆成 `PaperPanel.vue` 可以避免继续扩大 `BankPanel.vue` 的展示责任。
- 复用 `renderMarkdown.ts` 能保持题目内容、答案、解析的 Markdown / LaTeX 渲染规则一致。

边界：

- 不修改后端 Paper API 主逻辑。
- 不修改 Draft flow。
- 不修改 legacy recognize。
- 不做导出、智能组卷、拖拽排序、分值编辑、复杂排版或打印样式优化。

日期：2026-06-03

## 决策 22：组卷 MVP 使用 Paper + PaperItem 并保存题目快照

结论：

- 新增 `Paper` 表表示一张试卷草稿。
- 新增 `PaperItem` 表表示试卷中的题目条目，按请求顺序生成 `position`。
- `PaperItem` 关联 `question_id`，并在存在 `QuestionRevision` 时记录当前最新 `question_revision_id`。
- `PaperItem` 同时保存 `content_snapshot`、`answer_snapshot`、`analysis_snapshot`、`knowledge_tags_snapshot`。

原因：

- 组卷 MVP 当前目标是后端最小手动选题竖切，不引入智能组卷、导出或前端复杂交互。
- 题库题目后续可能被编辑，如果试卷只动态读取 Question 当前内容，历史试卷会被动变化。
- 保存快照可以保证已创建试卷内容稳定，同时保留与题库题目的关联。
- 当前 `QuestionRevision` 已存在，但历史题目不一定都有完整 revision；因此同时保存快照作为稳定兜底。

边界：

- 当前不做智能组卷算法。
- 当前不做 PDF/Word 导出。
- 当前不做前端组卷入口。
- 当前不做拖拽排序或自动配比。
- 不改变 Draft flow、legacy recognize 或题库保存逻辑。

日期：2026-05-27

## 决策 21：保留两个 Draft smoke 文档并明确主次

结论：

- 保留 `docs/API_SMOKE_DRAFT_FLOW.md` 和 `docs/API_SMOKE_DRAFT_PIPELINE.md`，本轮不合并、不删除。
- `docs/API_SMOKE_DRAFT_FLOW.md` 作为当前推荐 smoke 文档，负责 Dashboard Draft 主路径、异常契约、legacy 边界和人工/API 验收标准。
- `docs/API_SMOKE_DRAFT_PIPELINE.md` 作为脚本化 smoke 补充文档，负责 `scripts/smoke_draft_pipeline.ps1` 的执行方式、参数和脚本断言说明。

原因：

- 两个文档存在部分 API 顺序重复，但受众不同：一个用于理解和人工核查，一个用于脚本执行。
- 合并会让主路径验收口径和脚本参数说明互相干扰，后续维护成本不一定更低。
- 明确主次和互链可以降低维护者误读风险，同时保持现有链接不失效。

边界：

- 不删除任何 smoke 文档。
- 不改变 Draft API 或业务行为。
- 后续修改 Draft 主链路或 smoke 脚本时，应同步检查两个 smoke 文档。

日期：2026-05-27

## 决策 20：legacy recognize 先审计标注，后续小步退场

结论：

- 当前 Dashboard 上传主路径继续以 Draft 流水线为基线。
- `POST /api/v1/recognize` 和 `runLegacyRecognition()` 本轮不删除、不重构，作为 legacy / 兼容入口保留。
- 后续清理顺序应先补足引用审计和测试保护，再评估是否隐藏、废弃或移除 legacy 入口。

原因：

- Dashboard 主流程已经不调用 `runLegacyRecognition()`，直接删除 legacy 入口会扩大兼容风险。
- 后端仍有 `/api/v1/recognize` 失败路径测试覆盖，说明该入口仍有明确兼容价值。
- 本轮目标是降低误用风险，而不是改变业务行为。

边界：

- 不把 legacy recognize 描述成当前 Dashboard 主路径。
- 不删除 `/api/v1/recognize`。
- 不删除 `runLegacyRecognition()`。
- 不修改 OCR / LLM service 或数据库模型。

日期：2026-05-27

## 决策 19：Draft 重复保存当前返回 409 而不是幂等结果

结论：

- 当前 Draft 流程中，Draft 已达到 `saved_to_bank` 状态后，再次调用 `POST /api/v1/drafts/{draft_id}/save-to-bank` 返回 `409 Conflict`。
- 当前不重建并返回已有的保存结果。

原因：

- 防止重复创建 `Question` / `QuestionRevision`。
- 保持当前实现小而明确。
- 在保存结果模型完全稳定前，避免提前引入幂等响应重建逻辑。

影响：

- 前端应将该行为视为可恢复的状态冲突。
- 后续可升级为幂等返回既有 `question_id` / `question_revision_id` / `rev_no`。

日期：2026-05-27

## 决策 18：接受 Dashboard Draft 初步接入为新的前端主路径基线

结论：

- 第十一轮补充确认，当前 `Dashboard.vue` 上传主路径已初步接入 Draft 流水线。
- 上传按钮链路为：图片/PDF 单页确认后调用 `runRecognition()`，依次请求 `POST /api/v1/assets`、`POST /api/v1/drafts`、`POST /api/v1/drafts/{draft_id}/recognize`。
- 保存入题库调用 `POST /api/v1/drafts/{draft_id}/save-to-bank`。
- `runLegacyRecognition()` 仍保留，并继续调用 `POST /api/v1/recognize`，但当前上传按钮和主上传流程不引用它。
- 接受该状态作为新的前端主路径基线。
- `POST /api/v1/recognize` 不删除、不重构，定义为 legacy / 兼容入口。

原因：

- 代码事实已经显示 Dashboard 上传主流程走 Draft 接口，继续保留“尚未接入主前端”的口径会误导后续开发。
- Draft 前端接入符合既定渐进式迁移方向，可作为路线推进接受。
- 当前接入仍不是完整生产级完成，仍需补 API smoke 文档、异常场景、UI 状态和 legacy 清理。
- 当前项目仍只表述为“可启动、可验证、可继续开发”，不表述为生产可用。

边界：

- 不删除 `/api/v1/recognize`。
- 不删除 `runLegacyRecognition()`。
- 不做异步队列、批量 PDF、多页 draft 或 OCR/LLM provider 抽象。
- 不声称 Draft 已完整生产可用。

日期：2026-05-27

## 决策 17：前端 Markdown/LaTeX 渲染逻辑统一收敛到共享工具

结论：

- 将 `Dashboard.vue`、`BankPanel.vue`、`HistoryPanel.vue` 中重复的 `markdown-it + markdown-it-mathjax3` 渲染逻辑抽取到 `frontend/src/utils/renderMarkdown.ts`。

原因：

- 避免多个组件各自维护 Markdown/LaTeX 渲染规则。
- 确保识别结果、题库详情、历史详情使用一致的渲染行为。
- 为历史数据或异常数据中的 `\(...\)` / `\[...\]` 提供展示层兜底。
- 后续如果需要调整 Markdown 配置、LaTeX 兼容规则或渲染安全策略，只需要修改一个入口。

边界：

- 不改变后端返回结构。
- 不改变原始题目内容。
- 只在展示前做格式归一化。
- 本轮不处理 `katex` 冗余依赖和 `markdown-body` 样式问题。

日期：2026-05-26

## 决策 16：Draft 流水线先作为后端旁路能力

结论：

- 第七轮新增 Draft 后端旁路正式流水线最小竖切。
- 新增接口为 `POST /api/v1/drafts`、`GET /api/v1/drafts/{draft_id}`、`POST /api/v1/drafts/{draft_id}/recognize`、`POST /api/v1/drafts/{draft_id}/save-to-bank`。
- Draft 状态流转为 `draft_created`、`recognizing`、`draft_ready`、`failed`、`saved_to_bank`。
- `DraftEvent` 会记录创建、开始识别、识别成功/失败、保存入题库。
- `OCRRun` 在 Draft 识别后写入，失败也记录错误。
- `LLMRun` 在 OCR 成功后写入，LLM 失败记录错误并允许 `partial_success`。
- `QuestionRevision` 在保存入题库时创建 v1，并关联 `source_asset_id`、`ocr_run_id`、`llm_run_id`。
- 当前前端主链路仍然是 `/api/v1/recognize`。
- `Dashboard.vue` 尚未切换到 Draft 流水线。
- `/api/v1/recognize` 未删除、未重构，仍是当前 MVP 主入口。

原因：

- 先让正式流水线具备可验证的后端旁路能力，可以降低直接切换主前端的风险。
- 当前 MVP 主入口仍可用，立即硬切前端会扩大验证面。
- 下一阶段更适合先补 API smoke 文档或做前端接入方案评估。

日期：2026-05-07

## 决策 15：主链路采用渐进式迁移

结论：

- 选择 C：短期继续使用 `POST /api/v1/recognize`，长期逐步迁移到 `assets/drafts/ocr_runs/llm_runs` 正式流水线。
- 当前主链路仍是 `/api/v1/recognize`。
- `/upload_pdf`、`/assets`、drafts 当前不是主前端闭环。
- 下一阶段目标是新增最小正式流水线后端竖切，不影响现有前端。
- 不要删除 `/recognize`。
- 不要现在硬切 `Dashboard.vue`。
- 不要做 OCR/LLM provider 抽象、异步队列、批量 PDF、多页 draft 管理。

原因：

- 当前 `/recognize -> questions -> history/bank` 已经跑通，是现有可用 MVP 主链路。
- `assets/drafts/ocr_runs/llm_runs` 已有模型和迁移，但缺少主接口、schema、前端闭环和测试。
- 现在硬切正式流水线风险过大。
- 继续只维护 `/recognize` 又会让正式流水线长期架空。
- 因此采用渐进式迁移：先新增后端正式流水线竖切，不影响现有前端；验证通过后再切 Dashboard。

日期：2026-05-07

## 决策 14：第三轮只做文档和示例配置收口

结论：

- 第三轮只允许修改文档和示例配置文件。
- 不修改业务代码、测试代码、前端代码、后端代码。
- `backend/.env` 作为本地文件，不应提交；需要示例配置时使用 `backend/.env.example`。

原因：

- 第二轮已经完成必要修复与验证，本轮目标是让交付口径一致。
- 继续改代码会扩大本轮范围，干扰“文档收口”的判断。

日期：2026-05-05

## 决策 13：当前状态表述为“可启动、可验证、可继续开发”

结论：

- 当前项目可以表述为“可启动、可验证、可继续开发”。
- 不表述为生产可用。
- 不夸大 `/upload_pdf`、`/assets`、draft 流水线的完成度。

原因：

- 第二轮验证命令已通过，但仍存在前端中文乱码、主链路决策、mock/legacy 清理、后端测试稳定性等后续工作。
- `assets/drafts/ocr_runs/llm_runs` 已建模，但未形成主前端闭环。

日期：2026-05-05

## 决策 12：当前主链路仍是 `/api/v1/recognize`

结论：

- 当前主链路继续按 `POST /api/v1/recognize` 说明。
- `assets/drafts/ocr_runs/llm_runs` 作为正式流水线预留。
- `/upload_pdf`、`/assets`、draft 流水线目前不写成主前端已接入能力。

原因：

- 主前端闭环尚未切到 draft 流水线。
- 文档必须反映当前可验证事实，而不是按未来结构提前表述完成。

日期：2026-05-05

## 决策 11：下一阶段避免大重构

结论：

- 下一阶段优先处理前端中文乱码、主链路决策、mock/legacy 文件清理、后端测试稳定性。
- 不新增规划之外的大模块。
- 不以大重构方式解决当前收敛问题。

原因：

- 当前项目刚进入可启动、可验证状态，优先级应是稳定和收敛。
- 大范围重构会削弱第二轮已经建立的验证基线。

日期：2026-05-05

## 决策 10：`alembic upgrade head` 是硬前置

结论：

- 后端启动、管理员初始化和共享环境验证前必须执行 `alembic upgrade head`。
- 不依赖运行时 `create_all` 或兼容补表替代正式迁移链。

原因：

- 数据库 schema 的正式演进需要单一可信路径。
- 运行时兜底会让本地和目标环境行为分叉。

日期：2026-03-24

## 决策 9：README / STATUS / WORKLOG / DECISIONS / KNOWN_ISSUES 职责边界

结论：

- README 负责启动、配置、验证和当前能力边界。
- STATUS 负责当前阶段状态和当前门禁结论。
- WORKLOG 记录时间线，不承载当前唯一真相。
- DECISIONS 记录为什么这样定。
- KNOWN_ISSUES 记录当前未解决边界与风险。

原因：

- 多个文档同时承载当前真相会导致重复、冲突和过时结论并存。
- 明确职责后，后续维护可以判断应修改哪个文件。

日期：2026-04-20
