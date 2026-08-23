# STATUS

## 2026-08-23 题目图片访问改为鉴权通道(#44)

- 新增 `GET /api/v1/questions/{id}/image`:未认证 401、非 owner 403、owner 经 `FileResponse` 流式取回原图;所有权校验挂在 Question 层,`SourceAsset` 按 sha256 全局去重仅作共享字节仓库(不同用户可通过各自题目引用同一份文件)。
- `UPLOAD_DIR` 默认移出公开 `/static` 挂载(本地 `backend/uploads`,生产 `/data/uploads`),启动时 fail-closed 校验 uploads 不落在 `STATIC_DIR` 内;`deploy.sh` 自动把旧 `${DATA_ROOT}/static/uploads` 一次性迁移到 `${DATA_ROOT}/uploads`(两目录并存时拒绝并要求人工合并),`backup.sh` 兼容新旧布局。
- API 的 `image_url` 字段改指鉴权端点;前端 HistoryPanel / BankPanel 经全局 axios(带 Authorization、复用 401 refresh 重试)预取 Blob 后以 object URL 渲染,卸载时释放;Dashboard 预览本就走本地 File objectURL,不受影响。浏览器自动缓存的 ETag/Cache-Control 补偿列为后续可选项。
- 本地验证:`python -m compileall app` 通过;`python -m pytest -q` 169 passed + 7 subtests(含新增 10 个图片访问回归);`npm run test:stage3-contract` 与 `npm run build` 通过。真实 Linux/Docker/HTTPS 环境验证与 uploads 文件迁移演练待 Staging 执行。

## 2026-08-18 digest-pinned Staging 与 HTTPS production-mode Demo 验收完成

- 首次真实 first-party digest-pinned Staging rollout 已通过：部署 Git SHA `45b604bbde646e0f41b219c1fbaad6d506525fe1`，backend/web trusted digest 分别为 `sha256:a9fc71f85461a8360d44e8b76bbb8798a703d828fa041fa81e829ba31dcf9018` 与 `sha256:3c69c38858ee402b45d7e557ebde292c466b3d758238fa80fc881a2ddbf47af6`；`repository@sha256` runtime、exact RepoDigest、OCI revision、备份、Alembic、SQLite `quick_check`、uploads、HTTP、PDF.js `.mjs` MIME、backend 到 Gotenberg 的真实 PDF smoke 和服务健康均已验证，结论为 `DIGEST-PINNED STAGING DEPLOYMENT PASS`。
- `math.wwlabcode.top` 已使用 Host Caddy `2.11.4` 和 Let's Encrypt 托管证书提供 HTTPS：公网 IPv4 仅开放 `22/80/443`，Caddy 在 `80` 重定向 HTTPS、在 `443` 终止 TLS 并代理到 `127.0.0.1:8000`；`backend:8000` 与 `gotenberg:3000` 仅在 Docker 内部，宿主机 `8000/8080/3000` 不对公网开放，也没有公网 IPv6 `80/443` listener。
- 已验收的 production-mode Demo 精确运行 Git SHA `feca1a7c540666b5b520121a8ca8c8b2eb4467c6`；backend/web trusted publisher digest 分别为 `sha256:6b05dfdb355a146f31ac1cb1df4b7344da795fd31f7bf341c26a82219e60f268` 与 `sha256:be2556c4f2c9898b3a8a4fb228b1f2299a527360e051dcc27b4434257365413b`。运行环境启用 `APP_ENV=production`、严格认证安全、`trusted_proxy_tls`、Secure refresh cookie、精确 HTTPS CORS origin，并关闭公开注册；密钥未写入或输出到验收记录。
- 自动验收覆盖 exact digest/revision/RepoDigest 门禁、备份、migration current/head、SQLite、uploads、服务健康、HTTP 到 HTTPS、可信证书、页面/health/static/MIME、CORS、forwarded-header 防伪、refresh cookie、注册开关、真实 PDF 与公网端口边界，结论为 `HTTPS PRODUCTION-MODE DEMO ROLLOUT PASS`。用户已完成人工浏览器 Demo 验收并确认通过。
- 验收时 Demo 运行 `feca1a7...`；其后 `main` 才推进到子提交 `6795ede0dcd366ba5d15cc0bcc148ef25a99ab27`。这是显式选择 release 的预期状态而非部署竞态；Demo 不自动跟随每个 main commit，不能据此宣称 `6795ede...` 的 #29/#33 已部署。

## 2026-08-18 完整试卷草稿编辑

- 组卷中心支持草稿试卷标题、描述、分值、题序、题干、答案和解析编辑，并支持删除题目及从当前用户题库继续添加题目；前端修改保存在本地草稿中，单次保存或取消。
- 新增原子 `PATCH /api/v1/papers/{paper_id}`：只允许 owner 编辑 `draft`，以后端提交数组顺序生成连续 `position`，通过临时 position 两阶段更新规避唯一约束交换冲突，并在保存后显式更新 Paper 时间戳。
- 已有题目的文本修改只写入当前 PaperItem snapshot；新增题目的基础 snapshot、题型、难度、知识点及 revision id 由服务端读取最新 Question / QuestionRevision，Question 与 QuestionRevision 不会被试卷编辑修改。
- Paper detail/list、PaperRenderModel 与服务端 PDF 继续读取保存后的 Paper/PaperItem 数据；学生版 render/PDF 仍不暴露答案和解析。现有表结构足够，本次不新增 Alembic migration。

## 2026-08-17 组卷答题区改为 50mm 纯留白

- `answer_area_mode=after_each_question` 的 render model 使用 `height_mm: 50` 明确表达固定高度，不再输出横线行数；`none` 继续表示无答题区，API 枚举保持兼容。
- 组卷界面默认选择“每题后留白”，前端预览按模型使用 CSS `mm` 单位渲染，PDF HTML 同步输出 50mm 白底空白且不包含横线或占位文字。
- PDF 分页只约束题干末尾块与答题区尾部，普通短题尽量避免题干和留白分离；不对整道题强制 `break-inside: avoid`，长题内容仍可跨页。

## 2026-08-17 裁剪识别图像质量修复

- 前端裁剪链路不再依赖 `vue-cropper 1.1.4` 的默认 `maxImgSize=2000`；现在按源图真实像素显式计算上限，最长边不超过 8192px、总像素不超过 3600 万，常见 4961×7016 的 600 DPI A4 扫描保持原始像素。
- 裁剪首先生成 PNG；16 MiB 以内直接上传，超出后依次尝试保持像素尺寸的 JPEG quality 0.95、0.90、0.85，仍超限才进行一次 0.75–0.90 比例的有限降采样，最后仍超过 16 MiB 则阻止上传并要求缩小裁剪范围。该 soft limit 为 Nginx 和后端共同的 20 MiB 上限保留 multipart/代理余量；上传文件的 MIME 与扩展名保持一致。PDF 页面仍按既有 2.5 倍 Canvas 和 JPEG 中间图生成。
- 本地无头浏览器对同一 4961×7016 JPEG、396×560 CSS 裁剪框的实测：旧配置内部输入 1414×2000、输出 1131×1600 JPEG；新配置内部输入 4961×7016、输出 3969×5613 PNG。CSS 裁剪框尺寸不是上传 Blob 的像素尺寸。
- 新增尺寸上限、PNG MIME/文件名和 Dashboard cropper 配置回归测试，并纳入 Stage 3 前端合同；真实 Issue #20 样本的整页/裁剪 OCR 人工对比仍需在 Draft PR 验收。
- 本地真实 Canvas/Blob 合成验证：3969×5613 白底文字图的 PNG 为 1,617,150 bytes，保持 PNG 原尺寸；4096×4096 高熵彩色噪声 PNG 为 57,717,592 bytes，自动选择保持原尺寸的 JPEG quality 0.90，最终为 13,825,093 bytes。普通图片 Blob URL 会在替换、重置、解码失败和组件卸载时释放。
- 第一轮真实 UI 验收发现第二层问题：固定高度的横向裁剪 viewport 配合 `mode=contain` 会把竖版 A4 完整缩入容器，导致默认显示宽度过小。当前 PR 改为可读优先的默认 `cover` 视图，保留图片/裁剪框平移、滚轮缩放，并增加明确的 +/- 控件和真实输出像素尺寸标签；高清 source bitmap、`full=true` Blob 输出与 adaptive encoding 策略不变。第二轮真实 Issue #20 人工 UI 验收仍待完成。

## 2026-08-17 first-party release image digest-pinned deployment contract

- 当前 implementation PR 将 production Compose 和部署脚本从 backend/web 完整 Git SHA tag 升级为 trusted `repository@sha256:...` 输入；digest 缺失、格式非法、OCI revision 不等于 checkout SHA 或 RepoDigest 不精确匹配都会在 backup、Alembic migration 和 rollout 前 fail closed。
- Git SHA 继续作为 source identity，main publisher 的 SHA tag 继续用于 release discovery / traceability；successful main `Publish release images` 记录的 backend/web digest 是服务器部署的 immutable artifact identity，部署脚本不通过 tag 自行解析 digest，也没有 build fallback。
- `Production stack checks` 保持原 required job name，并为 Compose/部署合同使用固定合法 digest fixture；正式 Dockerfile build、OCI revision 和 Nginx `.mjs` MIME validation 继续保留，PR CI 不 pull 虚构的 GHCR digest。
- 在该 implementation PR 合并前，它只实现 first-party backend/web 合同和 CI 验证；当时服务器基线仍是下节记录的 SHA-tag rollout，后续 rollout 必须等待 main publisher 产出并显式提供两个 trusted digest。
- 后续真实 digest-pinned Staging 与 HTTPS production-mode Demo rollout 已于 2026-08-18 完成，见本文件顶部验收记录。该合同本身仍不包含第三方 Gotenberg digest pinning、签名/SLSA、自动部署或 GHCR credential 生命周期管理。

## 2026-08-16 production-like deployment 使用 GHCR release images

- `main` publish workflow 按完整 Git SHA 构建并发布 backend/web release images；production Compose 使用同一 SHA tag 从 GHCR 拉取，不再在部署服务器构建 application images。
- 部署脚本在 backup、Alembic migration 和启动前完成 pull、OCI revision 匹配及 RepoDigest 记录；pull 失败不会 fallback build。
- `Production stack checks` 保留原 job 名，独立执行 Compose 合同验证、backend/web Dockerfile 构建和 OCI revision 验证；PR CI 不尝试拉取不存在的 PR HEAD release image。
- 首次完整 Staging GHCR pull-only deployment 已在 [SERVER] 通过：部署 `main` SHA `b78fbd43deadda495771d0fe221d76d81e9486b2`，backend RepoDigest 为 `sha256:c4e78f2a6ce0f5c2b4d532be81c92d795522f1d446f6d88ce2daa8f354f5d524`，web RepoDigest 为 `sha256:f039b40b67c5b0f0ab319fd39c6649dcec4961c42f9b4c335d56b50434574993`。
- 本次闭环已覆盖 `main SHA -> GHCR SHA-tagged images -> exact digest verification -> server pull -> revision/digest gate -> backup -> Alembic migration -> Compose rollout -> HTTP/Nginx health -> backend 到内部 Gotenberg 的真实 PDF smoke`；数据库 `current == head == 20260604_0005`，服务健康且 restart count 均为 0，数据库 quick check 与 uploads 完整性通过。
- 该次是当时的 SHA-tag Staging infrastructure deployment 验证，本身不代表 Demo/production deployment 或 production ready；后续 digest-pinned Staging 与 HTTPS Demo 验收见顶部 2026-08-18 记录。GHCR credential 生命周期仍由管理员管理；authenticated business-level `/papers/{id}/pdf` 在这一次历史 rollout 中未重新执行。

## 2026-08-06 KaTeX 块公式解析限制加固

- 已修复块公式在同行或最后一行闭合时未计入闭合符前内容、从而绕过 `MAX_BLOCK_MATH_LENGTH` 的问题；所有片段及片段间换行现在都会在 KaTeX 调用前计数。
- 块结束符查找改为从行尾跳过有限空白后只检查唯一可能的 `$$`，不再为每个伪候选重复 `slice().trim()`；扫描保持有界线性复杂度。
- 新增同行超长、最后一行超长、大量伪结束符 2 秒硬超时、201 行上限和正常块公式回归；超长且有合法闭合符的块会作为 HTML 转义的普通文本输出，不再进入 inline KaTeX 解析。

## 2026-08-06 KaTeX 不可信公式渲染迁移

前端已停用会把不可信 TeX URL、style、class 和 id 输出到 HTML 的 `markdown-it-mathjax3` / `mathxyjax3` 链路，改用项目既有的 `katex 0.16.27`，不新增数学渲染依赖，不改变 OCR、LLM 或后端业务。

- MarkdownIt 本地 inline/block 规则支持 `$...$`、`$$...$$`，并继续把 `\(...\)`、`\[...\]` 归一化后交给同一 renderer；转义美元、code span、fenced code 和未闭合分隔符保持普通文本。
- KaTeX 明确使用 `throwOnError: false`、`trust: false`、`strict: 'warn'`、`maxSize: 10`、`maxExpand: 1000`、`globalGroup: false`、`output: 'htmlAndMathml'`；不传入共享 `macros`，不动态加载 package。
- 安全合同覆盖危险 TeX URL、`includegraphics`、HTML class/id/style/data 扩展、动态 `require`、500em 尺寸和递归宏；危险属性未生成，递归宏在有 2 秒硬超时的子进程中安全结束。
- 常规上下标、分数、根号、`aligned`、`cases`、`pmatrix` 和中文 `\text{}` 已通过回归；仓库未发现 mhchem、Xy-pic、bussproofs 等核心业务依赖。当前不宣称支持任意完整 LaTeX，动态 `\require` 和 KaTeX 未实现扩展不受支持。
- 生产入口只加载一次本地 KaTeX CSS；Vite 构建产物包含 1 个合并 CSS 和 59 个 KaTeX 字体文件，不依赖 CDN，未发现 MathJax runtime 或 `mathxyjax3`。
- 实时 `npm audit` 在迁移前后均为 25 项（15 moderate、10 high、0 critical），没有由本次迁移新增 high/critical，KaTeX 不在公告链中；Vite、Sass、MarkdownIt 传递链等剩余风险需后续独立处理。

## 2026-08-06 前端运行时安全加固

当前前端已收紧所有共用 Markdown 渲染入口，并将直接生产依赖 Axios 在现有 major 内升级；不改变 OCR、LLM、Draft、题库、组卷流程，也不升级 Vite、Sass 或其他构建工具链。

- 不可信 Markdown 的原始 HTML 已禁用，`<script>`、事件处理属性和 SVG 载荷只会作为转义文本显示；自动裸链接转换已关闭。
- MarkdownIt 默认危险协议检查继续生效，并额外拒绝全部 `data:` URL；显式 HTTPS 链接、标题、列表、加粗、换行及数学公式仍正常渲染。该 checkpoint 当时使用 MathJax，现已由上方 KaTeX 迁移替代。
- 新增共享生产 renderer 工厂和真实安全合同测试，覆盖原始 HTML、`javascript:`、`vbscript:`、`file:`、`data:`、裸 URL、安全 HTTPS 链接及数学公式，并纳入 `test:stage3-contract`。
- Axios 从 `1.13.2` 升级到 npm 当前 stable `1.19.0`；`follow-redirects` 从 `1.15.11` 升至 `1.16.0`，`form-data` 从 `4.0.5` 升至 `4.0.6`。
- 本轮现场 `npm audit` 从 12 项（2 moderate、10 high）降至 9 项（1 moderate、8 high），Axios、`follow-redirects` 和 `form-data` 相关公告已消失；未运行 `npm audit fix`。
- 剩余公告涉及 Markdown 运行时依赖和 Vite、Rollup、PostCSS 等构建链，留待后续独立 PR；当前不宣称 npm 漏洞已清零。
- 干净 `npm ci --ignore-scripts`、生命周期脚本清单、5 组前端合同测试、Markdown 安全测试、Node 语法检查和生产构建均通过；仍保留既有 Vite chunk size warning。

## 2026-08-06 npm 供应链安全加固

当前前端安装、CI 与生产镜像构建已默认禁止 npm 生命周期脚本，不升级业务依赖、不改变 OCR、LLM、Draft、题库、组卷或前端功能。

- Docker 与 CI 使用 `npm ci --ignore-scripts`；干净安装、Stage 3 合同测试和生产构建通过。
- 当前依赖树中 `@parcel/watcher 2.5.1`、`esbuild 0.27.2`、`vue-demi 0.14.10` 声明安装生命周期脚本；跳过这些脚本后现有验证仍通过，无需增加例外。
- GitHub Actions checkout 不再持久化仓库凭据；全部第三方 Actions 已固定到官方版本标签对应的完整 SHA。
- pull request 新增 Dependency Review 检查；CI 会输出只读生命周期脚本依赖清单。
- 2026-08-06 重新查询 npm audit 得到 28 项（16 moderate、12 high）；直接 production 依赖 `axios 1.13.2` 存在同一 major 的修复版本，依赖升级需单独评估，本轮不自动升级。
- 当前 Windows 环境没有 Docker，且 WSL Bash 服务已禁用，因此 Compose config 与 Shell 语法检查仍需由 GitHub Actions 验证。

## 2026-08-05 v0.1 单机部署候选栈

当前 `v0.1 Release Candidate` 已增加可重复的单机容器部署能力，不改变 OCR、LLM、Draft、题库或组卷业务逻辑。

- Nginx Web 容器提供 Vue dist，并反向代理 `/api/`、`/static/`、`/healthz`；FastAPI 的 `8000` 不映射到宿主机。
- FastAPI 使用 Python 3.11 slim、非 root 用户和单 Uvicorn worker；SQLite、上传文件与 PDF 临时目录统一持久化到宿主机 `/srv/math-knowledge/data/`。
- 部署脚本在启动前显式执行 Alembic migration，不允许应用启动时自动修改 schema。
- 备份脚本通过 SQLite Backup API 生成一致快照，同时保存上传文件、部署 commit 和不含值的环境字段清单。
- 前端开发默认地址仍为 `http://127.0.0.1:8000`；生产默认改为同源 `/api/v1` 与 `/static`，仍支持 `VITE_API_BASE_URL` 覆盖。
- 本地后端 125 项 pytest、125 项 unittest、前端 Stage 3 契约和生产构建通过；生产 dist 不包含 localhost API 地址。
- 当前 Windows 环境没有 Docker 命令，Compose 解析和 Linux 镜像构建由 GitHub Actions 验证；既有 [SERVER] 容器栈与 GHCR pull smoke 已完成，本次 pull-only 部署改动仍需以 Draft PR 的 `Production stack checks` 作为合并前验证。

## 2026-08-05 v0.1 MVP 交付收尾

当前项目状态已收口为 `v0.1 Release Candidate`。本轮目标是建立可重复的自动门禁与人工发布验收标准，完成后停止无边界开发，只根据真实客户需求迭代。

生产路线冻结：

- 主流程固定为“上传 → 百度 OCR → LLM 清洗 → Draft 确认 → 保存题库 → 组卷 → Paper Preview”。
- 生产默认固定为 `OCR_PROVIDER=baidu`，LLM 使用 DeepSeek 或兼容 OpenAI API 的服务。
- RapidOCR 只保留为历史实验代码，不属于 v0.1 交付范围；除非客户需求或成本数据要求重新评估，否则不再继续迁移或比较 RapidOCR、PaddleOCR、Pix2Text。
- 不修改 Draft 主流程，不新增题库删除/回收站、Draft 历史恢复、私有/共享/群组题库、服务端 PDF/DOCX 导出，不做大范围 UI 重构或无关依赖升级。

本轮交付内容：

- 新增 `.github/workflows/ci.yml`，在 main push、面向 main 的 PR 和手工触发时分别运行后端与前端 job。
- 后端 CI 使用 Python 3.11，安装正式依赖与 pytest，执行 `python -m compileall app` 和 `python -m pytest`；测试环境密钥为空或明确为 CI 占位值，不调用真实外部 API。
- 前端 CI 使用 Node.js 22 LTS、合法 lockfile 和 `npm ci`，执行 `npm run test:stage3-contract` 与 `npm run build`。
- 新增 `docs/MVP_RELEASE_CHECKLIST.md`，覆盖环境、启动、自动检查、至少 5 题真实 smoke、失败路径、保护机制、数据隔离、组卷快照、打印与发布签字。
- README 已改为 v0.1 RC 交付口径，并明确真实 smoke 完成前不能视为正式发布。

修改前基线（2026-08-05 实跑）：

- 后端解释器：`D:\math_knowledge_system\backend\venv\Scripts\python.exe`，Python 3.11.7。
- `python -m compileall app` 通过。
- `python -m pytest` 通过，`125 passed`，有 1 个 `.pytest_cache` 权限 warning。
- `python -m unittest discover tests` 通过，`Ran 125 tests OK`。
- `npm run test:stage3-contract` 通过，3 个契约脚本全部通过。
- `npm run build` 通过，仍有 Vite chunk size warning。

修改后验证（2026-08-05 实跑，百度/DeepSeek Key 显式为空）：

- `python -m compileall app` 通过。
- `python -m pytest` 通过，`125 passed`，有 1 个 `.pytest_cache` 权限 warning。
- `python -m unittest discover tests` 通过，`Ran 125 tests OK`。
- `npm run test:stage3-contract` 通过，3 个契约脚本全部通过。
- `npm run build` 通过，1601 个模块完成转换，仍有 Vite chunk size warning。
- 测试日志明确显示百度 OCR 与 DeepSeek 凭据未配置，全部自动测试仍通过，证明本轮自动门禁不依赖真实第三方调用。

发布门禁：

- 自动检查通过后仍需发布负责人按 `docs/MVP_RELEASE_CHECKLIST.md` 人工执行至少 5 张真实数学题图片的百度 OCR + LLM smoke。
- OCR/LLM 失败、风险提示与二次确认、重复保存保护、用户数据隔离、组卷快照、Paper Preview 浏览器打印/另存 PDF 均需人工确认。
- 人工 smoke 未完成前不创建 `v0.1.0` 标签，不把当前状态表述为正式发布或生产可用。

## 2026-06-17 第二十八点七轮 RapidOCR 3.8.4 返回结构适配

当前 MVP smoke 阶段已修复 `RapidOcrProvider` 对 RapidOCR 3.8.4 返回对象的解析兼容问题，`unsupported result format` 不再误伤当前版本。

本轮结果：

- 项目 venv 使用 `D:\math_knowledge_system\backend\venv\Scripts\python.exe`。
- 项目 venv 中 `rapidocr` 已升级到 `3.8.4`，`onnxruntime 1.27.0` 已安装。
- 探测确认 RapidOCR 3.8.4 返回 `rapidocr.utils.output.RapidOCROutput`。
- 关键字段为 `txts`、`boxes`、`scores`，其中 `txts` 是 tuple，`boxes` 是 numpy ndarray，并提供 `to_json()`。
- 解析器已优先支持 `txts/texts`，避免对 numpy/array-like `boxes` 做布尔判断，并增加 `to_dict()` / `model_dump()` / `to_json()` 兜底解析。
- 空 `txts` 视为合法空文本，不再误报 unsupported；真正 unsupported 时错误信息包含类型、属性摘要和截断 repr。
- 新增 `backend/scripts/__init__.py` 与 `backend/scripts/evaluation/__init__.py`，避免第三方 `scripts` 包遮蔽项目脚本导致 pytest 收集失败。
- RapidOCR-only smoke 对 3 张图片均成功返回文本。
- 完整 baidu vs rapidocr A/B 已重跑，双方均 3 张成功。

Smoke 摘要：

- RapidOCR-only：3/3 成功，耗时约 2029-2811 ms，文本长度分别为 43、87、95；第二张触发 `choice_options_incomplete`。
- 完整 A/B 中 Baidu：3/3 成功，耗时约 930-1430 ms，文本长度分别为 74、326、291；3 张均触发 `choice_options_incomplete`。
- 完整 A/B 中 RapidOCR：3/3 成功，耗时约 2134-2824 ms，文本长度分别为 43、87、95；第二张触发 `choice_options_incomplete`。

OCR 当前状态：

- RapidOCR 已完成 Provider 接入和真实 smoke，但当前数学题图识别完整性明显弱于百度 OCR。
- 当前默认 OCR 继续使用 Baidu。

当前边界：

- RapidOCR 已能完成本地 OCR smoke，但质量仍需人工判断。
- RapidOCR 文本长度明显短于 Baidu，可能存在漏题、漏选项或版面识别不足。
- 本轮不修改默认 `OCR_PROVIDER`，默认仍为 `baidu`。
- 本轮不修改 Draft recognize API、不修改前端、不修改数据库模型、不修改 BaiduOcrProvider、不修改 legacy `/api/v1/recognize`。
- 本地完整报告和 JSON 位于 `backend/reports/ocr_ab/`，该目录已被 `.gitignore` 忽略，不作为提交内容。

验证结果：

- `cd backend && python -m pytest tests/test_ocr_provider.py` 通过，`15 passed`，仍有 `.pytest_cache` 权限 warning。
- `cd backend && python -m pytest tests/test_ocr_ab_evaluation.py` 通过，`5 passed`，仍有 `.pytest_cache` 权限 warning。
- `cd backend && python -m pytest` 通过，`125 passed`，仍有 `.pytest_cache` 权限 warning。
- `cd backend && python -m compileall app` 通过。
- `cd backend && python -m unittest discover tests` 通过，`Ran 125 tests OK`。
- `cd backend && python scripts/evaluation/compare_ocr_providers.py --input "D:\math_knowledge_system\data\manual_smoke\ocr_images" --providers rapidocr --output reports/ocr_ab/rapidocr_smoke_after_parser_fix.md --json-output reports/ocr_ab/rapidocr_smoke_after_parser_fix.json` 通过。
- `cd backend && python scripts/evaluation/compare_ocr_providers.py --input "D:\math_knowledge_system\data\manual_smoke\ocr_images" --providers baidu,rapidocr --output reports/ocr_ab/ocr_ab_first_smoke_parser_fixed.md --json-output reports/ocr_ab/ocr_ab_first_smoke_parser_fixed.json` 通过。

## 2026-06-17 第二十八点五轮 OCR A/B first smoke 实跑

当前 MVP smoke 阶段已使用本地 3 张 smoke 图片运行 OCR Provider A/B 评测，输入目录明确为 `D:\math_knowledge_system\data\manual_smoke\ocr_images`。

本轮结果：

- 评测命令从 `backend/` 目录运行，providers 为 `baidu,rapidocr`。
- 本轮未带 `--with-llm`，未调用 LLM。
- Baidu OCR 对 3 张图片均成功返回文本。
- 3 张图片均触发 `choice_options_incomplete` 风险提示。
- RapidOCR 包已安装，但运行依赖 `onnxruntime` 缺失，3 张图片均失败并记录 `onnxruntime is not installed.`。
- 本地完整报告和 JSON 已生成在 `backend/reports/ocr_ab/`，该目录已被 `.gitignore` 忽略，不作为提交内容。
- 新增 `docs/OCR_AB_FIRST_SMOKE.md` 作为提交用摘要，不粘贴完整 OCR 原文。

当前边界：

- 本轮不能形成 RapidOCR 识别质量结论，只确认失败原因和脚本容错行为。
- 本轮不修改默认 `OCR_PROVIDER`，默认仍为 `baidu`。
- 本轮不修改 Draft recognize API、不修改前端、不修改数据库模型、不修改 legacy `/api/v1/recognize`。

验证结果：

- `cd backend && python scripts/evaluation/compare_ocr_providers.py --input "D:\math_knowledge_system\data\manual_smoke\ocr_images" --providers baidu,rapidocr --output reports/ocr_ab/ocr_ab_first_smoke.md --json-output reports/ocr_ab/ocr_ab_first_smoke.json` 通过。
- `cd backend && python -m pip show rapidocr` 显示已安装 `rapidocr 3.8.4`。
- `cd backend && python -m pip show onnxruntime` 显示未安装。

## 2026-06-17 第二十八轮 OCR Provider A/B smoke 评测机制

当前 MVP smoke 阶段新增 OCR Provider A/B 手工评测入口，用于对比 `baidu` 和 `rapidocr` 在同一批题图上的 OCR 文本、耗时、失败信息和识别质量风险。

新增能力：

- 新增 `backend/scripts/evaluation/compare_ocr_providers.py`，支持单图或目录输入。
- `--providers` 默认 `baidu,rapidocr`，也支持只跑单个 provider。
- `--output` 输出 Markdown 报告，`--json-output` 可额外输出结构化 JSON。
- 默认只跑 OCR 和 `quality_warnings`；只有显式 `--with-llm` 才调用现有 LLM 清洗服务。
- 单个 provider、单张图片或 LLM 调用失败只记录失败信息，不中断整批评测。
- `OCRService.recognize()` 增加可选 `provider_name` 单次覆盖参数，默认仍读取 `OCR_PROVIDER`，默认 provider 仍是 `baidu`。
- `backend/reports/ocr_ab/` 已加入 `.gitignore`，真实评测报告默认不入库。

当前边界：

- 本轮不修改默认 `OCR_PROVIDER`，不把 RapidOCR 设为默认。
- 本轮不修改 Draft recognize API、不修改前端、不修改数据库模型。
- 本轮不优化 OCR 精度，不重构 Draft 流程，不强制安装 RapidOCR。
- 自动化测试使用 fake OCR/LLM，不调用真实百度 OCR、RapidOCR 模型、DeepSeek API、网络或 API key。

验证结果：

- `cd backend && python -m unittest tests.test_ocr_provider.OcrProviderTests.test_ocr_service_can_override_provider_per_recognize_call` 先按预期失败，实现后通过。
- `cd backend && python -m unittest tests.test_ocr_ab_evaluation` 先按预期失败，实现后通过，`Ran 5 tests OK`。
- `cd backend && python -m compileall app` 通过。
- `cd backend && python -m py_compile scripts/evaluation/compare_ocr_providers.py` 通过。
- `cd backend && python -m unittest tests.test_ocr_provider tests.test_ocr_ab_evaluation` 通过，`Ran 18 tests OK`。
- `cd backend && python -m unittest discover tests` 首次 120 秒超时未取得最终结论；提高超时后通过，`Ran 123 tests OK`。

## 2026-06-16 第二十七点五轮 pytest 根目录遗留测试收口

当前 MVP smoke 阶段已清理 pytest 根目录遗留收集问题，后端全量 pytest 可直接运行。

新增/调整：

- 将根目录历史手工脚本 `backend/test_deepseek.py` 移出 pytest 自动收集范围。
- 新位置为 `backend/scripts/manual/deepseek_manual_check.py`，并标注为手工 DeepSeek 检查脚本，不属于自动测试套件。
- 手工脚本改用当前 `app.services.llm.nlp_service.analyze()` 接口，不恢复已废弃的 `correct_text`。
- 自动化测试仍集中在 `backend/tests/`，不引入真实 DeepSeek API 调用到测试。

验证结果：

- `cd backend && python -m compileall app` 通过。
- `cd backend && python -m unittest discover tests` 通过，`Ran 117 tests OK`。
- `cd backend && python -m pytest tests` 通过，`117 passed`，仍有 `.pytest_cache` 权限 warning。
- `cd backend && python -m pytest` 通过，`117 passed`，仍有 `.pytest_cache` 权限 warning。
- `cd backend && python -m py_compile scripts/manual/deepseek_manual_check.py` 通过。

## 2026-06-16 第二十七轮 RapidOCR 本地 OCR Provider 实验接入

当前 MVP smoke 阶段新增 RapidOCR 本地 OCR Provider 实验接入，用于验证 Draft OCR Provider 可配置切换能力。

新增能力：

- `OCR_PROVIDER` 支持 `baidu` 和 `rapidocr`，默认仍为 `baidu`。
- 新增 `RapidOcrProvider`，通过延迟导入 `rapidocr.RapidOCR` 避免未安装 rapidocr 时影响默认 baidu 流程。
- RapidOCR 引擎在 provider 内懒加载并缓存，`OCRService` 也按 provider 名称缓存实例，避免每次识别重复初始化。
- RapidOCR 返回结果增加最小兼容解析，覆盖对象 `txts/texts`、`boxes/scores`、旧式 `(boxes, txts, scores)` 和逐行 tuple/dict 结构。
- `backend/.env.example` 增加 `OCR_PROVIDER=baidu` 与 `# OCR_PROVIDER=rapidocr` 示例；`requirements.txt` 仅注释 RapidOCR 为可选依赖。

当前边界：

- 百度 OCR 仍是稳定默认 provider，本轮不替换百度 OCR。
- 本轮不修改 Draft recognize API 请求/响应结构、不改前端、不改数据库模型。
- RapidOCR 当前只是本地文本 OCR 实验 provider，真实高中数学题、公式和双栏选项效果需要后续用 smoke 图片实测对比。

验证结果：

- `cd backend && python -m unittest tests.test_ocr_provider` 通过，`Ran 12 tests OK`。
- `cd backend && python -m compileall app` 通过。
- `cd backend && python -m unittest discover tests` 通过，`Ran 117 tests OK`。
- `cd backend && python -m pytest tests` 通过，`117 passed`，仍有 `.pytest_cache` 权限 warning。
- `cd backend && python -m pytest` 在第二十七点五轮已收口通过。

## 2026-06-16 第二十六轮识别结果风险提示与保存前校验

当前 MVP smoke 阶段新增识别质量风险提示，用于避免疑似残缺题无感保存入题库。

新增能力：

- Draft detail / recognize / save-to-bank 响应新增 `quality_warnings`，按当前识别文本、原始 OCR 文本和 LLM 清洗文本动态计算，不新增数据库字段。
- 新增选择题风险提示：疑似选择题选项不足 4 个时返回 `choice_options_incomplete`。
- 新增选择题标签断档提示：如 A/C 缺 B 或 A/B/D 缺 C 时返回 `choice_options_sequence_gap`。
- 新增保守文本质量提示：识别文本过短返回 `recognized_text_too_short`，LLM 清洗后明显短于 OCR 原文返回 `ocr_llm_text_changed_substantially`。
- Dashboard 结果区展示“识别风险提示”，用户仍可编辑草稿。
- Dashboard 保存入题库前如果存在 `quality_warnings`，弹出确认框；用户可取消返回编辑，也可确认继续保存。

当前边界：

- 本轮不解决 OCR 双栏选项漏识别本身，只提示风险。
- 本轮不接入 RapidOCR、PaddleOCR、Pix2Text，不改 OCRService provider、BaiduOcrProvider 或 LLM prompt。
- 本轮不阻止后端 save-to-bank，不改变 API 兼容性，不做数据库迁移。
- 本轮不修改 legacy `/api/v1/recognize`、PaperRenderModel 或 PaperPreview 打印逻辑。

验证结果：

- `cd backend && python -m compileall app` 通过。
- `cd backend && python -m unittest tests.test_recognition_quality` 通过，`Ran 6 tests OK`。
- `cd backend && python -m unittest tests.test_draft_pipeline` 通过，`Ran 17 tests OK`。
- `cd backend && python -m unittest discover tests` 通过，`Ran 109 tests OK`。
- `cd frontend && npm run test:stage3-contract` 通过。
- `cd frontend && npm run build` 通过，仍有 Vite chunk size warning。

## 2026-06-16 第二十五轮重复素材上传支持 smoke 复用

当前 MVP smoke 阶段已修复同一用户重复上传同一张本地 smoke 图片时被 `Asset already exists` 卡死的问题。

新增能力：

- `POST /api/v1/assets` 首次上传仍正常创建 `SourceAsset`。
- 同一用户重复上传相同图片时，后端不重复保存文件，不再作为阻塞性失败返回，而是复用已有 asset。
- 重复上传响应包含 `deduplicated=true`、`existing_asset_id` 和提示信息，前端可继续用该 asset 创建 Draft。
- Dashboard 收到复用响应时显示“素材已存在，已复用已有素材继续录入。”，并继续后续 Draft 创建和识别流程。
- 当前 `Draft.source_asset_id` 没有唯一约束，同一张 smoke 图片可以多次创建 Draft，用于反复测试 OCR/LLM 效果。

当前边界：

- 本轮保留 asset 去重，不重复保存同一份图片文件。
- 本轮不做历史记录重构，不支持历史记录重新编辑旧素材。
- 本轮不做题库删除功能。
- 本轮不修改 OCR provider、BaiduOcrProvider、LLM prompt、legacy `/api/v1/recognize`、PaperRenderModel 或 PaperPreview 打印逻辑。
- `SourceAsset.sha256` 当前仍是全局唯一；如果未来需要严格支持不同用户上传相同文件并各自拥有独立 asset，需要单独设计 asset user isolation 和迁移。

验证结果：

- `cd backend && python -m unittest tests.test_draft_pipeline.DraftPipelineTests.test_repeated_asset_upload_reuses_existing_asset_and_allows_new_draft` 先按预期失败，实现后通过。
- `cd frontend && npm run test:stage3-contract` 先按预期失败，实现后通过。
- `cd backend && python -m compileall app` 通过。
- `cd backend && python -m unittest discover tests` 通过，`Ran 103 tests OK`。
- `cd frontend && npm run test:auth-contract` 通过。
- `cd frontend && npm run test:stage3-contract` 通过。
- `cd frontend && npm run build` 通过，仍有 Vite chunk size warning。

## 2026-06-16 第二十四轮 OCR/LLM 保真与可回溯修复

当前项目针对 3 张本地 MVP smoke 样例暴露的 OCR/LLM 保真问题，优先收口“可回溯、可定位、禁止 LLM 猜题改题意”，而不是继续接入本地 OCR 或扩展导出能力。

新增能力：

- Draft detail / recognize / save-to-bank 响应新增可选 `recognition_debug`，包含 `ocr_provider`、`ocr_raw_text`、`llm_cleaned_text`、`ocr_error`、`llm_error`。
- `recognition_debug` 复用已有 `OCRRun`、`LLMRun`、`Draft.current_content` 字段，不新增数据库字段，不做迁移。
- Dashboard 题目录入结果区新增默认折叠的“识别调试信息”，展示“原始 OCR 文本”和“LLM 清洗文本”，便于人工比较原图、OCR 原文、LLM 清洗结果和当前草稿。
- Draft LLM prompt 调整为保真整理模式：禁止猜题、补题、改题意、替换变量/焦点编号/线段名、删除残缺选项或把一个数学表达式改成另一个表达式。
- 增加后端测试锁定 prompt 防篡改规则和 Draft detail 调试字段，前端契约测试锁定调试展示入口。

当前边界：

- 本轮不提升 OCR 准确率，不接入 RapidOCR、PaddleOCR、Pix2Text。
- 未修改 OCRService provider 选择逻辑、BaiduOcrProvider、legacy `/api/v1/recognize`、PaperRenderModel 或 PaperPreview 打印逻辑。
- 未新增数据库字段、迁移或 QuestionAsset 表。
- LLM prompt 约束只能降低篡改概率，仍需用 3 张 smoke 图片复测确认错误来源。

验证结果：

- `cd backend && python -m compileall app` 通过。
- `cd backend && python -m unittest tests.test_llm` 通过，`Ran 23 tests OK`。
- `cd backend && python -m unittest tests.test_draft_pipeline` 通过，`Ran 16 tests OK`。
- `cd backend && python -m unittest discover tests` 通过，`Ran 102 tests OK`。
- `cd frontend && npm run test:auth-contract` 通过。
- `cd frontend && npm run test:stage3-contract` 通过。
- `cd frontend && npm run build` 通过，仍有 Vite chunk size warning。

## 2026-06-16 第二十三轮 MVP 使用闭环与本地 smoke 样例收口

当前项目从 OCR 评估基础阶段转入 MVP 使用闭环收口：优先保证少量真实用户可以完成“上传图片 -> Draft 识别 -> 人工编辑 -> 保存题库 -> 创建试卷 -> 预览 -> 浏览器打印/另存 PDF”的本地演示链路。

新增能力和文档：

- 新增 `docs/DEMO_FLOW.md`，说明一次 MVP Demo 从启动前后端到浏览器打印/另存 PDF 的完整流程。
- 新增 `docs/MVP_SMOKE_CHECKLIST.md`，约定 3 张本地 PDF 截图 smoke 图片和人工检查项。
- `.gitignore` 已忽略 `data/manual_smoke/ocr_images/` 和 `data/manual_smoke/predictions/`，真实图片和本地预测记录不提交到 Git。
- `PaperPreview.vue` 新增最小“打印/导出 PDF”按钮，点击后调用 `window.print()`。
- `PaperPreview.vue` 新增最小 print CSS，打印时隐藏试卷列表、详情按钮、预览工具栏和不必要导航，保留 A4 预览内容。
- `frontend/tests/paper-mvp-contract.test.mjs` 增加打印入口契约检查。

当前边界：

- OCR Eval 暂停扩展，本轮不新增复杂评估集。
- 当前默认 OCR provider 仍为 `baidu`，本地 OCR 尚未接入。
- 当前 smoke 图片来自本地 PDF 截图，不覆盖真实拍照噪声、阴影、倾斜、手写批注或低清晰度场景。
- 当前导出方案为浏览器打印/另存为 PDF，服务端 PDF/DOCX 导出尚未实现。
- 未修改 Draft recognize 主流程，未修改 legacy `/api/v1/recognize`，未修改 OCRService provider 选择逻辑。
- 未修改 PaperRenderModel 核心数据结构，未做数据库迁移。

验证结果：

- `cd frontend && node ./tests/paper-mvp-contract.test.mjs` 先按预期失败，提示缺少浏览器打印导出、按钮文案和 print CSS；实现后通过，`Paper MVP frontend contract passed.`。
- `cd backend && python -m compileall app` 通过。
- `cd backend && python -m unittest discover tests` 通过，`Ran 102 tests OK`。
- `cd frontend && npm run build` 通过，仍有 Vite chunk size warning。

## 2026-06-16 第二十二轮 OCR 方案评估集与评估指标基础

当前项目在第二十一轮 Draft OCR Provider 抽象之后，新增 OCR 离线评估集和文本级评估指标基础，但不接入新 OCR 引擎，不调用真实 OCR API。

新增能力：

- 新增轻量 OCR eval case JSON 结构，记录 `case_id`、占位 `image_path`、人工 `expected_text`、类别、难度、关键术语和说明。
- 新增轻量 OCR prediction JSON 结构，记录 `case_id`、`provider`、`predicted_text`、`latency_ms` 和 `error`。
- 新增 `ocr_evaluation.py`，支持文本归一化、单条 prediction 评估、批量按 provider 汇总。
- 指标包括 exact match、normalized exact match、文本相似度、长度差、关键术语召回和错误标记。
- 新增 `docs/OCR_EVAL.md`，说明为什么先建立评估标准，再接入本地 OCR provider。

当前边界：

- OCR Provider 已抽象，OCR Eval 基础已建立，本地 OCR 尚未接入。
- 当前默认 OCR provider 仍为 `baidu`。
- 未修改 Draft recognize 主流程，未修改 legacy `/api/v1/recognize`。
- 未接入 RapidOCR、PaddleOCR、Pix2Text 或云 fallback。
- 当前评估只是文本级初步评估，不覆盖数学公式语义、几何图结构或版面理解。
- 尚未建立真实大规模高中数学题图片评估集。

验证结果：

- `cd backend && python -m compileall app` 通过。
- `cd backend && python -m unittest tests.test_ocr_evaluation` 通过，`Ran 6 tests OK`。
- `cd backend && python -m unittest discover tests` 通过，`Ran 102 tests OK`。

## 2026-06-06 第二十一轮 OCR Provider 抽象与部署成本控制基础

当前项目完成 Draft recognize OCR Provider 抽象基础，但不替换 OCR 引擎，不改变 legacy `/api/v1/recognize`。

新增能力：

- 新增内部统一 `OCRResult` 和 `OcrProvider` 接口，字段包含 text、provider、confidence、boxes、raw_response_summary、latency_ms、error 等。
- 新增 `BaiduOcrProvider`，只封装既有 `ocr_engine.py` 行为，不改变百度 OCR 识别逻辑或文本处理口径。
- 新增 `OCRService`，通过 `OCR_PROVIDER` 选择 provider；当前实际支持 `baidu`。
- `OCR_PROVIDER` 默认 `baidu`，`OCR_FALLBACK_PROVIDER` 已预留但本轮未启用 fallback。
- Draft recognize 改为调用 `OCRService`，OCRRun 记录实际 provider，性能日志增加 `ocr_provider`。
- 未知 OCR provider 会明确返回 `unsupported_provider` / `unsupported_ocr_provider:<provider>`。

当前边界：

- 本轮未接入 RapidOCR、PaddleOCR、Pix2Text 或任何本地 OCR。
- 本轮未解决百度 OCR 成本问题，只为后续切换和 fallback 打基础。
- 本轮未修改数据库模型、Alembic 迁移、PaperRenderModel、PaperPreview、前端或 legacy `/api/v1/recognize`。
- 自动化测试均使用 fake / mock，不真实调用百度 OCR API。

验证结果：

- `cd backend && python -m unittest tests.test_ocr_provider` 通过，`Ran 4 tests OK`。
- `cd backend && python -m unittest tests.test_draft_pipeline.DraftPipelineTests.test_draft_pipeline_recognize_is_lightweight_and_save_to_bank_sets_metadata_pending` 通过。
- `cd backend && python -m compileall app` 通过。
- `cd backend && python -m unittest discover tests` 通过，`Ran 96 tests OK`。

## 2026-06-06 第二十点六轮 Draft LLM 非思考模式 + JSON 输出稳定化

当前项目暂停第二十一轮新功能，根据 DeepSeek 官方文档将第二十点六轮目标从“单纯提高 max_tokens”调整为 Draft LLM 非思考模式和 JSON 输出稳定化。

新增能力：

- Draft LLM 调用默认关闭 thinking：OpenAI SDK 调用传入 `extra_body={"thinking": {"type": "disabled"}}`。
- thinking mode 可通过 `LLM_THINKING_MODE` 配置，默认 `disabled`。
- 启用 JSON Output：OpenAI SDK 调用传入 `response_format={"type": "json_object"}`。
- system/user prompt 均明确 JSON 要求，user prompt 包含 JSON 输出样例。
- Prompt 角色调整为“高中数学 OCR 文本清洗与结构化工具”，强调不解题、不证明、不分析、不输出推理过程，只修正 OCR、只规范 LaTeX、只返回 JSON。
- `max_tokens` 可通过 `LLM_MAX_TOKENS` 配置，默认 `2048`；timeout 可通过 `LLM_TIMEOUT_SECONDS` 配置，默认 `45` 秒。
- 不传 `reasoning_effort`，避免 DeepSeek low/medium 映射为 high。
- 第二十点五轮安全摘要日志继续保留：`finish_reason`、`content_len`、`reasoning_content_len`、`usage_completion_tokens`、`usage_total_tokens`、`raw_response_preview` 等字段仍记录。
- `finish_reason=length` 且 content 为空时继续 fallback，并返回可区分 detail：`deepseek_length_exhausted_empty_content`。

当前边界：

- 本轮未修改 PaperRenderModel、PaperPreview、前端、数据库模型、Alembic 迁移或 legacy `/api/v1/recognize`。
- 本轮未把 max_tokens 直接升到 6000。
- 本轮未把 `reasoning_content` 当作 `corrected_text` 使用。
- Draft fallback 状态机未改变：LLM 失败仍返回 `draft_ready + partial_success=True`。
- 复杂椭圆题仍需真实在线复测，以确认关闭 thinking 和 JSON Output 后是否消除 empty content。

验证结果：

- `cd backend && python -m unittest tests.test_llm` 通过。
- `cd backend && python -m unittest tests.test_draft_pipeline.DraftPipelineTests.test_draft_recognize_records_empty_content_invalid_response` 通过。
- `cd backend && python -m compileall app` 通过。
- `cd backend && python -m unittest discover tests` 通过，`Ran 92 tests OK`。

## 2026-06-06 第二十点五轮 Draft LLM 空响应诊断增强

当前项目暂停第二十一轮新功能，针对第二十轮人工验收发现的复杂 OCR 文本触发 DeepSeek empty content 问题，完成 Draft LLM 响应解析的最小可观测性增强。

新增诊断能力：

- `NLPService.analyze()` 对 DeepSeek 响应生成安全摘要日志，覆盖 response 类型、id、model、choices 数、finish_reason、message role、content 长度和截断预览、refusal、reasoning_content、tool_calls、usage token、输入长度、配置模型、timeout 和截断 raw response preview。
- empty content、空 choices、缺 choices、非 JSON、缺 `corrected_text`、字段结构非法等分支不再打印完整 response/result，改为打印安全摘要。
- empty content 的 `detail` 包含 `choices_count`、`finish_reason`、`content_len`、`completion_tokens`，便于下一次复杂题复现时定位原因。
- Draft fallback 状态机未改变：LLM 失败仍返回 `draft_ready + partial_success=True`，并保留 warning 和 LLMRun 错误信息。

当前边界：

- 本轮未修改 PaperRenderModel、PaperPreview、前端、数据库模型、Alembic 迁移或 legacy `/api/v1/recognize`。
- 本轮未恢复 `response_format={"type": "json_object"}`；是否启用需等待复杂椭圆题复现后的日志证据。
- 本轮不表示已彻底解决所有 DeepSeek 空响应，只表示已有可诊断日志和测试保护。

验证结果：

- `cd backend && python -m compileall app` 通过。
- `cd backend && python -m unittest discover tests` 通过，`Ran 90 tests OK`。

## 2026-06-06 第二十轮 PaperRenderModel + 作业模板预览 MVP

当前项目在不修改 Paper / PaperItem 数据库模型、不做迁移、不做 PDF / DOCX 导出、不切换 Draft/Paper 主流程的前提下，为已有试卷增加学生版作业预览能力。

新增能力：

- 新增 `POST /api/v1/papers/{paper_id}/render-model`，将 Paper / PaperItem 快照转换为 PaperRenderModel。
- 当前仅支持 `template_type=homework`、`version=student`、`paper_size=A4`、`group_by=question_type`、`sort_by=position`。
- 支持 `answer_area_mode=none` 和 `after_each_question`，默认 `none`。
- PaperRenderModel 按 `question_type_snapshot` 分组，每组内按 `position` 排序，`display_number` 全局连续。
- `question_type_snapshot` 为空时归入 `unknown / 未分类`。
- 学生版响应层面不返回答案解析快照。
- `PaperPanel.vue` 增加预览入口，`PaperPreview.vue` 渲染 A4 作业样式并复用 `renderMarkdown.ts`。

当前边界：

- 不支持自动分页；长题会撑开 A4 视觉容器。
- 不支持 PDF / DOCX 导出。
- 不支持用户自定义模板、模板编辑器、拖拽排序、知识点排序、难度排序或复杂答题卡。
- 当前预览适合 MVP 验收，不等同于正式打印排版引擎。

## 2026-06-04 第十九轮性能收口：元数据后台补全

当前项目在不重构 OCR / Draft / Paper 主流程、不删除 legacy recognize、不新增排序/模板/导出/答题区/智能组卷的前提下，将题型与五星难度从同步 Draft recognize 主链路拆出，改为保存入题库后后台补全。

新增能力：

- LLM analyze 默认轻量返回 `corrected_text` 和 `knowledge_tags`；题型/难度评估需显式调用元数据评估。
- 旧字段 `tags` 继续兼容；`corrected_text` 仍是主结果。
- Draft recognize 只强制等待 OCR + 轻量 LLM 洗稿 + 知识点标签，不再强制等待题型/难度。
- Draft save-to-bank 创建 `Question` 后设置 `metadata_status=pending`，并通过 FastAPI `BackgroundTasks` 后台补全题型与难度。
- Question 列表和详情返回题型、难度以及 `metadata_status` / `metadata_error` / 开始结束时间。
- PaperItem 仅在 Question 元数据 ready 且已有难度时保存题型与难度快照；pending/failed/null 时快照为空但不阻止组卷。
- `BankPanel.vue` 支持展示“元数据评估中”“难度评估失败”“未评估”和五星难度。
- Draft recognize 增加 `[DraftRecognizePerf]` 性能日志；后台元数据评估增加 `[QuestionMetadataPerf]` 性能日志。
- 补充 recognize 和 metadata 阶段耗时日志：Draft recognize 记录 OCR、轻量 LLM、total 和失败阶段；后台 metadata 记录 load、prompt、api、parse、db 和 total。

当前边界：

- 不支持按难度排序或筛选。
- 不支持按知识点排序。
- 不支持组卷模板、自定义模板、PDF / DOCX 导出、答题区域或智能组卷。
- LLM 难度评分是估计值，不是绝对标准。
- 历史题目可能没有题型和难度字段。
- 用户编辑题目后不会自动重新评估难度。
- 前端不轮询元数据状态；用户刷新题库后可看到后台评估结果。
- 后台任务依赖当前后端进程，服务重启可能丢失正在执行的元数据评估任务。

## 2026-06-03 第十八轮前端组卷入口 MVP

当前项目在不改动后端 Paper API 主逻辑、不改动 Draft flow、不改动 legacy recognize 的前提下，新增前端最小组卷入口。

新增前端能力：

- `BankPanel.vue` 支持从当前题库勾选题目、显示已选数量，并创建试卷。
- 创建试卷调用 `POST /api/v1/papers`，items 使用当前已选题目生成 `{ question_id, score }`，score 当前统一为 `0`。
- 新增 `PaperPanel.vue`，支持查看当前用户试卷列表和试卷详情。
- `Dashboard.vue` 新增独立“组卷”菜单入口，不干扰题目录入、Draft 保存入库、题库查看和历史记录。
- 试卷详情中的题目内容、答案、解析继续复用 `frontend/src/utils/renderMarkdown.ts` 渲染 Markdown / LaTeX。

当前组卷前端能力边界：

- 只支持手动从题库选题创建试卷。
- 不支持拖拽排序。
- 不支持分值编辑。
- 不支持 PDF / Word 导出。
- 不支持智能组卷。
- 不支持复杂试卷排版或打印样式优化。

## 2026-05-27 第十七轮组卷 MVP 后端最小竖切

当前项目在既有 Draft flow、legacy recognize 和题库保存逻辑不重构的前提下，新增后端最小组卷能力。

新增接口：

- `POST /api/v1/papers`
- `GET /api/v1/papers`
- `GET /api/v1/papers/{paper_id}`

当前组卷能力边界：

- 只支持登录用户手动选择自己题库中的题目组卷。
- `PaperItem` 保存题目快照；如存在 `QuestionRevision`，优先以最新 revision 生成快照。
- 当前不支持智能组卷、PDF/Word 导出、前端组卷、拖拽排序、自动配比。

## 2026-05-27 第十六轮 release checkpoint

当前项目进入“可启动、可验证、可继续开发”的状态。该结论不等于生产可用，也不表示所有正式流水线已经闭环。

## 当前结论

- `Dashboard.vue` 当前上传主路径已初步接入 Draft 流水线，并接受为新的前端主路径基线。
- `POST /api/v1/recognize` 仍存在，后端未删除、未重构，定义为 legacy / 兼容入口。
- 第七轮已新增 Draft 后端旁路正式流水线最小竖切。
- 第八轮已完成后端 LLM LaTeX 分隔符程序级归一化。
- 第九轮已补充 LLM analyze 成功路径 LaTeX 归一化集成测试。
- 第十轮已完成前端 Markdown / LaTeX 渲染工具抽取。
- 第十一轮补充确认：当前 `Dashboard.vue` 上传按钮实际调用 `POST /api/v1/assets`、`POST /api/v1/drafts`、`POST /api/v1/drafts/{draft_id}/recognize`，保存调用 `POST /api/v1/drafts/{draft_id}/save-to-bank`。
- `Dashboard.vue` 中仍保留 `runLegacyRecognition()` 对 `POST /api/v1/recognize` 的调用，但当前上传按钮未引用该函数。
- 本轮接受当前 Dashboard Draft 初步接入作为新基线；这属于渐进式迁移的路线推进，不再按疑似误改处理。
- Draft 主路径已接受为当前基线，已补充 API smoke 验证文档；当前仍是可启动、可验证、可继续开发，不是生产可用。
- 第十三轮已阶段性收口 Draft 后端异常契约：缺失 asset/draft、非图片 recognize、未 ready 保存、重复保存、已保存后再次识别均返回可解释的 4xx。
- 第十四轮已收口 Dashboard Draft 主路径 UI 状态：上传素材、创建草稿、识别、保存入题库有阶段化提示；识别中和保存中按钮分别禁用；`partial_success` 作为 warning 展示；常见错误码有前端可理解提示。
- 第十五轮已完成 legacy recognize 引用审计与最小标注：Dashboard 主路径确认继续走 Draft，`runLegacyRecognition()` 和 `POST /api/v1/recognize` 均保留为 legacy / 兼容入口。
- 第十六轮已完成阶段性文档去重和 release checkpoint：README、API、smoke 文档、STATUS、DECISIONS、KNOWN_ISSUES、WORKLOG 的当前口径已统一。
- 第十七轮已完成组卷 MVP 后端最小竖切，新增 Paper / PaperItem、papers API、service 和后端测试；不涉及前端、导出或智能组卷。
- 第十八轮已完成前端组卷入口 MVP：题库选题、创建试卷、试卷列表、试卷详情已接入；不涉及后端 Paper API 主逻辑、导出、智能组卷或 Draft/recognize 改动。
- 第十九轮已完成 LLM 题型与五星难度元数据，并完成性能收口：Draft recognize 主链路只强制等待 OCR、`corrected_text` 和知识点标签，题型/难度在 save-to-bank 后通过后台任务补全到 Question。
- Draft 前端接入不是完整生产级完成，legacy recognize 已完成引用审计和误用风险标注，仍需后续退场策略执行。
- 当前推荐 smoke 文档为 `docs/API_SMOKE_DRAFT_FLOW.md`；`docs/API_SMOKE_DRAFT_PIPELINE.md` 保留为脚本化 smoke 补充文档。
- `saved_to_bank` 状态重复 save-to-bank 当前返回 `409`，本轮不改为幂等返回，且已测试不会重复创建 Question 或 QuestionRevision。
- 后端启动和管理员初始化前必须先执行 `alembic upgrade head`。
- `backend/.env` 是本地文件，不应提交；示例配置使用 `backend/.env.example`。

## 第七轮后端旁路 Draft 流水线

新增接口：

- `POST /api/v1/drafts`
- `GET /api/v1/drafts/{draft_id}`
- `POST /api/v1/drafts/{draft_id}/recognize`
- `POST /api/v1/drafts/{draft_id}/save-to-bank`

状态流转：

- `draft_created`
- `recognizing`
- `draft_ready`
- `failed`
- `saved_to_bank`

落库行为：

- `DraftEvent`：创建、开始识别、识别成功/失败、保存入题库都会写入。
- `OCRRun`：Draft 识别后写入，失败也记录错误。
- `LLMRun`：OCR 成功后写入，LLM 失败记录错误并允许 `partial_success`。
- `QuestionRevision`：保存入题库时创建 v1，并关联 `source_asset_id`、`ocr_run_id`、`llm_run_id`。

## 最新验证结果

| 范围 | 命令 | 状态 |
| --- | --- | --- |
| frontend | `npm run test:auth-contract` | 通过 |
| frontend | `npm run test:stage3-contract` | 通过 |
| frontend | `npm run build` | 通过，仅有 Vite chunk size warning |
| backend | `python -m compileall app` | 通过 |
| backend | `python -m unittest discover tests` | 通过，`Ran 74 tests OK` |
| backend | `alembic current` | 默认本地 SQLite 当前 `20260604_0004` |
| backend | `DATABASE_URL=sqlite:///./alembic_verify_tmp.db alembic upgrade head; alembic current` | 通过，当前 `20260604_0005 (head)` |
说明：

- 第十九轮性能收口已重新实测 `python -m compileall app`、`python -m unittest discover tests`、`npm run build`、`npm run test:auth-contract`、`npm run test:stage3-contract`。
- 第十九轮性能收口默认 `alembic upgrade head` 因当前本地 SQLite 数据库只读失败，默认 `alembic current` 显示仍为 `20260604_0004`；已改用临时 SQLite 数据库验证迁移链成功到 `20260604_0005 (head)`。
- 第十九轮初次元数据实现已重新实测 `python -m compileall app`、`python -m unittest discover tests`、`npm run build`、`npm run test:auth-contract`、`npm run test:stage3-contract`；当时临时 SQLite 迁移链验证到 `20260604_0004 (head)`。
- 第十八轮已重新实测 `npm run build`、`npm run test:auth-contract`、`npm run test:stage3-contract`；其中 `test:stage3-contract` 已纳入 Paper MVP 前端契约检查。
- 第十七轮已重新实测 `python -m compileall app`、`python -m unittest discover tests`。
- 第十六轮已重新实测 `npm run test:auth-contract`、`npm run test:stage3-contract`、`npm run build`、`python -m compileall app`、`python -m unittest discover tests`。
- `python -m pytest tests/test_draft_pipeline.py` 和 `python -m pytest tests/test_llm.py` 为第十三轮专项验证结果，本轮未重复执行。
- `npm run build` 仍有 Vite chunk size warning，但构建成功。

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
- Dashboard Draft 接入已接受为新基线，已补充 API smoke 验证文档，后端异常契约和前端 UI 状态已完成阶段性收口；仍需后续 legacy 清理。
- Draft 重复保存当前以 `409` 拒绝，不返回既有保存结果；如后续需要幂等返回，应另行设计保存结果追踪方式。
- mock/legacy 文件需要清理，但不应在下一阶段做大重构。
- 后端测试已通过本轮验证，但稳定性仍需持续关注。
- 真实第三方失败场景仍缺少系统化在线验证矩阵。
- 完整多页 PDF 和批量 draft 能力未完成，不应在当前状态中夸大。
- legacy recognize 最终退场未完成，当前仍保留为兼容入口。
- 当前状态不是生产可用。

## 下一阶段口径

下一阶段以收敛和稳定为主，不新增规划之外的大模块，不做大重构。优先级为：前端中文乱码、mock/legacy 文件清理、后端测试稳定性。

明确不做：

- 不删除 `/recognize`。
- 不把 Draft 前端接入写成完整生产级完成。
- 不做 OCR/LLM provider 抽象。
- 不做异步队列。
- 不做批量 PDF。
- 不做多页 draft 管理。
- 不把 legacy recognize 写成 Dashboard 当前主路径。
