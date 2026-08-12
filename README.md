# 仓维云 · 轻量化 AI 仓储设备智能维检平台

面向中小仓储企业的设备智能维检 SaaS：免布线磁吸传感器采集运行数据，轻量化 AI 智能体实现设备健康监测、故障预判、错峰维保，打通维保工单、备件库存、设备资产台账一体化管理。

## 技术栈

- **后端**：FastAPI + SQLAlchemy 2.0 + MySQL + Redis + APScheduler + scikit-learn
- **前端**：Vue3 + Vite + Element Plus + Pinia + ECharts
- **算法**：阈值层（连续 N 次超限防抖）+ 趋势层（滑动窗口斜率）+ 孤立森林异常检测 + 健康度评分（0-100）

## 环境要求

- Python ≥ 3.11（开发环境 3.12）
- Node.js ≥ 18（开发环境 22）
- MySQL 8（本地 3306，配置见 `backend/.env`）
- Redis（可选，预警去重等预留，未用不影响启动）

## 快速开始（10 分钟）

### 1. 准备数据库

```sql
CREATE DATABASE cangweiyun CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

### 2. 安装依赖

```bash
cd backend
pip install -r requirements.txt
cd ../frontend
npm install
```

### 3. 建表 + 初始化演示环境

```bash
cd backend
alembic upgrade head          # 建表（14 张业务表）
python scripts/seed_demo.py   # 一条命令：重置库 + 模板 + 账号 + 演示数据
```

`seed_demo.py` 会产出：1 个仓库、4 台设备（含传感器点位）、3 个备件（1 个低库存）、2 小时模拟数据、1 条告警、4 条健康度记录、1 条工单——五个页面都有数据。

### 4. 启动

Windows 直接双击 `start.bat`，或手动：

```bash
# 终端 1：后端
cd backend && python -m uvicorn app.main:app --host 0.0.0.0 --port 9901

# 终端 2：前端
cd frontend && npm run dev
```

- 前端：http://localhost:5173
- 后端 API 文档（Swagger）：http://localhost:9901/docs

## 演示账号

| 账号 | 密码 | 角色 |
|---|---|---|
| admin | admin123 | 管理员 |
| worker | worker123 | 维修工 |
| viewer | viewer123 | 观察者 |

## 认证开关

`backend/.env` 中 `AUTH_ENABLED`：

- `False`（默认）：开发联调期，所有接口免认证
- `True`：演示/生产前打开，除 `/health`、`/api/auth/login`、文档外全部需要 Bearer token

## 演示流程解说词（约 5 分钟）

1. **登录**：打开 http://localhost:5173，用 `admin/admin123` 登录
2. **监测看板**：展示 4 台设备的健康度卡片——其中 1 台因告警呈 ABNORMAL（红色）；下拉切换设备看健康度趋势曲线
3. **设备管理**：查看设备点位及阈值（振动/温度/电流），可编辑阈值（演示"配置灵活"）
4. **告警中心**：看到待处理告警（温度超限），点击"确认"→ 再点"转工单"
5. **工单管理**：新转出的工单（来源=ALERT）→ "派单"（选 worker）→ "开始" → "提交验收" → "完成"
6. **备件库存**：勾选"仅看低库存"，看到轴承库存 3 < 安全 10（红色）；"出库"验证库存不足被拒
7. **收尾**：回到监测看板，告警处理后设备健康度回升（后端定时任务每 5 分钟自动重算）

## 目录结构

```text
仓维云/
├── backend/
│   ├── app/
│   │   ├── api/          # 路由（只做校验和包装）
│   │   ├── services/     # 业务逻辑
│   │   ├── core/         # 算法引擎（阈值/趋势/孤立森林/健康度/安全）
│   │   ├── models/       # ORM 模型（14 张表）
│   │   └── tasks/        # APScheduler 定时任务
│   ├── alembic/          # 数据库迁移
│   └── scripts/          # 初始化/测试/验收脚本
├── frontend/             # Vue3 前端
├── start.bat             # Windows 一键启动
└── README.md
```

## 测试

```bash
cd backend
pytest                # 21 个测试全绿（纯函数单测 + 数据库集成测试）
ruff check app scripts
mypy app
```

定时任务（采集 60s / 判定 3min / 健康度 5min）随后端启动自动运行，模拟真实传感器持续采集。
