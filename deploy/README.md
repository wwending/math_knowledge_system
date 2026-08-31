# v0.1 单机部署

该部署栈用于 v0.1 Release Candidate 的单台 Linux 服务器验证。浏览器只访问 Nginx；Nginx 提供 Vue 静态文件，并把 `/api/`、`/static/` 和 `/healthz` 转发给内部 FastAPI 服务。后端端口 `8000` 仅在 Compose 网络中暴露，不映射到宿主机。试卷 PDF 由 FastAPI 调用内部 Gotenberg Chromium 即时生成；Gotenberg `3000` 不映射宿主机端口，浏览器不能直接访问。Gotenberg 禁用 JavaScript、`downloadFrom` 与公私网 HTTP(S) 子资源，并把 Chromium 并发限制为 1、等待队列限制为 4，以适应低资源部署。

## 前提条件

- 一台安装了 Docker Engine、Docker Compose v2、Git、curl、tar 和 sha256sum 的 Linux 服务器。
- 仓库建议检出到固定目录，例如 `/opt/math-knowledge-system`。
- 部署脚本需要能够创建并调整 `/srv/math-knowledge` 下目录的属主；首次执行通常使用 `sudo`。
- 当前 checkout 的完整 Git SHA 必须已有成功的 `main` `Publish release images` workflow；该 workflow 仅在对应 push 的 CI 全部通过后才运行，因此存在发布记录即隐含该 SHA 已通过测试门禁。部署调用方须从该次成功 workflow 取得 backend/web digest，并显式传给部署脚本。如 GHCR package 需要认证，管理员须在部署前完成 `docker login ghcr.io`，部署脚本不读取或管理凭据。
- 防火墙只开放当前访问模式所需端口。不要把应用 Web 的宿主机端口或 backend/Gotenberg 容器端口直接暴露到公网。

## RC HTTP 部署

```bash
git clone https://github.com/wwending/math_knowledge_system.git /opt/math-knowledge-system
cd /opt/math-knowledge-system
git switch main
cp deploy/.env.production.example deploy/.env
```

编辑 `deploy/.env`：至少生成随机 `SECRET_KEY`，填写服务器 IP/端口对应的 `CORS_ALLOW_ORIGINS`、百度 OCR 凭据和 DeepSeek 凭据。示例中的 `SERVER_IP`、`PORT` 和空密钥不能直接用于部署。`deploy/.env` 被 Git 忽略，不应提交。

```bash
chmod +x deploy/scripts/*.sh
sudo env \
  BACKEND_IMAGE_DIGEST='sha256:<backend-64-hex>' \
  WEB_IMAGE_DIGEST='sha256:<web-64-hex>' \
  ./deploy/scripts/deploy.sh
```

这里有三个互补的 artifact identity：Git SHA 是 source identity；同 SHA 的 GHCR tag 用于 release discovery / traceability；publisher 记录的 digest 是服务器实际消费的 immutable artifact identity。支持的发布路径是：合并到 `main` → `Publish release images` 成功并输出 backend/web digest → checkout 对应的精确 main SHA → 把两个 trusted digest 作为部署输入 → 按 `repository@sha256:...` pull → 验证两个镜像的 OCI `org.opencontainers.image.revision` 都等于 checkout SHA → backup、migration 和 rollout。部署脚本不会通过 SHA tag、`main` 或 `latest` 自行解析或选择 digest。

脚本拒绝 dirty Git worktree，也会在任何目录创建、pull、backup、migration 或服务替换前，要求两个 digest 严格匹配 `sha256:<64 lowercase hex>`。digest 缺失或格式非法会失败；pull、OCI revision 或 exact RepoDigest 不匹配也会失败，且不会继续 backup、migration 或启动服务。服务器不构建 application images，pull 失败没有本地 build fallback。最终报告包含 Git commit、完整 `repository@digest` image reference、revision 与 exact RepoDigest。脚本不会创建 PAT、执行 Docker login、读取 GHCR credential，也不会运行 `docker system prune`、删除 volume 或删除历史备份。

默认公网或普通 RC 使用 `HTTP_BIND_ADDR=0.0.0.0` 和 `HTTP_PORT=8080`，访问地址为 `http://SERVER_IP:8080`。SSH tunnel/private RC 推荐使用 `HTTP_BIND_ADDR=127.0.0.1` 和 `HTTP_PORT=8000`，以避免 Web 端口直接暴露到公网。访问链路为 `Windows localhost:8000` → SSH local forwarding → `Server 127.0.0.1:8000` → Web/Nginx → `backend:8000` (Docker internal only)。后端 `8000` 始终只在 Compose 内部网络中暴露，不映射到宿主机。当前已验收 Demo 的 DNS/HTTPS 边界见“正式 HTTPS”一节；其他环境仍须按自身域名和网络边界单独配置。前端生产构建默认使用当前页面同源地址，因此 API 请求为 `/api/v1/*`，上传资源为 `/static/*`；如有特殊需求仍可在构建时设置 `VITE_API_BASE_URL`。

如需创建初始管理员，可在部署后显式执行：

```bash
export BACKEND_IMAGE_DIGEST='sha256:<backend-64-hex>'
export WEB_IMAGE_DIGEST='sha256:<web-64-hex>'
docker compose --env-file deploy/.env -f compose.prod.yml run --rm \
  -e ADMIN_PHONE=实际手机号 -e ADMIN_PASSWORD='一次性强密码' \
  backend python -m app.scripts.create_admin
```

## 数据与迁移

宿主机持久化布局：

```text
/srv/math-knowledge/
├── data/
│   ├── math_knowledge.db
│   ├── uploads/
│   ├── static/
│   └── pdf_temp/
└── backups/
```

容器内固定使用 `/data/math_knowledge.db`、`/data/static`、`/data/uploads` 和 `/data/pdf_temp`。题目图片自 #44 起存放在公开 `/static` 挂载之外的 `uploads/` 目录，只能通过带鉴权与所有权校验的 `GET /api/v1/questions/{id}/image` 读取;`deploy.sh` 在部署时会自动把旧的 `${DATA_ROOT}/static/uploads` 迁移到 `${DATA_ROOT}/uploads`(若两个目录同时存在则拒绝执行,需人工合并)。**自 #59 起试卷题图快照按文件名引用 `uploads/` 内的文件，历史试卷的预览与 PDF 出图依赖该目录持久留存**——请确认备份计划覆盖 `uploads.tar.gz`（见下文备份章节）且任何清理脚本不得触碰该目录。试卷导出 PDF 仅在请求期间存在于内存和 Gotenberg 临时工作区，不写入持久化目录；`pdf_temp` 仍供既有 PDF 上传解析流程使用。后端镜像不包含 `.env` 或真实密钥，构建阶段不会调用 OCR/LLM。运行时 schema 开关被 Compose 强制关闭，数据库只通过以下显式命令升级：

```bash
export BACKEND_IMAGE_DIGEST='sha256:<backend-64-hex>'
export WEB_IMAGE_DIGEST='sha256:<web-64-hex>'
docker compose --env-file deploy/.env -f compose.prod.yml run --rm backend alembic upgrade head
```

## 题图检测模型（#58）

版面分析（题目图形区域自动检测）使用 rapid-layout + ONNXRuntime CPU。DocLayout-YOLO 模型（约 50MB `.onnx`）**不打包进镜像**：后端首次执行检测时从 ModelScope 下载到 `LAYOUT_MODEL_DIR` 并做 SHA256 校验，之后发版/换镜像都复用已下载文件，无需重新下载。

部署要求：

- 在 `deploy/.env` 中设置 `LAYOUT_MODEL_DIR=/data/models`（落在持久卷内；缺省值 `weights` 是容器内临时路径，重启即丢，会导致每次启动重新下载）。
- 首次启用时服务器需能访问 ModelScope（`www.modelscope.cn`）；离线环境可手动把模型放到 `LAYOUT_MODEL_DIR/doclayout_docstructbench.onnx`。
- 模型下载失败/缺失不会阻塞录入：系统降级为无图流程并记录 `[LayoutDetect]` warning 日志。
- 备份提示：`/data/models` 建议纳入备份范围（可选，丢失仅触发一次重新下载）。

## 备份和恢复

手工备份：

```bash
sudo ./deploy/scripts/backup.sh
```

由 `deploy.sh` 调用时，备份脚本继承本次目标 release 的两个 digest，因此数据库快照使用即将部署的 pinned backend image。独立手工运行且未显式提供 digest 时，脚本只接受当前 Compose project 中唯一运行的 backend/web 容器，并要求其 `.Config.Image` 分别是预期 GHCR repository 的合法 `repository@sha256:...` 引用；容器不存在、数量不唯一、仍使用 tag 或 repository 不符时会 fail closed，并提示显式提供 trusted digests。它不会从 Git SHA tag、`main` 或 `latest` 解析 digest，也不会 fallback build。

每次备份写入 `/srv/math-knowledge/backups/<UTC时间>/`，包含：

- 通过 SQLite Backup API 创建的一致数据库快照；
- `uploads.tar.gz`；
- `deploy_commit.txt`；
- 仅记录字段名、不记录值的 `environment_fields.txt`；
- `SHA256SUMS`。

环境变量文件本身不会进入备份，也不会提交到 Git。应使用 SSH 密钥和受限账号将备份同步到第二台服务器或独立存储，例如：

```bash
rsync -a --checksum /srv/math-knowledge/backups/ backup-user@SECOND_SERVER:/srv/backups/math-knowledge/
```

恢复使用 `deploy/scripts/restore.sh`：显式提供两个 trusted digest 与备份目录后，它依次完成 SHA256SUMS 校验 → 停栈 → 把现有 DB/uploads 隔离（移动而非删除，作为回退点）→ 恢复 DB 与 uploads → 修复属主(10001) → SQLite quick_check → `alembic upgrade head` → 起栈 → healthz 检查。完整的前置条件、每步预期输出、失败回退点与演练流程见 [`deploy/RESTORE_RUNBOOK.md`](./RESTORE_RUNBOOK.md)。

## 正式 HTTPS

应用 release 与 TLS infrastructure 是两个独立生命周期：应用 release 由 exact Git SHA 和 main publisher 记录的 backend/web digest 标识；TLS 由宿主机 edge 和证书管理系统维护，Caddy 不属于 application image digest。

2026-08-18 已验收 Demo 使用已配置的 Demo 域名、Host Caddy `2.11.4` 和 Let's Encrypt 托管证书。公网 IPv4 边界为 `22/80/443`，其中 `80` 重定向到 HTTPS，`443` 代理到 loopback `127.0.0.1:8000`；`backend:8000` 与 `gotenberg:3000` 仅在 Docker 内部。公网未开放 `8000/8080/3000`，也没有 IPv6 `80/443` listener。首次 HTTPS rollout 有意未启用 HSTS。

该 Demo 已使用 production security mode 完成自动验收与用户人工浏览器验收，但这不等于所有 production-readiness 工作均已完成。Demo 不自动跟随 main；已部署 release 保持其显式选择的 exact Git SHA 与 publisher digest，直到下一次授权 rollout。

其他正式环境仍应在 Web 容器前配置可信的 TLS 终止层（如主机 Caddy/Nginx、云负载均衡或隧道服务），使用真实证书，并避免直接开放应用端口。不要把测试证书或私钥提交到仓库。

正式环境至少改为：

```env
APP_ENV=production
CORS_ALLOW_ORIGINS=https://实际域名
AUTH_STRICT_SECURITY=true
SECURE_TRANSPORT_MODE=trusted_proxy_tls
REFRESH_TOKEN_COOKIE_SECURE=true
REFRESH_TOKEN_COOKIE_SAMESITE=lax
```

同时使用不少于 32 字符的随机 `SECRET_KEY`，确保 TLS 终止层覆盖并传递 `Host`、`X-Real-IP`、`X-Forwarded-For`、`X-Forwarded-Proto`，并通过防火墙限制 Web 容器的宿主机端口只能被该可信 TLS 代理访问。内层 Nginx 会保留外层代理提供的 `X-Forwarded-Proto`；若没有外层头，则使用当前连接协议。变更后重新运行部署脚本和完整 smoke。

## 运维检查

```bash
export BACKEND_IMAGE_DIGEST='sha256:<backend-64-hex>'
export WEB_IMAGE_DIGEST='sha256:<web-64-hex>'
docker compose --env-file deploy/.env -f compose.prod.yml ps
docker compose --env-file deploy/.env -f compose.prod.yml logs --tail=200 backend gotenberg web

# 默认 HTTP RC（HTTP_PORT=8080）
curl --fail http://127.0.0.1:8080/healthz

# 当前 HTTPS Demo（HTTP_PORT=8000）
curl --fail http://127.0.0.1:8000/healthz
curl --fail https://<demo-domain>/healthz

docker image inspect \
  --format '{{ index .Config.Labels "org.opencontainers.image.revision" }}' \
  "ghcr.io/wwending/math-knowledge-backend@${BACKEND_IMAGE_DIGEST}"
docker image inspect \
  --format '{{ index .Config.Labels "org.opencontainers.image.revision" }}' \
  "ghcr.io/wwending/math-knowledge-web@${WEB_IMAGE_DIGEST}"
```

也可以用 `docker image inspect` 的 `.RepoDigests` 或对运行中的容器执行 `docker inspect`，把 exact artifact digest、OCI revision、部署 commit 和用于发现 release 的完整 SHA tag 交叉比对。Compose 对 first-party backend/web 使用 digest；第三方 `gotenberg/gotenberg:8.34.0-chromium` 本阶段仍保持固定 version tag。

发布前仍需按 `docs/MVP_RELEASE_CHECKLIST.md` 完成真实百度 OCR + LLM + Draft + 题库 + 组卷 + Paper Preview smoke。本部署能力不改变业务逻辑，也不代表 v0.1 已正式生产验收。
