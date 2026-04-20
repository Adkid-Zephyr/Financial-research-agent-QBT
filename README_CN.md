# 金融研究智能体

<div align="center">

**面向商品期货的多智能体研报自动化流水线**

[![许可证](https://img.shields.io/badge/许可证-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Python](https://img.shields.io/badge/Python-3.11+-green.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-teal.svg)](https://fastapi.tiangolo.com/)
[![Stars](https://img.shields.io/github/stars/Adkid-Zephyr/Financial-research-agent-QBT?style=social)](https://github.com/Adkid-Zephyr/Financial-research-agent-QBT)

[English](./README.md) | 中文 | [日本語](./README_JP.md)

---

*构建端到端研究自动化系统——从数据采集到结构化研报与质量复核*

</div>

---

## 🚀 项目故事

> **为什么我选择公开构建这个项目**

在传统的量化研究流程中，分析师需要花费 60-70% 的时间处理重复性任务：收集数据、格式化报告、追踪事件、执行首轮质量检查。这个项目始于一个简单的实验问题：

**能否构建一个系统来处理这些"流水线"工作，让研究员专注于真正重要的——分析与决策？**

从最初的验证概念，逐步演化为一个完整的研究自动化系统：
- 多智能体编排（LangGraph）
- 实时 WebSocket 事件流
- 生产级 FastAPI 后端
- Docker Compose 一键部署
- 结构化评分质量复核

这是我在 **安点科技（AnnPoint）** 工作期间开发的**个人作品集项目**。公司慷慨地授予我完整权利，将其作为开源项目发布，同时保持专有数据源私有。

---

## ✨ 核心特性

| 特性 | 描述 |
|------|------|
| 🔀 **多智能体流水线** | 编排式工作流：聚合器 → 分析器 → 撰写器 → 复核器 |
| 📊 **多源数据融合** | CTP快照、Yahoo Finance、AkShare 商品数据 |
| 🔄 **审核循环** | 最多2轮结构化评分质量复核 |
| 🌐 **FastAPI + WebSocket** | 实时事件流，任务状态监控 |
| 📦 **PostgreSQL 存储** | 持久化研报存档，支持查询API |
| 🐳 **Docker Compose** | 一键部署：app + postgres + nginx |
| 🖥️ **Web 控制台** | 健康检查、任务触发、事件流、报告浏览 |
| 📝 **研报复核工具** | 独立评审工具，支持 Markdown/PDF/JSON 导出 |

---

## 🏗️ 系统架构

```
┌─────────────────────────────────────────────────────────────────┐
│                        FastAPI 后端                              │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────────────────┐ │
│  │ /runs   │  │/batches │  │/reports │  │ WebSocket /ws/events│ │
│  └─────────┘  └─────────┘  └─────────┘  └─────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                     LangGraph 工作流                             │
│                                                                  │
│   ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐  │
│   │  聚合器  │───▶│  分析器  │───▶│  撰写器  │───▶│  复核器  │  │
│   └──────────┘    └──────────┘    └──────────┘    └──────────┘  │
│        │              │               │               │         │
│        ▼              ▼               ▼               ▼         │
│   ┌──────────────────────────────────────────────────────────┐  │
│   │              数据源注册中心                               │  │
│   │   CTP快照 │ Yahoo Finance │ AkShare │ Mock（开发调试）   │  │
│   └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      存储层                                      │
│          PostgreSQL（生产环境） / SQLite（本地开发）             │
└─────────────────────────────────────────────────────────────────┘
```

---

## 📁 项目结构

```
.
├── futures_research/          # 主工作流 & API
│   ├── api/                   # FastAPI 路由 & 静态前端
│   ├── agents/                # LangGraph 节点
│   ├── data_sources/          # CTP、Yahoo、AkShare 适配器
│   ├── storage/               # PostgreSQL 仓储
│   └── events/                # WebSocket 事件总线
├── report_review_agent/       # 独立评审工具
├── deploy/                    # Docker、Nginx、cron 脚本
├── varieties/                 # 品种 YAML 配置
├── tests/                     # 40+ 单元测试
└── memory/                    # 开发交接文档
```

---

## ⚡ 快速开始

### 前置要求
- Python 3.11+
- Docker & Docker Compose（用于部署）

### 本地开发

```bash
# 克隆仓库
git clone https://github.com/Adkid-Zephyr/Financial-research-agent-QBT.git
cd Financial-research-agent-QBT

# 创建虚拟环境
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt

# 启动 API 服务
uvicorn futures_research.api.app:app --reload --port 8025
```

打开以下地址：
- 🖥️ **前端**: http://127.0.0.1:8025/
- 🔧 **管理控制台**: http://127.0.0.1:8025/admin
- 📖 **API 文档**: http://127.0.0.1:8025/docs
- 🔌 **WebSocket**: ws://127.0.0.1:8025/ws/events

### Docker 部署

```bash
# 复制环境模板
cp .env.example .env

# 配置设置（可选：添加 ANTHROPIC_API_KEY 启用 LLM 模式）
# 使用编辑器修改 .env

# Docker Compose 启动
docker compose up --build -d

# 检查健康状态
curl http://127.0.0.1:8080/healthz
```

默认端点：
| 服务 | URL |
|------|-----|
| 前端 | http://127.0.0.1:8080/ |
| 健康检查 | http://127.0.0.1:8080/healthz |
| API 文档 | http://127.0.0.1:8080/docs |
| WebSocket | ws://127.0.0.1:8080/ws/events |

---

## 🔧 配置说明

### 环境变量

| 变量 | 描述 | 默认值 |
|------|------|--------|
| `ANTHROPIC_API_KEY` | LLM API 密钥（可选） | - |
| `ANTHROPIC_BASE_URL` | LLM 端点 URL | - |
| `LLM_MODEL` | 模型标识 | `kimi-k2.5` |
| `DATABASE_URL` | PostgreSQL DSN（可选） | SQLite 回退 |
| `ANALYSIS_RENDER_MODE` | `deterministic` / `hybrid` / `llm` | `hybrid` |
| `REPORT_RENDER_MODE` | `deterministic` / `hybrid` / `llm` | `hybrid` |
| `ENABLE_YAHOO_MARKET_SOURCE` | 启用 Yahoo Finance 数据 | `false` |
| `ENABLE_AKSHARE_COMMODITY_SOURCE` | 启用 AkShare 数据 | `false` |

### 启用外部数据源

```bash
ENABLE_YAHOO_MARKET_SOURCE=true \
ENABLE_AKSHARE_COMMODITY_SOURCE=true \
uvicorn futures_research.api.app:app --port 8025
```

---

## 📈 开发路线

> **公开构建——这是我们的方向**

### Phase 2（规划中）
- [ ] 更多数据源接入（Wind、Bloomberg API）
- [ ] 高级调度与任务编排
- [ ] 更精细的报告评分维度
- [ ] 前端历史回放能力增强
- [ ] 多用户支持与认证
- [ ] GitHub Actions CI/CD 流水线

### 当前状态
- ✅ Phase 1 完成：完整工作流、API、WebSocket、存储
- ✅ Docker Compose MVP 部署
- ✅ 多源数据融合（CTP + Yahoo + AkShare）
- ✅ 结构化评分审核循环
- ✅ Web 监控控制台

---

## 🧪 测试

```bash
# 运行全部测试
python -m unittest discover -s tests

# 运行特定模块
python -m unittest tests.test_workflow tests.test_api

# 覆盖率报告（可选）
pip install coverage
coverage run -m unittest discover -s tests
coverage report
```

---

## 📜 许可证与归属

```
Copyright 2026 FENGSHUO LIU (刘丰硕)

Licensed under the Apache License, Version 2.0
```

本项目在 **安点科技（AnnPoint 广州安点科技）** 工作期间开发。公司已授予作者完整权利，作为个人开源项目发布。

> ⚠️ **注意**：安点科技提供的 tick 级数据源为专有资产，未包含在本项目中。用户可自行接入其他数据源进行测试评估。

### 作者
**刘丰硕 FENGSHUO LIU** ([@Adkid-Zephyr](https://github.com/Adkid-Zephyr))

### 致谢
- **Kris77z** ([@Kris77z](https://github.com/Kris77z)) — CI/CD 流水线搭建与部署支持
- **安点科技 AnnPoint 广州安点科技** — 测试基础设施与数据源支持

---

## 🤝 参与贡献

这是个人作品集项目，但欢迎：
- 🐛 Bug 报告与问题讨论
- 💡 功能建议与路线反馈
- 📖 文档改进
- 🔀 Bug 修复的 Pull Request

欢迎开 Issue 或发起 Discussion！

---

<div align="center">

**由一位相信研究自动化应当开放可触的量化研究员-turned-developer 构建 ❤️**

[⬆ 返回顶部](#金融研究智能体)

</div>