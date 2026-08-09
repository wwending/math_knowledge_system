# v0.1 单机部署

该部署栈用于 v0.1 Release Candidate 的单台 Linux 服务器验证。浏览器只访问 Nginx；Nginx 提供 Vue 静态文件，并把 `/api/`、`/static/` 和 `/healthz` 转发给内部 FastAPI 服务。后端端口 `8000` 仅在 Compose 网络中暴露，不映射到宿主机。试卷 PDF 由 FastAPI 调用内部 Gotenberg Chromium 即时生成；Gotenberg `3000` 不映射宿主机端口，浏览器不能直接访问。Gotenberg 禁用 JavaScript、`downloadFrom` 与公私网 HTTP(S) 子资源，并把 Chromium 并发限制为 1、等待队列限制为 4，以适应低资源部署。

## 前提条件

- 一台安装了 Docker Engine、Docker Compose v2、Git、curl、tar 和 sha256sum 的 Linux 服务器。
- 仓库建议检出到固定目录，例如 `/opt/math-knowledge-system`。
- 部署脚本需要能够创建并调整 `/srv/math-knowledge` 下目录的属主；首次执行通常使用 `sudo`。
- 防火墙只开放选定的 HTTP 端口。不要开放后端 `8000`。

## RC HTTP 部署

```bash
git clone https://github.com/wwending/math_knowledge_system.git /opt/math-knowledge-system
cd /opt/math-knowledge-system
git switch deploy/v0.1-single-server
cp deploy/.env.production.example deploy/.env
```

编辑 `deploy/.env`：至少生成随机 `SECRET_KEY`，填写服务器 IP/端口对应的 `CORS_ALLOW_ORIGINS`、百度 OCR 凭据和 DeepSeek 凭据。示例中的 `SERVER_IP`、`PORT` 和空密钥不能直接用于部署。`deploy/.env` 被 Git 忽略，不应提交。

```bash
chmod +x deploy/scripts/*.sh
sudo ./deploy/scripts/deploy.sh
```

脚本依次创建持久化目录、构建镜像、备份已有数据、显式执行 Alembic migration、启动服务、等待健康检查，并输出容器状态与 Git commit。任何步骤失败都会返回非零退出码。它不会运行 `docker system prune`、删除 volume 或删除历史备份。

默认公网或普通 RC 使用 `HTTP_BIND_ADDR=0.0.0.0` 和 `HTTP_PORT=8080`，访问地址为 `http://SERVER_IP:8080`。SSH tunnel/private RC 推荐使用 `HTTP_BIND_ADDR=127.0.0.1` 和 `HTTP_PORT=8000`，以避免 Web 端口直接暴露到公网。访问链路为 `Windows localhost:8000` → SSH local forwarding → `Server 127.0.0.1:8000` → Web/Nginx → `backend:8000` (Docker internal only)。后端 `8000` 始终只在 Compose 内部网络中暴露，不映射到宿主机；DNS 和 HTTPS 可在正式上线阶段再配置。前端生产构建默认使用当前页面同源地址，因此 API 请求为 `/api/v1/*`，上传资源为 `/static/*`；如有特殊需求仍可在构建时设置 `VITE_API_BASE_URL`。

如需创建初始管理员，可在部署后显式执行：

```bash
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
│   ├── static/
│   │   └── uploads/
│   └── pdf_temp/
└── backups/
```

容器内固定使用 `/data/math_knowledge.db`、`/data/static`、`/data/static/uploads` 和 `/data/pdf_temp`。试卷导出 PDF 仅在请求期间存在于内存和 Gotenberg 临时工作区，不写入持久化目录；`pdf_temp` 仍供既有 PDF 上传解析流程使用。后端镜像不包含 `.env` 或真实密钥，构建阶段不会调用 OCR/LLM。运行时 schema 开关被 Compose 强制关闭，数据库只通过以下显式命令升级：

```bash
docker compose --env-file deploy/.env -f compose.prod.yml run --rm backend alembic upgrade head
```

## 备份和恢复

手工备份：

```bash
sudo ./deploy/scripts/backup.sh
```

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

恢复前先停止写入并再次备份当前数据；校验 `SHA256SUMS` 后，将数据库快照和解压后的 uploads 放回持久化目录，再执行 Alembic migration。恢复属于有覆盖风险的运维操作，本脚本不会自动执行。

## 正式 HTTPS

RC 的 IP + HTTP 端口仅用于 smoke，不适合正式生产。正式环境应在 Web 容器前配置可信的 TLS 终止层（如主机 Nginx、云负载均衡或隧道服务），使用真实证书并只开放 443。不要把测试证书或私钥提交到仓库。

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
docker compose --env-file deploy/.env -f compose.prod.yml ps
docker compose --env-file deploy/.env -f compose.prod.yml logs --tail=200 backend gotenberg web
curl --fail http://127.0.0.1:8080/healthz
```

发布前仍需按 `docs/MVP_RELEASE_CHECKLIST.md` 完成真实百度 OCR + LLM + Draft + 题库 + 组卷 + Paper Preview smoke。本部署能力不改变业务逻辑，也不代表 v0.1 已正式生产验收。
