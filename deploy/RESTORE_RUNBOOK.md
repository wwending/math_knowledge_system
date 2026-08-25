# 恢复 Runbook：备份 → 恢复全流程

本 runbook 描述如何用 `deploy/scripts/backup.sh` 产出的一份既有备份，把系统恢复到可用状态并通过验证。它同时服务两个场景：

1. **事故恢复**：数据库或 uploads 损坏/丢失后，按本流程恢复最近一份完好备份。
2. **定期演练**：在 Staging 上无事故地完整走一遍，证明备份真实可恢复（审计 #97 A1 的解除条件）。

执行入口是单一脚本 `deploy/scripts/restore.sh`；本文档负责前置条件、每步预期输出与失败回退点。首次真实恢复不应发生在事故压力下——演练请严格照抄命令。

## 恢复语义与范围

- **覆盖**：`math_knowledge.db`（SQLite 全库）与 `uploads/`（题目原图、试卷题图快照依赖的持久目录）。
- **不覆盖**：
  - `static/` —— 自 #44 起新写入不再落该目录，备份也不包含它；
  - `models/` —— 版面检测模型丢失只触发一次重新下载（见 `deploy/README.md` 题图模型一节）;
  - `pdf_temp/` —— 请求期临时目录，无需恢复；
  - `deploy/.env` 与 `SECRET_KEY` —— 不在备份中。保持 `.env` 稳定；若 `SECRET_KEY` 变更，已签发的 refresh token 全部失效，用户需重新登录。
- **schema 方向**：恢复旧备份后脚本立即执行 `alembic upgrade head`。因此最终状态是「旧数据 + 当前镜像的 schema」：数据回退，schema 前进，应用版本不变。
- **清库语义**：脚本在恢复前把当前 `math_knowledge.db`（含 `-wal`/`-shm`）与整个 `uploads/` **移出**活跃路径到隔离目录——恢复目标路径从零重建，不存在对现有状态的隐性依赖；这正是「清库 → 恢复」要证明的事，且多一层可回退保障。**脚本绝不删除任何数据。**

## 前置条件

- 能 SSH 登录服务器并执行 `sudo`；仓库检出在固定目录（下文以 `/opt/math-knowledge-system` 为例）。
- `deploy/.env` 存在且 `DATA_ROOT`、`BACKUP_ROOT`、`HTTP_PORT` 与现网一致（默认 `/srv/math-knowledge/data`、`/srv/math-knowledge/backups`、`8080`；HTTPS Demo 为 `8000`）。
- **两个 trusted digest**（`BACKEND_IMAGE_DIGEST`、`WEB_IMAGE_DIGEST`）：取自备份目录内 `deploy_commit.txt` 所指 commit 的成功 `Publish release images` workflow 输出。恢复必须显式提供 digest，脚本不从运行容器解析（事故时栈可能已停），缺失即拒绝执行。
- 对应 release 镜像已在主机本地（演练/恢复不做 pull）。确认：

```bash
docker image inspect "ghcr.io/wwending/math-knowledge-backend@${BACKEND_IMAGE_DIGEST}" >/dev/null && echo backend-image-present
```

- 磁盘空间 ≥ 当前数据体积的 2 倍（隔离区 + 恢复副本并存）：

```bash
sudo du -sh /srv/math-knowledge/data; df -h /srv/math-knowledge
```

- 已声明维护窗口：从 `compose stop` 到 `up -d` 完成期间服务不可用（演练约数分钟，取决于 uploads 体积）。

## Step 0：现场确认（演练前）

```bash
cd /opt/math-knowledge-system
export BACKEND_IMAGE_DIGEST='sha256:<当前运行的backend-64-hex>'
export WEB_IMAGE_DIGEST='sha256:<当前运行的web-64-hex>'
docker compose --env-file deploy/.env -f compose.prod.yml ps
curl --fail http://127.0.0.1:${HTTP_PORT:-8080}/healthz
```

预期：backend/web/gotenberg 三服务 Up 且 healthy；healthz 返回 `{"status":"ok"}`。若起点就不健康，先排查再演练。

## Step 1：取一份新备份

```bash
sudo ./deploy/scripts/backup.sh
```

预期输出结尾：`Backup written to /srv/math-knowledge/backups/<UTC时间戳>`。随即校验这份备份自身：

```bash
cd /srv/math-knowledge/backups/<UTC时间戳>
sudo sha256sum -c SHA256SUMS
```

预期：每个文件 `: OK`。**后续所有步骤都以这一份备份为源**；记下该目录绝对路径。

## Step 2：确定 digest 输入

```bash
cat /srv/math-knowledge/backups/<UTC时间戳>/deploy_commit.txt
```

用该 commit 在 GitHub Actions 找到对应 `Publish release images` 成功 run，取得 backend/web 两个 digest 并导出（Step 3 直接消费）：

```bash
export BACKEND_IMAGE_DIGEST='sha256:<backend-64-hex>'
export WEB_IMAGE_DIGEST='sha256:<web-64-hex>'
```

## Step 3：执行恢复

```bash
cd /opt/math-knowledge-system
sudo env \
  BACKEND_IMAGE_DIGEST="${BACKEND_IMAGE_DIGEST}" \
  WEB_IMAGE_DIGEST="${WEB_IMAGE_DIGEST}" \
  ./deploy/scripts/restore.sh /srv/math-knowledge/backups/<UTC时间戳>
```

逐段预期输出（每段都是回退点的界标）：

1. `Verifying backup checksums...` + 每个文件 `: OK` —— 任一 FAIL 立即中止，系统未受影响。
2. `Restore plan:` 四行 —— 核对源备份路径、data root、两个 image 引用无误再继续（脚本自动继续，人工复核输出即可）。
3. `Stopping stack (dependency order: web -> backend -> gotenberg)...`
4. `Quarantined: <DATA_ROOT>/math_knowledge.db` 与 `Quarantined: <DATA_ROOT>/uploads`（如存在 `-wal`/`-shm` 也各一行）。隔离目录形如 `<BACKUP_ROOT>/pre-restore-<UTC时间戳>`。
5. `Restoring database and uploads from ...`
6. `quick_check: ['ok']` 且 `foreign_key_check violations: []`。
7. Alembic 迁移输出 + `Current migration revision:` 显示当前 revision 且带 `(head)`。
8. `Health check passed: http://127.0.0.1:<HTTP_PORT>/healthz`。
9. 结尾 `Restore complete.` 报告块，含 `rollback point:` 隔离目录路径。

任一段落失败：脚本打印 `Restore FAILED ... No data was deleted.` 与隔离目录路径后停止，按下表回退。

## 失败回退点

| 失败阶段 | 系统状态 | 回退动作 |
|---|---|---|
| checksum 校验 | 未做任何变更 | 无需回退；更换备份或排查存储后重跑 |
| stop 之后、隔离之前 | 栈停止，原数据原位 | `docker compose --env-file deploy/.env -f compose.prod.yml start` 即恢复 |
| 隔离之后、migration 之前（含 restore/copy/quick_check 失败） | 原数据在隔离目录，活跃路径是半程新数据 | 手工移回：`sudo mv <隔离目录>/math_knowledge.db* <隔离目录>/uploads <DATA_ROOT>/` → `sudo chown -R 10001:10001 <DATA_ROOT>/math_knowledge.db <DATA_ROOT>/uploads` → `compose start` |
| migration 及之后 | schema 已前进；直接移回旧 DB 会因 schema 落后于镜像而不可用 | **不要手工移回**。重新完整执行一次 Step 3（同一或更早备份）：脚本会重新隔离、重新恢复并重放迁移 |

通用原则：先保留现场（隔离目录 + 完整报错输出），再决定回退或修复；隔离目录在任何验收完成前都不得清理。

## Step 4：恢复后技术验证

```bash
cd /opt/math-knowledge-system
docker compose --env-file deploy/.env -f compose.prod.yml ps
curl --fail http://127.0.0.1:${HTTP_PORT:-8080}/healthz
export BACKEND_IMAGE_DIGEST='sha256:<backend-64-hex>'
docker compose --env-file deploy/.env -f compose.prod.yml run --rm --no-deps backend alembic current
```

预期：三服务 Up/healthy；healthz OK；alembic current 与该镜像 head 一致（带 `(head)` 标记）。

可选的数据抽样核对（与演练前记录的主要表行数对比）：

```bash
docker compose --env-file deploy/.env -f compose.prod.yml run --rm --no-deps backend python -c '
import sqlite3
conn = sqlite3.connect("file:/data/math_knowledge.db?mode=ro", uri=True)
for table in ("users", "questions", "papers"):
    print(table, conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
conn.close()'
```

## Step 5：业务 smoke（最小集）

按 `docs/MVP_RELEASE_CHECKLIST.md` 执行完整 smoke；最小集必须包含：

1. 真实用户登录（refresh token 链路可用）；
2. 题库列表与题目详情打开（DB 主链路）；
3. **打开一张带题图的历史试卷 Preview 并导出 PDF**（`uploads/` 是 #59 出图的持久依赖，这是本次恢复的关键资产，不能省）。

全部通过后本次恢复才算成功。

## 收尾：隔离区清理

验收通过后，人工确认并删除隔离区（此为唯一允许的删除点，由人执行而非脚本）：

```bash
ls -la /srv/math-knowledge/backups/pre-restore-<UTC时间戳>
sudo rm -rf /srv/math-knowledge/backups/pre-restore-<UTC时间戳>
```

## 演练证据留存

完成后在本 issue 评论粘贴：备份目录名与 `sha256sum -c` 全部 OK 输出、Step 3 关键段落（checksum OK / Quarantined 两行 / quick_check ok / alembic `(head)` / Health check passed / Restore complete 块）、Step 4 的 `compose ps` 与行数抽样、Step 5 各项结论、隔离区路径及清理确认。

## 与 Staging rollout（#100）的同窗口关系

推荐顺序：先完成 #100 的当前 SHA rollout，紧接着立刻演练——此时 Step 1 的备份恰好来自刚上线的版本，一次停机窗口同时验证「新版本的部署」与「新版本的备份可恢复」。也可独立演练：digest 取目标 release 对应 workflow 的输出即可，流程完全相同。
