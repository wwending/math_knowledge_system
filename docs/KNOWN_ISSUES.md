# KNOWN_ISSUES

## 0. 组卷 MVP 后续能力未完成

第十七轮新增的是后端最小手动组卷能力，只覆盖登录用户基于自己题库题目创建、查看、列表查询试卷。

当前明确暂不支持：

- 智能组卷算法。
- PDF / Word 导出。
- 前端组卷页面。
- 拖拽排序。
- 按知识点、难度或分值自动配比。

影响：

- 当前 papers API 只能作为后端 MVP 能力验证。
- 后续如果接前端或导出，应继续保持小步推进，并避免影响 Draft flow、legacy recognize 和题库保存逻辑。

## 1. 前端中文乱码

当前文档和部分前端显示曾出现中文乱码问题。下一阶段应优先处理编码与展示链路，避免继续扩大文案维护成本。

影响：

- 影响人工验收和后续维护判断。
- 可能掩盖真实交互文案问题。

## 2. Dashboard Draft 接入已阶段性收口但仍非生产完成态

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

## 3. legacy recognize 仍需后续退场

第十五轮已完成 legacy recognize 引用审计与最小标注。当前 `runLegacyRecognition()` 和 `POST /api/v1/recognize` 仍保留为 legacy / 兼容入口，不被 Dashboard 主上传流程调用。

影响：

- 新开发仍可能误用 legacy 入口。
- 后续应在测试保护和兼容影响明确后，小步执行退场策略。
- 本轮不删除 legacy 入口，不改变后端业务行为。

## 4. mock/legacy 文件需要清理

项目中仍存在历史 mock、legacy 或过渡文件。它们不一定阻断当前启动和验证，但会增加后续判断成本。

影响：

- 新开发容易误用历史入口。
- 清理应小步进行，避免演变成大重构。

## 5. 后端测试稳定性仍需持续关注

第七轮后端验证已通过：

- `python -m compileall app` 通过。
- `python -m unittest discover tests` 通过，`Ran 38 tests OK`。

但当前测试仍依赖已正确安装 `backend/requirements.txt` 的 Python 环境，后续仍需关注环境一致性和测试隔离。

影响：

- 裸 Python 环境或依赖不完整时会出现非业务失败。
- 下一阶段应优先提升测试稳定性，而不是扩大功能面。

## 6. 真实第三方失败场景尚未系统化在线验证

当前不能声称错误密钥、第三方超时、第三方限流、异常响应结构、网络抖动等场景都已逐项在线验证。

影响：

- 可以记录本地失败分支语义，但不能等同于真实第三方异常验收完成。
- 对外交付说明必须区分“主链路可验证”和“生产级异常覆盖”。

## 7. 当前状态不是生产可用

当前项目状态是“可启动、可验证、可继续开发”。不要把它表述为生产可用。

影响：

- 后续文档、验收、汇报需要保持该边界。
- 下一阶段不要新增规划之外的大模块，也不要做大重构。
