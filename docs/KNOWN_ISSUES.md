# KNOWN_ISSUES

## 1. 前端中文乱码

当前文档和部分前端显示曾出现中文乱码问题。下一阶段应优先处理编码与展示链路，避免继续扩大文案维护成本。

影响：

- 影响人工验收和后续维护判断。
- 可能掩盖真实交互文案问题。

## 2. Dashboard Draft 接入已确认但仍需收口

主链路已决策采用渐进式迁移。第十一轮补充确认，当前 `Dashboard.vue` 上传主路径已初步接入 Draft 流水线，并接受为新的前端主路径基线。

当前 `Dashboard.vue` 上传按钮实际调用 Draft 相关接口：

- `POST /api/v1/assets`
- `POST /api/v1/drafts`
- `POST /api/v1/drafts/{draft_id}/recognize`
- `POST /api/v1/drafts/{draft_id}/save-to-bank`

同时，`Dashboard.vue` 中仍保留 `runLegacyRecognition()` 对 `POST /api/v1/recognize` 的调用，但当前上传按钮未引用该函数。`POST /api/v1/recognize` 不删除、不重构，保留为 legacy / 兼容入口。

影响：

- Draft 前端接入尚未达到完整生产级完成。
- API smoke 文档已补充，Draft 后端异常契约已开始收口；仍需补 UI 状态和 legacy 清理。
- `saved_to_bank` 状态重复保存当前返回 `409`，尚未做成返回既有保存结果的幂等接口。
- `/api/v1/recognize` 仍需作为 legacy / 兼容入口保留。
- 不做 OCR/LLM provider 抽象、异步队列、批量 PDF、多页 draft 管理。

## 3. mock/legacy 文件需要清理

项目中仍存在历史 mock、legacy 或过渡文件。它们不一定阻断当前启动和验证，但会增加后续判断成本。

影响：

- 新开发容易误用历史入口。
- 清理应小步进行，避免演变成大重构。

## 4. 后端测试稳定性仍需持续关注

第七轮后端验证已通过：

- `python -m compileall app` 通过。
- `python -m unittest discover tests` 通过，`Ran 38 tests OK`。

但当前测试仍依赖已正确安装 `backend/requirements.txt` 的 Python 环境，后续仍需关注环境一致性和测试隔离。

影响：

- 裸 Python 环境或依赖不完整时会出现非业务失败。
- 下一阶段应优先提升测试稳定性，而不是扩大功能面。

## 5. 真实第三方失败场景尚未系统化在线验证

当前不能声称错误密钥、第三方超时、第三方限流、异常响应结构、网络抖动等场景都已逐项在线验证。

影响：

- 可以记录本地失败分支语义，但不能等同于真实第三方异常验收完成。
- 对外交付说明必须区分“主链路可验证”和“生产级异常覆盖”。

## 6. 当前状态不是生产可用

当前项目状态是“可启动、可验证、可继续开发”。不要把它表述为生产可用。

影响：

- 后续文档、验收、汇报需要保持该边界。
- 下一阶段不要新增规划之外的大模块，也不要做大重构。
