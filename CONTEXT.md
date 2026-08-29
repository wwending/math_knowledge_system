# Domain Context

## Question content

- **题目（Question）**：用户题库中的可持续修订实体。当前投影用于查询，完整历史由不可变的题目版本保存。
- **题目版本（QuestionRevision）**：题干区段、答案区段、解析区段及其配图布局在一次保存时形成的完整不可变快照。文字、配图与布局必须作为同一个版本提交。
- **内容区段（ContentSection）**：题目版本中的有序内容容器。区段类型固定为题干、答案和解析。
- **题干区段（StemSection）**：必需区段。可以包含文字块、图片区或二者的有序组合；纯图片区段有效。
- **答案区段（AnswerSection）**：可选区段。可以为空，也可以包含文字块、图片区或二者的有序组合。
- **解析区段（AnalysisSection）**：可选区段。可以为空，也可以包含文字块、图片区或二者的有序组合。
- **文字块（TextBlock）**：区段中的 Markdown/LaTeX 正常流内容。文字块具有跨版本稳定 UUID；图片不得进入、环绕或改变文字块的正常流排版。
- **图片区（ImageArea）**：区段中的不可分割布局块，可放置零到多张题目配图。图片区具有跨版本稳定 UUID，并以相对宽度的 `height_ratio` 表达高度。
- **题目配图（QuestionFigure）**：由题目拥有、具有稳定 UUID 的图片资产身份。它记录来源和裁剪结果，但不记录某个版本中的摆放位置。
- **配图摆放（FigurePlacement）**：某个题目版本中，一张题目配图在一个图片区内的位置与尺寸。`x`、`y`、`width`、`height` 均为相对于图片区的归一化坐标。

## Coordinates and assets

- **原始页图**：用户上传的完整页面图片。
- **题目区域图**：从原始页图裁出的、包含一道完整题目的区域。
- **来源素材（SourceAsset）**：共享的持久化字节记录。它不是题目或用户的所有权边界；访问授权必须通过 Question、Paper 等业务对象判断。
- **来源裁剪坐标（SourceCropCoordinates）**：题目配图在其来源素材中的归一化 `[x, y, width, height]`，每个值位于 `0..1`，并满足 `x + width <= 1`、`y + height <= 1`。它用于重建配图来源，不表达题内排版。
- **图片区布局坐标（ImageAreaLayoutCoordinates）**：配图相对于图片区的归一化 `x/y/width/height`。它只表达某个题目版本中的排版，不用于裁剪来源素材。

来源裁剪坐标和图片区布局坐标属于不同坐标空间，不得互换或复用。

## Paper snapshots

- **试卷题目（PaperItem）**：题目加入试卷时形成的冻结副本。后续 Question 或 QuestionRevision 变化不得改变它。
- **试卷区段快照（PaperItemSectionSnapshot）**：PaperItem 冻结的题干、答案、解析和图片区布局结构。
- **试卷配图快照（PaperItemFigureSnapshot）**：PaperItem 独立冻结的配图资产引用及必要来源元数据。渲染历史试卷不得回读当前 QuestionFigure 状态。
- **作答区（ResponseArea）**：试卷上供学生书写答案的留白区域。它不属于答案区段，也不存储标准答案内容。

## Compatibility language

- **兼容文本投影（LegacyTextProjection）**：从结构化区段按顺序拼接文字块得到的 `content`、`answer`、`analysis` 文本。文字块之间用空行连接；图片区不会向 Markdown 注入资源 ID、文件名或占位标记。
- **schema v1**：现有未版本化 revision JSON 和扁平 Question/PaperItem 字段的统称。
- **schema v2**：带 `schema_version: 2` 的三区段、有序内容块和多图布局快照。

旧字段继续作为兼容投影存在，直到单独的兼容清理工作明确移除。旧历史版本通过适配器读取；迁移不得批量改写全部历史版本或历史 PaperItem。
