# DECISIONS

## 决策 49：作答空间按 PaperItem 的标准物理行数持久化（#126）

`response_line_count` 是 PaperItem 的卷内展示设置，不属于 Question 或冻结内容快照；值域为整数 `0..24`，新项与历史项默认 6。删除后重加创建新 PaperItem，因此恢复默认值而不恢复旧设置。用户只写行数，后端渲染模型计算 `height_mm = response_line_count × 8`；正数作答区另有固定 4mm 顶部间距，纯白、无横线、不可拆，0 不产生元素或间距。

标题、说明、显示开关、题序、分值、增删题与逐题行数共享一次全量原子 PATCH。浏览器编辑预览消费本地草稿，PDF 始终消费服务端保存值，未保存时前端禁止导出。显示答案/解析或旧 `answer_area_mode=none` 只隐藏本次渲染的作答区，不改持久行数；旧 `after_each_question` 使用逐题值，不再保留固定 50mm 的第二套高度语义。

## 决策 48：PaperItem schema-v2 是不可变三区段/多图快照（#133）

建卷或重新添加题目时，服务端从最新 QuestionRevision 冻结完整 `section_snapshot`，并把该 revision 的全部配图资产引用复制到 PaperItemFigureSnapshot；显示开关不影响冻结范围。正常 Paper 写入只允许卷级标题、说明、显示开关，以及条目顺序、分值和增删题，PaperItem 内容、图片和布局不提供编辑或“同步最新”入口。

浏览器预览与 HTML/PDF 消费同一 section/block/placement 模型。图片区保持归一化布局和比例并整体不可拆分；超过单页可打印内容高度时失败，不自动缩小。任一声明图片不可读时预览/PDF fail closed。多图 Blob 按 Paper owner 鉴权，旧单图快照保留兼容通道。`show_answer` / `show_analysis` 默认关闭，开启任一项即隐藏逐题作答区。

## 决策 47：题库只读详情按生命周期分流并仅加载可见区段配图（#132）

结论：Active 题目详情以 owner-scoped document API 的 canonical schema-v2 文档为唯一展示源，题干、答案、解析通过共享只读 ordered block renderer 按原序渲染；图片区沿用 normalized placement canvas。题目区域图继续由 question image loader 独立加载，用于列表缩略图和详情左栏，不得以某张 figure 替代。

figure Blob 注册表只把当前可见区段 placement 引用的 figure ID 视为 reachable：空区段、纯文字区段和未激活 tab 不发请求；切换区段或题目、关闭详情及组件卸载时撤销不可达 Object URL，迟到 Blob 立即创建后撤销，避免污染当前题目。回收站继续消费既有 flat lifecycle endpoint，并适配为 text-only sections；不为展示一致性放宽 document/figure 的 active-only ownership 与生命周期边界。

原因：schema-v2 的有序文字/图片区和多图 placement 无法由 flat 投影忠实恢复，而题目区域图与题内配图属于不同语义和资源生命周期。按可见区段惰性加载既保留正式布局，又避免空区段、隐藏 tab 和已关闭详情产生无用鉴权请求或 Blob 泄漏；回收站保持 flat 投影可避免扩大已删除资源访问面。

边界：共享 renderer 供后续页面复用，但本期不接入 Paper/HTML/PDF；不新增 endpoint、数据库迁移、依赖，也不改变认证、授权和 owner isolation 语义。

日期：2026-08-30

## 决策 46：schema-v2 图片区编辑采用纯文档历史与外置 Blob 注册表（#131）

结论：题目编辑器唯一可保存事实源是纯 JSON schema-v2 draft，完整页面撤销/重做只记录 `baseline/past/present/future` 文档快照；Blob、object URL、Canvas、指针临时状态和选择状态均留在历史之外。existing 配图通过 owner-scoped figure endpoint 加载，未保存 crop 从已鉴权题目区域图本地生成预览，注册表按历史可达 figure ID、crop fingerprint 和请求代际管理资源。成功保存以服务端 canonical response 重建会话并释放 crop URL；`409` 或其他失败不改变草稿、历史或预览。

图片区使用题目区域图自然宽度作为编辑期逻辑像素画布，`height_ratio` 给出逻辑高度；新图不自动放大、不拉伸，按自然尺寸加固定间距左上排列并换行。移动和等比例缩放先在逻辑像素空间验证越界/重叠，再写回相对图片区的归一化 placement；区域增高时重新归一化纵向坐标以保持配图像素位置和尺寸。空图片区可作为 UI 瞬时状态，但不能保存；同一 figure 在整题 revision 中只能 placement 一次，跨区段移动整个图片区保留全部稳定身份。

来源裁剪坐标与图文排版坐标继续严格分离：新 crop bbox 相对题目区域图，最终 PUT 成功时后端才组合到原始 SourceAsset 并正式高分辨率裁图；placement 相对图片区，移动布局不会重新裁图。document crop 最小面积为题目区域图的 1%，不改变 #129 Draft 检测框的独立阈值和“上传确认页禁止手工新增框”边界。四种整题预览直接消费当前未保存 draft，不读取 PaperItem；Paper/PDF schema-v2 渲染仍由后续 Issue 处理。

原因：把二进制资源放入历史会导致快照不可序列化、URL 泄漏和迟到异步响应污染当前题目；把布局编辑直接作用于归一化坐标则难以稳定表达自然尺寸、固定间距与区域增高。纯文档历史配合外置资源注册表，使原子保存、冲突保留、资源释放和几何校验可以分别测试，同时不引入数据库字段、endpoint 或运行时服务。

说明：本文件按时间倒序记录决策。较早决策中的“当前主链路”等表述保留为当时历史事实；如与顶部较新决策冲突，以较新决策和 `docs/STATUS.md` 当前 checkpoint 为准。

## 决策 45：schema-v2 文字编辑采用纯状态内核与保守段落边界（#130）

结论：独立题目编辑路由不再通过扁平 `content/answer/analysis` 投影反向重建文档，而是把 document API 返回的三区段、全部块、配图 manifest 和元数据深复制为 baseline/draft，由无 Vue 依赖的纯状态内核执行校验和不可变操作。保存始终提交完整 schema-v2 文档和 `expected_revision_no`；existing figure 只缩减为 `{id, kind: "existing"}` 声明，图片区及摆放数据原样保留。

文字块拆分和段落跨区段移动只允许使用原始 Markdown 中已验证的空行边界。扫描器在 fenced code、inline code、转义分隔符、`$…$` 和 `$$…$$` 公式内部不暴露边界；遇到未闭合或歧义分隔符时宁可把全文视为单段，不从渲染 HTML 反向生成 Markdown，也不猜测数学语义。

原因：schema-v2 的稳定 UUID、有序图片区和多图布局不能安全地经过旧扁平字段往返；把编辑规则收敛到纯模块可独立验证完整文档保存、冲突草稿保留和 Markdown/LaTeX 原文不被静默改写。保守边界牺牲少量自动拆分便利，以满足 OCR/LLM 数学语义保真不变量。

边界：本期仅编辑文字块和题目元数据；图片区展示为只读，不提供新增、删除、裁剪、缩放或布局移动。状态只保存在当前浏览器页面内，不新增跨刷新草稿持久化、后端 API、数据库迁移或依赖。

日期：2026-08-30

## 决策 44：题库采用当前投影加不可变 revision 与逻辑回收（#116）

结论：Question 保留可查询的当前投影，所有实际编辑追加连续递增的 `QuestionRevision`；无变化保存不创建 revision，并用 `expected_revision_no` 防止旧草稿覆盖新版本。删除只设置 `deleted_at`/`purge_at`，30 天到期在查询时判定；用户永久删除设置 `purged_at`，不物理删除历史 revision、PaperItem、共享 SourceAsset 或上传文件。新试卷只允许 active 题目，历史试卷始终读取冻结快照。

手工元数据保存递增 `metadata_generation` 并使自动分析任务在开始和写回前检查代际及生命周期，避免旧任务覆盖人工结果。所有题库旁路采用 owner-scoped 查询，非本人、到期和已永久删除资源统一 `404`。

原因：兼容现有 Question 投影和旧 revision 数据，同时保证编辑可追溯、并发可检测、历史试卷不受后续修改和生命周期操作影响；避免为 30 天清理引入新的调度基础设施。

边界：首期不提供 revision 浏览/比较/恢复界面，不做物理资产垃圾回收。

## 决策 43：恢复走单一脚本 + 隔离式清库，digest 显式门禁（#101）

结论：

- **单一入口**：备份恢复收敛到 `deploy/scripts/restore.sh`，生命周期固定为 checksum 校验 → 停栈 → 隔离 → 恢复 → 属主修复(10001) → SQLite quick_check → `alembic upgrade head` → 起栈 → healthz。runbook（`deploy/RESTORE_RUNBOOK.md`）只描述该脚本的输入、预期输出与回退点，不另设手工恢复路径。
- **隔离代替删除**：恢复前把现有 `math_knowledge.db`（含 `-wal`/`-shm`）与整个 `uploads/` 移动到 `<BACKUP_ROOT>/pre-restore-<UTC>` 隔离目录，活跃路径从零重建。「清库」语义由移出实现，脚本全篇无删除操作；唯一删除点是验收通过后由人执行的隔离区清理。
- **digest 显式门禁**：restore 必须显式提供两个 trusted digest，不复用 backup 的运行容器解析路径——事故时栈可能已停，且恢复是最高风险操作，artifact identity 不允许隐式来源。
- **schema 单向**：旧数据恢复后立即迁移到当前镜像 head；「migration 成功之后」的失败不支持手工移回旧 DB（schema 落后于镜像），回退方式是重跑完整 restore。

原因：

- 审计 #97 A1：全仓无 restore 路径、无演练记录，首次真实恢复可能发生在事故压力下。把正确顺序固化进脚本并让 runbook 只围绕它展开，比文字流程更能防事故时的操作变形。
- 移动而非删除同时满足「从零恢复的证明力」与「每一步可逆」，避免为演练单独设计一条带破坏性的清库分支。
- 恢复与部署共享同一 digest 合同（`image-digests.sh` 校验器复用），CI 契约测试锁定顺序与不变量。

边界：

- 覆盖 DB 与 uploads；`static/`、`models/`、`pdf_temp/`、`.env` 明确不在恢复范围（见 runbook）。
- 脚本管理停栈/起栈但不 pull 镜像；目标 release 镜像必须已在主机本地。
- 演练本身（Staging 实跑与证据留存）不在脚本 PR 内完成，按 runbook 在 #100 同窗口执行后回评本 issue。

日期：2026-08-25

## 决策 42：组卷题图快照存冻结文件名，HTML/PDF 以 data URI 内嵌（#59）

结论：

- **快照列**：`paper_items` 增加可空 `figure_image_snapshot`（裸文件名，镜像文本快照族语义）。建卷/编辑加题时按「最新 revision 的 figure_asset 路径，回退 question.figure_image」取值固化；编辑试卷的保留项不触碰该列，移除后重新加入视为新增、按当下原图重取。不做历史数据回填——历史卷建卷时本就无图，保持现状输出即符合快照语义。
- **卷内访问端点**：`GET /api/v1/papers/{paper_id}/items/{paper_item_id}/image` 服务快照冻结的文件字节（不是原题当前图形），保证历史卷不受原题后续改图影响。ownership 沿 papers 域惯例：缺失卷/跨用户卷/不属于该卷的条目/快照不可解析一律 404（与 questions 图片端点的 404+403 两段式是有意的资源族差异）。
- **渲染通道**：Gotenberg multipart 只接收单个 index.html 且禁止外联下载，data URI 是 HTML/PDF 嵌图唯一可行通道。base64 与文件路径只存在于渲染管线的内存中：render model JSON 仅含鉴权 URL 标识（`figure_image_url`），绝不出现路径或 base64。
- **CSP 放宽最小化**：`img-src` 仅当本卷实际嵌图时从 `'none'` 放宽为 `'data:'`，`.question-figure` CSS 同条件追加；无图试卷的 HTML 输出与 #59 之前逐字节一致。
- **超限策略**：单图原始字节 >4MB 或整卷累计 >24MB 时整卷渲染失败并以 413 报出题号，宁可失败也不无声丢图；mime 白名单 image/jpeg|png，非白名单静默跳过（413 语义是「过大」，对未知类型报错反而误导）。

原因：

- 快照存冻结引用字符串而非 SourceAsset 外键：与 content_snapshot「建卷时冻结、历史不变」语义直接对齐，且避开 sha256 全局去重资产的所有权纠缠（同一物理文件可被多用户的题目引用）；上传文件由 uuid 命名且当前无删除/覆写流程，冻结引用的稳定性与文本快照同级。
- 渲染器保持纯函数（schema 进、HTML 出、零磁盘依赖）：文件字节由 PDF 端点经 figure_loader 旁路传入，渲染器单测无需磁盘夹具，安全路径解析收敛在 `app/core/files.py` 一处。

边界：

- 图形编辑/替换交互不在本期；同卷同图不去重（逐题裁剪录入天然不重复）。
- CSP 只放开 `data:`，script/connect 等仍全禁；markdown/latex 管道已保证用户内容产不出 `<img`，卷面 img 是唯一受控插入点。
- 整卷接近累计上限时 Gotenberg 60s 读超时是观测项，必要时再调参数或分片。

日期：2026-08-25

## 决策 41：题图检测采用外键方案存图，DocLayout-YOLO 模型运行时下载（#58）

结论：

- **数据模型（外键方案）**：`source_assets` 表不动；`drafts` 增加可空 JSON 列 `detected_figures`（版面分析输出 `[{bbox:[x,y,w,h] 归一化, label, score}]`）；`question_revisions` 增加可空外键 `figure_asset_id -> source_assets.id`（镜像既有 `source_asset_id` 模式）；`questions` 增加可空 `figure_image`（裸文件名，镜像 `origin_image` 模式）与可空 `figure_crop_bbox`。“这行资产是不是题图”由引用方向反查判断，不在 SourceAsset 上加 role 字段。
- **模型分发（运行时下载）**：DocLayout-YOLO（rapid-layout 1.2.1 的 `doclayout_docstructbench`，imgsz1024，约 50MB .onnx）首次使用时从 ModelScope 下载到 `LAYOUT_MODEL_DIR`（dev 为 `backend/weights/`，prod 设 `/data/models` 落持久卷），SHA256 校验通过后长期复用，发版/换镜像不重下；支持 `LAYOUT_MODEL_PATH` 显式覆盖。下载失败/文件缺失不阻塞录入。
- **降级策略**：版面分析关闭、模型缺失、推理超时（默认 15s）、引擎异常一律降级为 #58 之前的行为——`detected_figures=[]`、OCR 吃原图、warning 日志，绝不阻塞录入主流程。
- **裁剪时机**：确认页用户修正后的 bbox 随 save-to-bank 提交，服务端从**原资产像素**按最终 bbox 现裁现存（SourceAsset `kind="figure"`），保证所见即所得且不回传图片字节。
- **本期边界**：一题只存一张图（多框时由用户选“主图”）；标签白名单仅认 `figure`（`LAYOUT_FIGURE_LABELS` 可调）；legacy `/recognize` 端点不做遮蔽接入。

后续修订（2026-08-30，#129）：上述“只存一张／选择主图”边界已由 schema-v2 多图基础取代。Draft 确认页默认保留全部自动检测框，只允许移动、缩放和删除，不允许新增；最终框按阅读顺序一次原子入库，并放入题干文字后的同一个图片区。初始布局以 Draft 有效图宽为画布，配图按自然像素尺寸左上排列并自动换行。Draft 路径沿用每个图片区最多 10 张的限制；零张或多张时不填充 legacy 单图字段，恰好一张时继续兼容旧字段。版面检测失败仍降级为空数组并允许纯文字保存。

原因：

- issue #58 要求 PR 前在两个候选方案中定案。role 字段方案需多一处迁移与回填语义，而本期没有任何“脱离题目列出所有题图”的查询需求，反查即可；外键方案与 `origin_image`/`source_asset_id` 既有代码同构，改动面最小，且 #59 组卷带图可直接经 revision/question 引用。
- 运行时下载使 CI 构建保持封闭、后端镜像体积不变；ModelScope 在国内服务器直连快，一次下载落 /data 卷即永久复用。烘进镜像则每次 pull 多 50MB 且构建依赖外部站点可达性。
- 零新增 API 费用约束下，RapidLayout(ONNXRuntime CPU) 自托管是既定技术选型（见 #58）；docstructbench 训练域偏学术文档，试卷场景阈值可能需 smoke 后调整，故 conf 阈值与标签白名单均留配置旋钮。

边界：

- 不做整页自动切题、一题多图、图形语义理解（几何关系识别）；`detected_figures` 仅存几何信息。
- OCR 遮蔽仅在 draft 流生效；遮蔽图临时文件写入私有 `uploads/` 并在 OCR 调用后立即删除，不经公开 `/static`。
- 超时守卫以线程池 abandon 方式实现，无法强杀进行中的 ONNX 推理；workers=1 下极端情况占用 CPU 由日志观测，必要时后续改子进程隔离。

日期：2026-08-25

## 决策 40：草稿原图走 Draft 行鉴权的专用图片端点

结论：

- 新增 `GET /api/v1/drafts/{draft_id}/image`（#22）：返回草稿引用 SourceAsset 的存储字节（`normalized_path or original_path`，经 `_resolve_upload_file_path` 防穿越解析），供识别结果编辑页在旁路常驻展示“题目原图”。
- 所有权校验挂在 **Draft 行**（`_ensure_owned_draft`），不挂 SourceAsset 行：SourceAsset 按 sha256 全局去重、仅作共享字节仓库，行内 `user_id` 不承载归属语义（与决策 37/#44 的 Question 行校验同理）。
- 前端以鉴权 blob → object URL 渲染（复用 #44 通道约定），并以本地整页预览图作为加载失败/legacy 路径的回退；不做缓存头与 ETag（沿用 #44 遗留后续项）。

原因：

- 识别修正时用户需要对照“真正送 OCR 的裁剪素材”，而非本地整页图；草稿接口与既有端点均不含图片通道，公开 `/static` 已在 #44 移除 uploads 挂载，新增通道必须继承鉴权语义。

边界：

- 不改变 Question/SourceAsset 数据模型，不新增迁移；不覆盖组卷编辑、题库详情等其他展示位（后续按需复用同一模式）。

日期：2026-08-23

## 决策 39：Issue 采用验收后手动关闭，禁止 PR 自动关闭关键词

结论：

- 正常 PR 一律用非关闭引用关联 Issue：默认 `Refs #123`，裸 `#123` 提及亦可；PR 标题与正文都禁止 `Closes/Fixes/Resolves #N`。
- `PR traceability` CI 相应改为：标题或正文出现关闭关键词即失败（防止习惯写法恢复 merge 自动关闭），无任何 Issue 引用即失败；“目标存在、是 Issue 而非 PR、至少一个 Issue 早于 PR 创建”三项既有校验保留。
- merge 不再改变 Issue 状态。merge 后由实现 agent 在 Issue 上发一条「实现报告」评论：做了什么/根因/已跑与未跑测试/**验收步骤+通过标准**/遗留风险。
- 只有用户验收后才手动关闭 Issue。允许多个 Issue 攒一批验收（同一 `main` 构建/部署上验证），但每个 Issue 独立关闭并附简短证据评论（环境、精确 SHA、观察结果）；验收不通过则评论记录现象并保持打开或重开。
- 追溯链由 `Issue -> Branch -> Commit -> PR -> Merge` 扩展为 `Issue -> Branch -> Commit -> PR -> Merge -> Acceptance -> Close`。

原因：

- 关闭关键词使 Issue 在 merge 时自动关闭，验收、文档记账与工作区回收全部发生在“已关闭”之后且无跟踪点：#44/#45/#46/#47 以零评论自动关闭、#50/#51/#52 三次合并未记账、5 个已完结任务 worktree 残留。用户实际节奏是敏捷开发、常攒数个 PR 一起验收，“closed 必须等于验收通过”。

边界：

- 不改变 Issue-first 原则与追溯链前四层；不追溯修改历史已关闭 Issue 的状态，仅按 #55 补审计评论。
- 本决策显式取代决策 35 中“使用 closing keyword 合并后自动关闭”的约定；决策 35 的 Issue-first 与 CI 追溯校验部分继续有效。

日期：2026-08-23

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
