# 反馈收件箱运维手册（Feedback Inbox Runbook）

对应 issue：#98。反馈中心的 AI 部分（整理归纳、转正式 issue）**不在应用内实现**：
管理员在部署机上用 codex 手动触发，应用只负责收集、存储、状态流转和导出。

```
用户提交反馈 ──► 应用存储（待处理）
                    │
                    ▼  管理员定期（导出接口 + codex）
              归类去重 / 排序 ──► GitHub issue（候选清单在 GitHub，不在应用内展示）
                    │
                    ▼  管理员看过 issue 后回应用内
        反馈中心改状态：已采纳 / 已拒绝 ＋ 处理说明（提交者可见）
```

## 1. 导出接口

仅管理员可用。两个参数：

| 参数 | 取值 | 默认 | 说明 |
| --- | --- | --- | --- |
| `format` | `markdown` / `json` | `markdown` | json 供 codex 消费；markdown 供人阅读 |
| `status` | `pending` / `adopted` / `rejected` | `pending` | 整理工作流只需 pending |

获取 token 并导出的示例：

```bash
TOKEN=$(curl -s -X POST 'https://<host>/api/v1/auth/token' \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  -d 'username=<admin手机号>&password=<密码>' | jq -r .access_token)

curl -s -H "Authorization: Bearer $TOKEN" \
  'https://<host>/api/v1/admin/feedback/export?format=json&status=pending' \
  -o feedback-pending.json
```

返回 JSON 结构：

```json
{
  "status": "pending",
  "count": 2,
  "exported_at": "2026-08-25T12:00:05+00:00",
  "items": [
    {
      "id": 12,
      "category": "bug",
      "content": "……",
      "status": "pending",
      "review_note": null,
      "submitter": { "display_name": "张三", "phone": "13700000001" },
      "created_at": "2026-08-24T02:12:33",
      "updated_at": "2026-08-24T02:12:33",
      "screenshot_files": ["/absolute/path/under/UPLOAD_DIR/xxx.png"]
    }
  ]
}
```

`screenshot_files` 是**部署机上的绝对路径**（位于服务器 `UPLOAD_DIR`），codex 在同一台机器上可直接读取图片作为证据；无法解析的条目为 null。

## 2. codex 工作流 sketch

在部署机仓库目录起一个 codex 会话，把导出 JSON 喂给它：

> 以下是本产品用户反馈的导出数据（JSON，字段含 id/category/content/submitter/screenshot_files）。
> 请：1) 按语义归类去重（同问题多条合并计数）；2) 按 影响×频度 排序；
> 3) 对每条候选产出 GitHub issue 草稿（标题、背景、复现步骤或需求描述、期望行为），
>    写入 issues-candidates.md；4) 不要修改任何代码。

人工复核 issues-candidates.md 后再用 `gh issue create` 正式建 issue。
候选清单以 GitHub issue 为准，应用内不展示候选清单。

## 3. 回写循环

正式 issue 建好后，管理员在应用内「反馈中心 → 处理」：

- 状态改为 **已采纳** 或 **已拒绝**；
- 填写处理说明（≤500 字，提交者在自己的列表里可见）；
- 三态可自由切回纠错（如误拒后改回待处理），`updated_at` 记录最近一次变更。

## 4. 边界说明

- 提交频率暂无限制（内测决策，代码已预留加限制的位置）；
- 无自动状态流转、无通知推送——提交者通过列表查看进度；
- 反馈与截图仅提交者本人和管理员可见；截图走认证通道，无公开静态 URL；
- 单条反馈最多 5 张截图（前后端同限：后端 `constants.MAX_FEEDBACK_SCREENSHOTS`，
  前端 `FeedbackInboxPanel.FEEDBACK_MAX_SCREENSHOTS`，调整时两处同步）。
