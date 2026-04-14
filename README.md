# Financial Research Agent

一个面向商品期货场景的投研自动化项目，目标是把"数据收集 -> 多 Agent 分析 -> 研报生成 -> 质检复核 -> API / Web 控制台交付"串成一条可运行、可验收、可部署的链路。

项目当前由两个彼此协作、又相对独立的部分组成：

- `futures_research/`
  主投研工作流，负责触发、分析、写作、事件流和报告存储
- `report_review_agent/`
  研报复核子项目，负责对 AI 生成的报告做规则化评分、问题定位和改写建议

## Why This Exists

传统投研流程里，很多时间花在重复整理信息、统一格式、追踪事件和做首轮质量检查上。这个仓库想解决的不是"生成一篇文本"这么简单，而是把投研产出包装成一个更接近生产可用的系统：

- 能手动触发单品种或批量任务
- 能通过 WebSocket 实时观察运行事件
- 能把结果落盘或落库，方便追踪与复盘
- 能通过前端控制台完成本地和部署后的验收
- 能在报告生成后再走一轮结构化 review

## Project Shape

```text
.
├── futures_research/          # 主投研工作流与 API
├── report_review_agent/       # 研报复核子项目
├── deploy/                    # Docker / Nginx / cron 部署脚本
├── templates/                 # 请求模板与业务说明
├── varieties/                 # 品种配置
├── tests/                     # 主项目测试
├── memory/                    # 阶段交接与项目记忆
├── outputs/                   # 主项目产物目录（默认仅保留 .gitkeep）
└── logs/                      # 运行日志目录
```

## Core Capabilities

### 1. Futures Research Workflow

- FastAPI 接口，支持健康检查、单次运行和批量运行
- WebSocket 事件流，便于前端实时观察任务状态
- 多 Agent 分工，包括 analyzer / writer / reviewer / aggregator
- CLI 触发方式，适合本地调试与批量执行
- PostgreSQL 存储接口与本地文件产物归档

### 2. Research Review Agent

- 支持上传 `.md`、`.txt` 和文本型 `.pdf`
- 使用确定性 rubric 做质量评分
- 输出问题列表、改进建议和结构化评审结果
- 可选接入兼容 Anthropic 的模型增强文案建议
- 导出 Markdown、PDF、JSON 三类评审产物

### 3. Deployment and Acceptance

- Docker Compose MVP 部署链路
- Nginx 统一入口
- 宿主机 cron 最小化调度方案
- Web 控制台用于健康检查、触发任务、查看事件和查询报告

## Quick Start

### Local API

```bash
cd /Users/ann/Documents/投研agent
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn futures_research.api.app:app --reload
```

然后打开：

- `http://127.0.0.1:8000/docs`
- `http://127.0.0.1:8000/`
- `http://127.0.0.1:8000/admin`

当前 `/` 是 C 端投研入口，保留一句话研究、报告展示、数据来源与追问；`/admin` 是原测试/验收工作台，保留健康检查、单品种/批量触发、WebSocket 事件、报告查询和删除。

### Review Agent

```bash
cd /Users/ann/Documents/投研agent
source .venv/bin/activate
python report_review_agent/run.py
```

然后打开：

- `http://127.0.0.1:8020`

### Docker Compose

```bash
cd /Users/ann/Documents/投研agent
cp .env.example .env
docker compose up --build -d
```

默认入口：

- Frontend: `http://127.0.0.1:8080/`
- Health: `http://127.0.0.1:8080/healthz`
- Docs: `http://127.0.0.1:8080/docs`
- WebSocket: `ws://127.0.0.1:8080/ws/events`

## Suggested Flow

1. 先通过前端控制台做健康检查。
2. 连接 WebSocket 观察事件流。
3. 触发单品种或批量运行。
4. 检查 `outputs/` 或 `/reports` 返回结果。
5. 需要质量复核时，把报告送进 `report_review_agent/`。

## Environment Notes

项目支持无模型密钥的流程验证模式；未配置真实模型时，可回退到 mock 流程，方便先联通整条链路。

常见环境变量包括：

- `ANTHROPIC_API_KEY`
- `ANTHROPIC_BASE_URL`
- `LLM_MODEL`
- `REVIEW_AGENT_API_KEY`
- `REVIEW_AGENT_BASE_URL`
- `REVIEW_AGENT_MODEL`
- `ENABLE_YAHOO_MARKET_SOURCE`
- `ENABLE_AKSHARE_COMMODITY_SOURCE`

默认运行只启用 CTP 快照主链路。需要让报告使用已配置的 yfinance 外盘/宏观与 AkShare 商品结构化数据时，显式打开：

```bash
ENABLE_YAHOO_MARKET_SOURCE=true ENABLE_AKSHARE_COMMODITY_SOURCE=true \
uvicorn futures_research.api.app:app --host 127.0.0.1 --port 8025
```

## Current Repo Policy

为了把仓库保持成一个适合继续迭代的基线，以下内容默认不提交：

- 本地密钥文件，如 `.env`
- 虚拟环境目录，如 `.venv/`
- 本地数据库文件
- 运行生成的 `outputs/` 产物

## Roadmap Direction

这个仓库接下来很适合继续往几个方向演进：

- 更真实的数据源接入
- 更稳定的批处理与任务编排
- 更细粒度的报告评分维度
- 更完整的前端展示与回放能力
- 更规范的 GitHub 协作与 CI 流程

## Background

这是一个带有明显工程化倾向的投研 Agent 原型：不是只验证某个 prompt，而是在验证一整套“可持续跑起来”的研究生产链路。它既能当实验台，也能逐步打磨成一个更正式的内部研究系统。
