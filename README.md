# Math Knowledge System

## 2026-03-19 交接结论

当前仓库已经完成本轮交付所需的兼容修复和链路收口，重点是：

- 配置已收敛到 `backend/app/core/config.py`，后端启动与静态目录解析不再依赖运行时 `cwd`
- `Question` 旧契约已做兼容修复，老库缺少 `content / knowledge_tags / origin_image` 列时可在启动阶段补齐
- 前端已改为真实 JWT 登录，不再使用假 token
- 图片地址已统一为后端返回 `image_url`，前端兼容读取 `image_url` 和旧字段 `origin_image`
- OCR / LLM 的主要失败路径已做最小可用修复，`OCR 全失败` 与 `OCR 成功但 LLM 失败` 已明确区分

当前可以客观表述为：

- 可本地启动
- 可用真实 JWT 登录
- 正向链路已人工浏览器验收通过
- 已确认真实百度 OCR 能返回
- 已确认真实 LLM 能返回
- 尚未系统完成真实第三方失败场景的在线烟雾测试

不建议表述为：

- 第三方异常场景已全面验证
- 已具备正式上线级别的部署一致性验证
- 已具备正式迁移体系

## 启动方式

### 后端

1. 在 `backend/.env` 中准备最小配置：

```env
SECRET_KEY=请替换为真实密钥
BAIDU_API_KEY=你的百度 OCR Key
BAIDU_SECRET_KEY=你的百度 OCR Secret
DEEPSEEK_API_KEY=你的 LLM Key
```

可选项：

- `DATABASE_URL`，默认是相对 `backend` 目录解析的 `sqlite:///./math_knowledge.db`
- `CORS_ALLOW_ORIGINS`
- `STATIC_URL_PREFIX`
- `STATIC_DIR`
- `UPLOAD_DIR`
- `PDF_TEMP_DIR`
- `DEEPSEEK_BASE_URL`
- `DEEPSEEK_MODEL`

2. 安装依赖并启动：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r backend\requirements.txt
uvicorn --app-dir backend app.main:app --reload
```

说明：

- 推荐从仓库根目录启动，当前配置已按仓库路径解析，不要求先 `cd backend`
- 启动时会自动创建静态目录，并在 `AUTO_CREATE_TABLES=True` 时自动建表
- 启动时会执行 `Question` 旧契约兼容补列

### 前端

```powershell
cd frontend
npm install
npm run dev
```

可选环境变量：

```env
VITE_API_BASE_URL=http://127.0.0.1:8000
VITE_API_V1_PREFIX=/api/v1
VITE_STATIC_URL_PREFIX=/static
```

默认前提：

- 前端默认请求 `http://127.0.0.1:8000`
- 登录接口使用 `POST /api/v1/auth/token`
- 路由鉴权会调用 `GET /api/v1/auth/me` 校验已存 token

## 本轮主变更

### 1. 配置收敛与 `cwd` 依赖消除

- 路径解析统一走 `settings`
- `STATIC_DIR / UPLOAD_DIR / PDF_TEMP_DIR / DATABASE_URL` 均按后端目录解析
- 静态目录挂载与运行时目录创建已收敛到应用启动阶段
- 从仓库根目录执行 `uvicorn --app-dir backend app.main:app --reload` 已成为推荐方式

### 2. `Question` 旧契约修复

- 启动时会检查 `questions` 表
- 若老库缺少 `content / knowledge_tags / origin_image` 列，会补齐最小兼容列
- 当前做法是兼容修复，不是正式迁移体系

### 3. 前端真实 JWT 登录接入

- 登录页改为调用真实 `/api/v1/auth/token`
- token 统一保存在前端鉴权工具中
- axios 请求拦截器自动附带 `Bearer token`
- 路由守卫会用 `/api/v1/auth/me` 验证本地会话
- `401` 会统一清理会话并跳回登录页

### 4. 图片 URL 统一

- 后端列表、详情、历史、识别结果统一返回 `image_url`
- 前端通过统一方法解析图片地址
- 兼容读取旧字段 `origin_image`

### 5. 失败路径处理修复

- OCR 全失败：稳定返回失败，不落库
- OCR 成功但 LLM 失败：返回 `partial_success`，保留 OCR 原文并允许落库
- 登录失败、缺 token、无效 token、过期 token 均有明确提示
- 图片资源缺失时，前端展示占位，不直接暴露 broken image

## 当前验证边界

### 已验证：真实人工浏览器 + 真实第三方成功链路

- 已完成今天的人工浏览器验收
- 已确认真实 JWT 登录可用
- 已确认上传图片后百度 OCR 真能返回
- 已确认 OCR 成功后 LLM 真能返回
- 已确认正向结果可回到页面展示链路

当前正向链路可描述为：

`登录 -> 上传图片 -> OCR 返回 -> LLM 返回 -> 结果展示 -> 历史/题库可查看`

### 已验证：stub 条件下的失败路径

- 仓库已补充 `backend/tests/test_failure_paths.py`
- 这组验证覆盖的是接口稳定性与返回语义
- 其中 OCR / LLM 异常、无效返回、部分成功等场景属于 `patch / monkeypatch` 条件下验证
- 这部分不能替代真实第三方在线异常验证

### 未系统验证

- 真实第三方失败场景的在线烟雾测试还没有系统跑完
- 尚未形成“断网 / 错密钥 / 三方限流 / 三方异常结构”全套线上验收记录
- 尚未验证多部署环境下静态路径、反向代理、CORS 与数据库路径差异

## 已知限制

- 当前没有正式迁移体系，`Question` 旧契约兼容依赖启动时补列
- 静态资源策略目前是“后端统一给 URL，前端展示层兜底”，不会自动修复丢失文件
- 真实第三方失败场景仍是当前最大未闭环项
- 当前登录态只有 access token，没有 refresh token 体系
- 这轮目标是交付可提交、可交接版本，不是继续推进新模型体系或重做数据结构

## 交付状态

当前项目已经达到：

- 可提交
- 可交接
- 可继续由接手者在本地复现主链路
- 可继续补做真实第三方失败场景烟雾测试

当前项目尚未达到：

- 真实第三方异常场景已系统验收
- 多环境部署差异已完全收口
- 正式迁移治理已补齐
