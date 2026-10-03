# 单次视觉转录与可选元数据

2026-10-03，依据 Issue #25 的已批准决策，Draft 推荐默认改为 `OCR_PROVIDER=vision`：一次 `deepseek-flash` 图像生成同时读取印刷正文、知识点、题型和估计难度，并独立返回手写批注与不确定内容。两阶段 OCR 后文本清洗曾引入公式、选项和条件变异；视觉路径因此直接采用结构化正文，跳过文本清洗及保存后的后台元数据评估，保留人工确认入库边界。

正文必须非空且结构可验证，批注与疑点字段必须是独立数组。非法 JSON、重复字段、可检测的 LaTeX 转义损坏、空输出或截断均失败，用户只能手动重试；SDK 自动重试关闭，不进行百度兜底、模型切换或额外 JSON 修复。有效正文的可选元数据缺失或非法时，保留合法部分，其余留空并提示，仍允许保存；不追加模型补全。结构校验不能证明模型没有将批注误认成印刷正文，也不能证明数学保真，仍须对照原图验收。

## 记录与兼容边界

- 复用 `OCRRun` 记录视觉图像识别，`provider=vision`；`response_raw_json.raw_response_summary` 保存供应商、模型、prompt 版本、HTTP `request_id`、独立 completion `response_id`、usage、finish reason 和限量去秘密化原始输出。缺少 HTTP 请求编号时保留 null，不用 completion ID 代替；不保存输入 base64 或凭证。失败也写入 run。
- `Draft.current_content` 保存正文和分离字段，既有 Draft/Question nullable 元数据字段承载同次结果；保存后 `metadata_status=ready`，有缺失/非法元数据则为 `failed` 并记录 warning，表示辅助字段不完整而非入库失败。视觉路径没有 `LLMRun`；手动重试清除旧清洗关联和旧结果，但不删除历史 run。
- 同次元数据只适用于该次识别正文。视觉 Draft 人工编辑后，只要首尾 `strip()` 后正文不同，就清空当前知识点、题型和全部难度字段，并提示失效、需人工确认；仅首尾空白变化或无变化保留结果，不做语义等价判断。有效正文可带空元数据入库（`metadata_status=failed`、warning 记录在 `metadata_error`），不追加模型调用，也不因改回原文或保存而恢复旧元数据。原 OCRRun 转录、批注与关联继续保留。
- 配图检测与裁图继续保留，视觉输入使用完整题目区域图，绝不遮白题目配图，以免丢失图中文字。批量分题仍为每个 Draft 各一次生成。
- 显式 `OCR_PROVIDER=baidu` 及保留的旧 provider 继续走旧 OCR、文本清洗、保存后后台元数据流程；legacy `/api/v1/recognize` 不变。既有 Question、QuestionRevision 和 Paper 快照不改写，owner 隔离与现有 API 字段继续兼容，仅增加可选调试字段。
- 视觉配置独立于文本模型，复用现有 OpenAI SDK；无新依赖、服务、数据库模型或迁移。代码默认改变不代表已有部署已切换；切换既有环境和真实付费 smoke 需另行授权。本轮仅离线 mock 验证，不宣称识别质量已通过真实服务验收。

本 ADR 在视觉路径范围内替代 `docs/DECISIONS.md` 决策 25 的保存后补全及决策 27/30 的默认百度选择；这些历史决策继续描述旧路径，不修改历史记录。
