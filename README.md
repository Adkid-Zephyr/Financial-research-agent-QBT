# FINANCIAL RESEARCH AGENT

<div align="center">

**A Multi-Agent Pipeline for Automated Futures Research & Report Review**

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Python](https://img.shields.io/badge/Python-3.11+-green.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-teal.svg)](https://fastapi.tiangolo.com/)
[![Stars](https://img.shields.io/github/stars/Adkid-Zephyr/Financial-research-agent-QBT?style=social)](https://github.com/Adkid-Zephyr/Financial-research-agent-QBT)

[English](#) | [中文](./README_CN.md) | [日本語](./README_JP.md)

---

*Building an end-to-end research automation system for commodity futures — from data ingestion to structured reports with quality assurance.*

</div>

---

## 🚀 THE STORY

> **Why I'm Building This In Public**

In traditional quantitative research workflows, analysts spend 60-70% of their time on repetitive tasks: collecting data, formatting reports, tracking events, and performing initial quality checks. This project started as an experiment to answer a simple question:

**Can we build a system that handles the "pipeline" work, so researchers can focus on what matters — analysis and decision-making?**

What began as a proof-of-concept has evolved into a full-stack research automation system with:
- Multi-agent orchestration (LangGraph)
- Real-time WebSocket event streaming
- Production-ready FastAPI backend
- Docker Compose deployment
- Quality review with structured rubrics

This is a **personal portfolio project** developed during my employment at **AnnPoint (广州安点科技)**. The company graciously granted me full rights to release this as an open-source project, while keeping proprietary data sources private.

---

## ✨ KEY FEATURES

| Feature | Description |
|---------|-------------|
| 🔀 **Multi-Agent Pipeline** | Orchestrated workflow: Aggregator → Analyzer → Writer → Reviewer |
| 📊 **Multi-Source Data Fusion** | CTP snapshots, Yahoo Finance, AkShare commodity data |
| 🔄 **Review Loop** | Up to 2 rounds of quality review with structured rubrics |
| 🌐 **FastAPI + WebSocket** | Real-time event streaming for task monitoring |
| 📦 **PostgreSQL Storage** | Persistent report archive with query API |
| 🐳 **Docker Compose** | One-command deployment: app + postgres + nginx |
| 🖥️ **Web Console** | Health check, task trigger, event stream, report viewer |
| 📝 **Report Review Agent** | Standalone review tool with Markdown/PDF/JSON export |

---

## 🏗️ ARCHITECTURE

```
┌─────────────────────────────────────────────────────────────────┐
│                        FastAPI Backend                           │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────────────────┐ │
│  │ /runs   │  │/batches │  │/reports │  │ WebSocket /ws/events│ │
│  └─────────┘  └─────────┘  └─────────┘  └─────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                     LangGraph Workflow                           │
│                                                                  │
│   ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐  │
│   │Aggregate │───▶│ Analyzer │───▶│  Writer  │───▶│ Reviewer │  │
│   └──────────┘    └──────────┘    └──────────┘    └──────────┘  │
│        │              │               │               │         │
│        ▼              ▼               ▼               ▼         │
│   ┌──────────────────────────────────────────────────────────┐  │
│   │              Data Source Registry                         │  │
│   │   CTP Snapshot │ Yahoo Finance │ AkShare │ Mock (dev)    │  │
│   └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Storage Layer                               │
│          PostgreSQL (production) / SQLite (local dev)           │
└─────────────────────────────────────────────────────────────────┘
```

---

## 📁 PROJECT STRUCTURE

```
.
├── futures_research/          # Main workflow & API
│   ├── api/                   # FastAPI routes & static frontend
│   ├── agents/                # LangGraph nodes
│   ├── data_sources/          # CTP, Yahoo, AkShare adapters
│   ├── storage/               # PostgreSQL repository
│   └── events/                # WebSocket event bus
├── report_review_agent/       # Standalone review tool
├── deploy/                    # Docker, Nginx, cron scripts
├── varieties/                 # Commodity YAML configs
├── tests/                     # 40+ unit tests
└── memory/                    # Development handoff docs
```

---

## ⚡ QUICKSTART

### Prerequisites
- Python 3.11+
- Docker & Docker Compose (for deployment)

### Local Development

```bash
# Clone the repository
git clone https://github.com/Adkid-Zephyr/Financial-research-agent-QBT.git
cd Financial-research-agent-QBT

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Start the API server
uvicorn futures_research.api.app:app --reload --port 8025
```

Then open:
- 🖥️ **Frontend**: http://127.0.0.1:8025/
- 🔧 **Admin Console**: http://127.0.0.1:8025/admin
- 📖 **API Docs**: http://127.0.0.1:8025/docs
- 🔌 **WebSocket**: ws://127.0.0.1:8025/ws/events

### Docker Deployment

```bash
# Copy environment template
cp .env.example .env

# Configure your settings (optional: add ANTHROPIC_API_KEY for LLM mode)
# Edit .env with your preferred editor

# Launch with Docker Compose
docker compose up --build -d

# Check health
curl http://127.0.0.1:8080/healthz
```

Default endpoints:
| Service | URL |
|---------|-----|
| Frontend | http://127.0.0.1:8080/ |
| Health Check | http://127.0.0.1:8080/healthz |
| API Docs | http://127.0.0.1:8080/docs |
| WebSocket | ws://127.0.0.1:8080/ws/events |

---

## 🔧 CONFIGURATION

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `ANTHROPIC_API_KEY` | LLM API key (optional) | - |
| `ANTHROPIC_BASE_URL` | LLM endpoint URL | - |
| `LLM_MODEL` | Model identifier | `kimi-k2.5` |
| `DATABASE_URL` | PostgreSQL DSN (optional) | SQLite fallback |
| `ANALYSIS_RENDER_MODE` | `deterministic` / `hybrid` / `llm` | `hybrid` |
| `REPORT_RENDER_MODE` | `deterministic` / `hybrid` / `llm` | `hybrid` |
| `ENABLE_YAHOO_MARKET_SOURCE` | Enable Yahoo Finance data | `false` |
| `ENABLE_AKSHARE_COMMODITY_SOURCE` | Enable AkShare data | `false` |

### Running with External Data Sources

```bash
ENABLE_YAHOO_MARKET_SOURCE=true \
ENABLE_AKSHARE_COMMODITY_SOURCE=true \
uvicorn futures_research.api.app:app --port 8025
```

---

## 📈 ROADMAP

> **Building in Public — Here's where we're headed**

### Phase 2 (Planned)
- [ ] More data source integrations (Wind, Bloomberg API)
- [ ] Advanced scheduling with task orchestration
- [ ] Fine-grained report scoring dimensions
- [ ] Enhanced frontend with historical playback
- [ ] Multi-user support with authentication
- [ ] GitHub Actions CI/CD pipeline

### Current Status
- ✅ Phase 1 Complete: Full workflow, API, WebSocket, Storage
- ✅ Docker Compose MVP deployment
- ✅ Multi-source data fusion (CTP + Yahoo + AkShare)
- ✅ Quality review loop with structured rubrics
- ✅ Web console for monitoring and control

---

## 🧪 TESTING

```bash
# Run all tests
python -m unittest discover -s tests

# Run specific modules
python -m unittest tests.test_workflow tests.test_api

# With coverage (optional)
pip install coverage
coverage run -m unittest discover -s tests
coverage report
```

---

## 📜 LICENSE & ATTRIBUTION

```
Copyright 2026 FENGSHUO LIU (刘丰硕)

Licensed under the Apache License, Version 2.0
```

This project was developed during employment at **AnnPoint 广州安点科技**. The company has granted full rights to the author for this personal open-source project.

> ⚠️ **Note**: Tick-level data sources provided by AnnPoint for testing remain proprietary and are not included. Users may integrate their own data sources for testing and evaluation.

### Author
**FENGSHUO LIU** ([@Adkid-Zephyr](https://github.com/Adkid-Zephyr))

### Acknowledgments
- **Kris77z** ([@Kris77z](https://github.com/Kris77z)) — CI/CD pipeline setup and deployment support
- **AnnPoint 广州安点科技** — Testing infrastructure and data source support

---

## 🤝 CONTRIBUTING

This is a personal portfolio project, but I welcome:
- 🐛 Bug reports and issue discussions
- 💡 Feature suggestions and roadmap feedback
- 📖 Documentation improvements
- 🔀 Pull requests for bug fixes

Feel free to open an issue or start a discussion!

---

<div align="center">

**Built with ❤️ by a quant-turned-developer who believes research automation should be open and accessible.**

[⬆ Back to Top](#financial-research-agent)

</div>