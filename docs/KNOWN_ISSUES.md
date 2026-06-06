# KNOWN_ISSUES

## 0. 组卷 MVP 后续能力仍未完成

第十七轮新增后端最小手动组卷能力。第十八轮新增前端组卷入口 MVP，支持从题库勾选题目、创建试卷、查看试卷列表和查看试卷详情。

当前明确暂不支持：

- 智能组卷算法。
- PDF / Word 导出。
- 拖拽排序。
- 分值编辑。
- 复杂试卷排版。
- 打印样式优化。
- 按知识点、难度或分值自动配比。

影响：

- 当前组卷前端只适合 MVP 验收，不应表述为完整组卷系统。
- 后续如果补导出、智能组卷、拖拽排序或分值编辑，应继续保持小步推进，并避免影响 Draft flow、legacy recognize 和题库保存逻辑。

## 1. LLM 难度评估是增强元数据，不是绝对标准

第十九轮新增 LLM 题型与五星难度元数据；性能收口后，Draft recognize 主链路只强制等待 OCR、`corrected_text` 和知识点标签，题型与难度在 save-to-bank 后通过后台任务补全到 Question。

当前限制：

- LLM 难度评分是估计值，不是严格教研标准或绝对难度。
- 历史题目可能没有 `question_type`、`difficulty_level`、`difficulty_label`、`difficulty_confidence` 或 `difficulty_reason`。
- 用户后续编辑题目内容后，题型和难度不会自动重新评估。
- 当前不支持按难度排序、按知识点排序、难度筛选或智能组卷。
- 后台任务依赖当前后端进程，服务重启可能丢失正在执行的元数据评估任务。
- 当前不做自动轮询或 WebSocket，前端需要刷新题库后看到后台更新结果。
- PaperItem 创建时如果 Question 元数据尚未 ready，题型和难度快照可能为空。
- `difficulty` 缺失或非法时，后端会保留 `corrected_text` 主流程并让难度字段为空或将元数据评估标记为失败。

影响：

- 前端和后续组卷逻辑必须把难度字段视为可空。
- 如后续要用于正式组卷策略，应增加人工校验、手动重新评估、版本化策略或真正任务队列。

## 2. 前端中文乱码

当前文档和部分前端显示曾出现中文乱码问题。下一阶段应优先处理编码与展示链路，避免继续扩大文案维护成本。

影响：

- 影响人工验收和后续维护判断。
- 可能掩盖真实交互文案问题。

## 3. Dashboard Draft 接入已阶段性收口但仍非生产完成态

主链路已决策采用渐进式迁移。第十一轮补充确认，当前 `Dashboard.vue` 上传主路径已初步接入 Draft 流水线，并接受为新的前端主路径基线。

当前 `Dashboard.vue` 上传按钮实际调用 Draft 相关接口：

- `POST /api/v1/assets`
- `POST /api/v1/drafts`
- `POST /api/v1/drafts/{draft_id}/recognize`
- `POST /api/v1/drafts/{draft_id}/save-to-bank`

同时，`Dashboard.vue` 中仍保留 `runLegacyRecognition()` 对 `POST /api/v1/recognize` 的调用，但当前上传按钮未引用该函数。`POST /api/v1/recognize` 不删除、不重构，保留为 legacy / 兼容入口。

已阶段性收口：

- API smoke 文档已补充。
- Draft 后端异常契约已阶段性收口：缺失 asset/draft 返回 `404`，非图片 asset recognize 返回 `400`，状态冲突和重复保存返回 `409`。
- Dashboard UI 状态已阶段性收口：上传、创建草稿、识别、保存有阶段提示，`partial_success` 以 warning 展示，常见错误码有可理解提示。
- legacy recognize 引用审计已完成，当前 Dashboard 主上传流程不调用 legacy 入口。
- 两个 smoke 文档已明确主次：`API_SMOKE_DRAFT_FLOW.md` 是当前推荐入口，`API_SMOKE_DRAFT_PIPELINE.md` 是脚本化 smoke 补充文档。

仍保留风险：

- Draft 前端接入尚未达到完整生产级完成。
- `saved_to_bank` 状态重复保存当前返回 `409`，尚未做成返回既有保存结果的幂等接口。
- `/api/v1/recognize` 仍需作为 legacy / 兼容入口保留。
- 两个 smoke 文档仍并存，后续修改 Draft 主链路或脚本参数时需要同步检查主文档和脚本文档，避免再次漂移。
- 不做 OCR/LLM provider 抽象、异步队列、批量 PDF、多页 draft 管理。

## 4. legacy recognize 仍需后续退场

第十五轮已完成 legacy recognize 引用审计与最小标注。当前 `runLegacyRecognition()` 和 `POST /api/v1/recognize` 仍保留为 legacy / 兼容入口，不被 Dashboard 主上传流程调用。

影响：

- 新开发仍可能误用 legacy 入口。
- 后续应在测试保护和兼容影响明确后，小步执行退场策略。
- 本轮不删除 legacy 入口，不改变后端业务行为。

## 5. mock/legacy 文件需要清理

项目中仍存在历史 mock、legacy 或过渡文件。它们不一定阻断当前启动和验证，但会增加后续判断成本。

影响：

- 新开发容易误用历史入口。
- 清理应小步进行，避免演变成大重构。

## 6. 后端测试稳定性仍需持续关注

第七轮后端验证已通过：

- `python -m compileall app` 通过。
- `python -m unittest discover tests` 通过，`Ran 38 tests OK`。

但当前测试仍依赖已正确安装 `backend/requirements.txt` 的 Python 环境，后续仍需关注环境一致性和测试隔离。

影响：

- 裸 Python 环境或依赖不完整时会出现非业务失败。
- 下一阶段应优先提升测试稳定性，而不是扩大功能面。

## 7. 真实第三方失败场景尚未系统化在线验证

当前不能声称错误密钥、第三方超时、第三方限流、异常响应结构、网络抖动等场景都已逐项在线验证。

影响：

- 可以记录本地失败分支语义，但不能等同于真实第三方异常验收完成。
- 对外交付说明必须区分“主链路可验证”和“生产级异常覆盖”。

## 8. 当前状态不是生产可用

当前项目状态是“可启动、可验证、可继续开发”。不要把它表述为生产可用。

影响：

- 后续文档、验收、汇报需要保持该边界。
- 下一阶段不要新增规划之外的大模块，也不要做大重构。
