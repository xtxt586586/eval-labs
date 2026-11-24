# Eval Labs 项目指南

## 项目概况

面向 RAG、AI Agent 和多轮对话应用的自托管评测工作台。后端为 FastAPI、SQLAlchemy、Pydantic，要求 Python 3.12+；前端为 React 18、TypeScript、Ant Design 5 和 Vite（Node.js 18+）。默认 SQLite，`DATABASE_URL` 可配置 PostgreSQL；真实 Judge 调用使用 OpenAI 兼容 API。

## 项目结构

- `backend/app/api/`：REST API 路由，包括评测、Endpoint、Agent 沙箱、Judge 校准和运行观测。
- `backend/app/core/`：评测引擎、trace 归一化、快照、数据库和任务队列。
- `backend/app/models/`、`schemas/`：SQLAlchemy 模型与 Pydantic API 类型。
- `backend/tests/`：后端回归测试。
- `frontend/src/pages/`：工作台和资源页面；`services/api.ts` 封装 API；`types/` 保存共享类型。
- `docs/`：使用、指标、Agent、存储和发布边界说明。

## 开发约定

### Python
- 使用类型注解和 PEP 8 风格；异步 I/O 使用 `async`/`await`。
- API 输入输出放在 `backend/app/schemas/`，路由放在 `backend/app/api/`。
- 保持 SQLite 与 SQLAlchemy 支持的数据库行为兼容；数据库 schema 变更需更新 runtime 升级逻辑及测试。目前尚未采用 Alembic。

### TypeScript
- 保持严格类型；使用函数组件和 Hooks。
- API 请求放在 `frontend/src/services/api.ts`，页面放在 `frontend/src/pages/`。
- 优先沿用现有 Ant Design 组件和项目样式。

## 常用开发命令

PowerShell：

```powershell
cd backend
..\.venv\Scripts\Activate.ps1
python run.py
```

```powershell
cd frontend
npm install
npm run dev
```

后端文档位于 `http://localhost:8000/docs`，前端默认位于 `http://localhost:5173`。后端测试使用 `python -m pytest tests/ -q`，前端检查使用 `npm run build`。

## 评测与运行事实

- Endpoint trace 在接入时归一化为 `otel-agent-trajectory/v1`；这不是 OTLP exporter。
- Agent 沙箱只回放声明式 JSON fixtures，不执行用户代码或发起外部网络请求。
- Judge 校准将人工标注分数与重复评分快照比较，提供 MAE 和分数方差；它不会自动设定发布阈值。
- 数据集、LLM 配置和指标有版本，评测任务保存内容快照及哈希。
- 任务队列使用 SQL 数据库状态、原子领取、worker 心跳租约、过期恢复和有限重试；worker 在线程池中运行于 API 进程，不是独立 broker/worker 集群。
- 运行观测 API 提供健康、队列/任务统计和任务 trace 元数据，不会向 OTLP Collector 导出 trace。

## 配置和安全

环境变量及默认值见 `backend/.env.example`。主要配置包括 `DATABASE_URL`、`UPLOAD_DIR`、`CORS_ORIGINS`、`SEED_ON_STARTUP`、`RUN_EVAL_ON_CREATE`、`EVAL_QUEUE_WORKERS`、`EVAL_TASK_LEASE_TIMEOUT_SECONDS` 和 `EVAL_MAX_TASK_ATTEMPTS`；Judge 配置还包括 `LLM_ENDPOINT`、`LLM_MODEL`、`LLM_API_KEY` 等。

不要提交 `.env`、数据库、上传数据或凭据。API 响应会脱敏 API key 和 endpoint authorization，但数据库静态值未加密。当前没有用户认证、RBAC 或审计日志；不得直接暴露给非可信网络。
