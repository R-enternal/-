# 仓脉智诊 Agent 模块（副本开发版）

> 本目录是 `D:\AI Program\仓脉智诊` 的完整副本，Agent 模块在此开发，**原项目文件未改动**。

## 功能

1. **智能查询**：对话式查询设备健康度、告警、工单、备件、忙闲（SSE 流式）
2. **AI 维保计划**：Plan-Execute-Replan 状态机，按健康度 + 告警 + 忙闲错峰生成维保方案，可落库、转工单
3. **智能调度**：按优先级 + 设备健康度对待派单工单生成派单建议，支持一键派单
4. **RAG 知识库**：上传维保手册/故障案例文档，自动切块向量化，对话中自动检索回答
5. **多传感器融合诊断**：振动+温度+电流联合判定故障模式（轴承磨损/电机过热/负载异常/复合故障）

## 技术栈（新增部分）

- LangChain Core + LangChain OpenAI + LangGraph（1.x 新版 API）+ LangChain Chroma
- SSE（sse-starlette）
- 对话模型：DeepSeek（deepseek-v4-flash）
- Embedding：智谱 GLM embedding-2（RAG 向量化）
- 向量库：Chroma（嵌入式持久化，无需 Docker）

## 快速开始

```bash
cd backend
alembic upgrade head          # 建 maintenance_busy_window / maintenance_plan 表（已执行）
python scripts/seed_agent_demo.py   # 初始化仓库忙闲时段（已执行）
python -m uvicorn app.main:app --host 0.0.0.0 --port 9901
```

前端：`cd frontend && npm run dev`（5173），浏览器打开后左侧导航进入「智能助手」。

或直接运行根目录 `start.bat`。

## 配置真实 LLM（可选）

编辑 `backend/.env`：

```ini
LLM_API_KEY=sk-xxx
LLM_BASE_URL=https://api.deepseek.com/v1
LLM_MODEL=deepseek-v4-flash

EMBEDDING_API_KEY=xxx
EMBEDDING_BASE_URL=https://open.bigmodel.cn/api/paas/v4/
EMBEDDING_MODEL=embedding-2
```

支持任意 OpenAI 兼容服务（DeepSeek / 智谱 / 通义 / OpenAI 等）。

## 知识库（RAG）

- 上传：知识库页面拖拽上传 `.md/.txt`，或调 `POST /api/kb/upload`；
- 灌入演示：`python scripts/seed_kb.py` 或调 `POST /api/kb/seed`（内置《设备维保手册.md》）；
- 检索：`GET /api/kb/search?q=...`；对话中问"电机过热怎么排查"会自动调用 `retrieve_knowledge` 工具；
- 向量持久化目录：`backend/vector_db/`（Chroma）。

## 验收

```bash
cd backend
ruff check app/ scripts/
mypy app/
python -m pytest
python scripts/verify_agent.py       # 工具/对话/建议/落库/转工单/调度
python scripts/verify_agent_sse.py   # SSE 流式（对话 + 维保计划）
python scripts/verify_rag.py         # RAG 知识问答 + 上传
python scripts/verify_llm_api.py     # 真实 LLM / Embedding 连通性
python scripts/verify_fusion.py      # 融合诊断（单测 + 端到端）
python scripts/verify_predictive.py  # 预测性告警（Holt 平滑）
```

## 代码结构

```
backend/app/
├── agent/
│   ├── llm.py              # LLM 工厂（真实模型 / 规则降级）
│   ├── chat_agent.py       # 智能查询 Agent（LangGraph ReAct）
│   └── aiops/              # 维保计划 Agent（Plan-Execute-Replan）
│       ├── state.py        #   状态定义
│       ├── planner.py      #   规划
│       ├── executor.py     #   执行（调工具）
│       ├── replanner.py    #   重规划/出报告
│       └── service.py      #   图编排（SSE 事件）
├── tools/agent_tools.py    # 业务工具（健康度/告警/工单/备件/设备/忙闲）
├── tools/knowledge_tool.py # 知识检索工具（RAG）
├── services/agent_service.py # 维保建议/落库/转工单/调度建议
├── services/kb_service.py  # 知识库服务（切块/向量化/检索）
├── models/agent.py         # MaintenanceBusyWindow / MaintenancePlan
├── models/kb.py            # KbDocument 文档记录
├── api/agent.py            # /api/agent/* 接口（SSE）
└── api/kb.py               # /api/kb/* 知识库接口
```

## 说明

- 数据库与主项目共用 `cangweiyun` 库，新增三张表（`maintenance_busy_window`、`maintenance_plan`、`kb_document`），未改动原表；
- 未配置 Key 时走内置规则降级模式（离线可演示）；已配置 DeepSeek + 智谱 Key 后自动使用真实模型；
- 忙闲时段演示数据：每仓库每天 3 个时段（含 06:00-08:00 很闲窗口，供错峰维保）。
