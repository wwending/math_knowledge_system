# ADR 0001: 题目区段与配图采用混合持久化

- 状态：Accepted
- 日期：2026-08-29
- 关联：GitHub Issue #127，父 Issue #118

## 背景

现有 Question 使用扁平 `content`、`answer`、`analysis` 字段；QuestionRevision 使用未版本化 JSON，并只能通过一个 `figure_asset_id` 表达单图；PaperItem 只冻结三段文本和单个图片文件名。这些结构不能表达文字与图片区交错、一个图片区多图、配图跨版本稳定身份或完整的多图试卷快照。

既有约束必须继续成立：

- Question 保留可查询的当前投影，实际编辑追加不可变 revision；
- 历史 PaperItem 不随源 Question 变化；
- SourceAsset 是全局去重的共享字节记录，不是所有权边界；
- 当前扁平字段和单图字段仍有兼容消费者；
- 迁移必须保护历史数据并支持可验证的 downgrade。

## 决策

采用“配图资产关系化 + 区段内容结构化快照”的混合持久化。

### 关系化部分

1. `QuestionFigure` 提供由 Question 拥有的稳定 UUID 身份。
2. QuestionFigure 分别引用：
   - 来源 SourceAsset；
   - 物化后的裁剪配图 SourceAsset；
   - 来源素材中的归一化裁剪坐标。
3. QuestionRevision 通过正式关联表声明所引用的 QuestionFigure。
4. 关联表携带 `question_id`，并使用 Question 范围内的组合外键，数据库层禁止 revision 引用其他 Question 的 figure。
5. PaperItem 使用独立配图快照关系，冻结 figure UUID、资产引用和来源裁剪元数据；历史渲染不得依赖当前 QuestionFigure。
6. SourceAsset 不增加所有权或级联删除语义。

### 结构化快照部分

Question 当前投影、QuestionRevision 和新 PaperItem 使用带版本号的 JSON 快照表达三区段、内容块和布局：

```json
{
  "schema_version": 2,
  "sections": {
    "stem": {
      "blocks": [
        {
          "id": "UUID",
          "kind": "text",
          "markdown": "题干"
        },
        {
          "id": "UUID",
          "kind": "image_area",
          "height_ratio": 0.4,
          "placements": [
            {
              "figure_id": "UUID",
              "x": 0.0,
              "y": 0.0,
              "width": 0.5,
              "height": 1.0
            }
          ]
        }
      ]
    },
    "answer": {"blocks": []},
    "analysis": {"blocks": []}
  }
}
```

约束：

- `schema_version` 固定为 `2`；未知版本必须显式拒绝，不能猜测解析。
- `stem`、`answer`、`analysis` 三个键始终存在。
- 区段内数组顺序就是内容顺序，不另存可漂移的 position。
- block `kind` 只允许 `text` 或 `image_area`。
- block ID、image-area ID 使用规范 UUID 字符串，并在同一快照内唯一。
- 文字块保存 `markdown`；空文字块不进入规范快照。
- 图片区使用正数 `height_ratio` 表达相对区段宽度的高度。
- placement 引用稳定 QuestionFigure UUID；其 `x/y/width/height` 是图片区坐标空间中的归一化值。
- 题干必须至少包含一个非空文字块或至少一个含 placement 的图片区。
- 答案和解析可以为空；纯图片区段有效。
- 配图保持自身比例，不自动拉伸填满图片区。
- 图片区在打印中不可拆分；过高内容由后续编辑能力拆成多个图片区。

### 稳定身份

- 修改文字、移动 block 或移动 figure placement 时保留已有 UUID。
- 新建或拆分 block/image area 时分配新 UUID。
- 合并后的新结构保留一个明确选定的存续 UUID，其余 UUID 不再出现在新 revision。
- legacy 投影产生的 UUID使用持久化迁移结果作为后续身份来源；旧历史 revision 的只读适配使用确定性 UUID，避免同一记录重复读取时漂移。

### 兼容与迁移

1. 新增独立 v2 JSON 列，不覆盖既有 QuestionRevision `content` JSON。
2. 保留 Question 的 `content`、`answer`、`analysis`、`origin_image`、单图字段，以及 PaperItem 现有快照字段。
3. legacy 到 v2 的标准映射：
   - 非空 `content` 变成一个 stem 文字块；
   - 当前单图变成位于 stem 文字块之后的一个图片区；
   - 非空 answer/analysis 各变成一个文字块；
   - 空 answer/analysis 变成空区段。
4. v2 到兼容文本的投影只按顺序用空行连接文字块；图片区不产生 Markdown 标记。
5. 迁移持久化当前 Question 和每题最新 revision 的 v2 投影。
6. 没有 revision 的 Question 不自动创建伪造 revision。
7. 旧历史 revisions 不批量重写，由兼容适配器使用确定性 UUID 读取；用户下一次实际保存才产生正式 v2 revision。
8. 历史 PaperItems 不回填。#127 只增加 nullable v2 结构；后续 PaperItem 功能开始创建完整快照。
9. 无有效题干且无可用配图的异常旧题不得阻塞整个升级，也不得被写入虚构用户文本；其 v2 投影保持为空兼容态，由读取边界识别。

### Downgrade

Downgrade 保证：

- 可以删除新增表、约束和列并回到旧 schema；
- 旧扁平字段和旧 revision JSON 仍可被旧版本应用读取；
- 不保证把仅能由 schema v2 表达的多图布局无损反投影到旧单图结构。

部署执行 downgrade 前仍须备份。该限制是数据模型表达能力差异，而不是静默丢失承诺。

## 备选方案

### 所有关系只放在 JSON 中

拒绝。它无法通过数据库外键防止悬空引用或跨题引用，也无法为配图建立稳定的可查询身份。

### 将所有区段、block、图片区和 placement 全部关系化

拒绝。嵌套内容排序和不可变 revision 快照会产生大量表、顺序更新和 join；当前没有独立查询每个文字块或 placement 的需求。结构化 JSON 更接近完整文档快照语义。

### 直接把现有 QuestionRevision.content 改成 schema v2

拒绝。现有服务依赖 `text/content/answer/analysis` 等 v1 键；原地换形会破坏旧读取路径并使 downgrade 必须做有损反向转换。

### 迁移时重写全部历史 revision 和 PaperItem

拒绝。批量重写会改变历史记录、扩大迁移风险，并违反试卷快照冻结边界。只迁移当前投影和最新 revision 足以为后续功能建立入口。

## 后果

- 后续 API 和编辑器可以围绕一个明确版本化文档合同工作。
- 数据库能约束 revision 与 figure 的同题完整性。
- 旧接口和渲染器可继续使用兼容字段。
- 在兼容期内同一内容同时存在结构化快照和扁平投影，写入边界必须集中维护二者一致性。
- PaperItem v2 的创建与渲染仍属于后续 Issue，本 ADR 和本期模型只提供数据基础。
