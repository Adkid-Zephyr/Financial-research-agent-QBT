# Docker Compose MVP 部署交接

## 本轮目标
- 基于当前 Phase 1 已完成项目，补齐单机 Docker Compose 部署方案。
- 保持 CLI、REST API、WebSocket、PostgreSQL 持久化能力可继续工作。
- 不做大重构，不扩展到 Phase 2，不引入 Redis/Celery。

## 本轮关键决策
- 部署拓扑采用 `app + postgres + nginx`。
- `app` 同时承载 FastAPI、WebSocket 和 CLI 执行环境，减少服务数量。
- 由于现有事件总线是进程内内存实现，`docker compose exec app python run.py ...` 无法把事件广播给已经运行中的 API 进程。
- 为解决这个部署态问题，新增同进程触发路由：
  - `POST /runs`
  - `POST /batches`
- 宿主机 cron 默认改为调用触发 API，而不是直接 `exec` 启新进程。
- CLI 不删除，继续保留给人工排障和手工执行。

## 已新增文件
- `Dockerfile`
- `docker-compose.yml`
- `.env.example`
- `deploy/app/start.sh`
- `deploy/cron/run_batch.sh`
- `deploy/nginx/default.conf`
- `deploy/verify_websocket.py`
- `DEPLOYMENT.md`
- `futures_research/api/static/index.html`
- `futures_research/api/static/styles.css`
- `futures_research/api/static/app.js`

## 已实现类名和公开方法签名

### API 触发层
- `futures_research.api.routes.runs.trigger_single_run(payload: RunTriggerRequest, request: Request) -> RunTriggerAccepted`
- `futures_research.api.routes.runs.trigger_batch_run(payload: BatchTriggerRequest, request: Request) -> BatchTriggerAccepted`

### App 装配
- `futures_research.api.app.create_app(repository: Optional[ReportRepository] = None, event_bus: Optional[EventBus] = None) -> FastAPI`
  - 现额外注入：
    - `app.state.run_single`
    - `app.state.run_batch`

## 关键 Pydantic 数据结构字段

### `RunTriggerRequest`
- `symbol`
- `target_date`

### `RunTriggerAccepted`
- `status`
- `requested_symbol`
- `target_date`

### `BatchTriggerRequest`
- `symbols`
- `all_varieties`
- `target_date`
- `concurrency`

### `BatchTriggerAccepted`
- `status`
- `requested_symbols`
- `target_date`
- `concurrency`

## 当前对外暴露的 API 路由
- `GET /`
- `GET /healthz`
- `GET /reports`
- `GET /reports/{run_id}`
- `POST /runs`
- `POST /batches`
- `WS /ws/events`

## 部署与运行说明
- 启动说明见根目录 `DEPLOYMENT.md`。
- 默认外部入口：
  - `http://127.0.0.1:8080`
  - `ws://127.0.0.1:8080/ws/events`
- 本地无 Docker 测试时，当前 `.env` 已切到 SQLite 文件库存储，并接入百炼 Anthropic 兼容端：
  - `ANTHROPIC_BASE_URL=https://coding.dashscope.aliyuncs.com/apps/anthropic`
  - `LLM_MODEL=kimi-k2.5`
- `deploy/cron/run_batch.sh` 已支持：
  - `--all-varieties`
  - `--symbol CF`
  - `--symbols CF,M`
  - `--target-date YYYY-MM-DD`
  - `--concurrency 2`

## 验收结果

### 已完成
- `2026-04-01` 执行 `DATABASE_URL='' .venv/bin/python -m unittest discover -s tests`
  - 18 个用例全部通过
- `2026-04-01` 执行 `DATABASE_URL='' .venv/bin/python run.py --symbol CF --target-date 2026-04-01`
  - 单品种 CLI 可用
- `2026-04-01` 执行 `DATABASE_URL='' .venv/bin/python run.py --symbols CF,M --target-date 2026-04-01 --concurrency 2`
  - 批量 CLI 可用
- `2026-04-01` 本地 `uvicorn` 验证
  - `GET /` 前端控制台可打开
  - `GET /healthz` 正常
  - `POST /runs` 返回 `202 accepted`
  - `POST /batches` 返回 `202 accepted`
  - `WS /ws/events?channel=run` 成功收到完整序列 `run_started -> step_started -> review_round_completed -> run_completed`
  - `WS /ws/events?channel=batch` 成功收到 `batch_started` / `batch_item_started`
- `2026-04-01` 百炼 Anthropic 兼容端最小调用探针
  - 返回 `pong`
- `2026-04-01` 执行 `docker-compose.yml` 结构检查
  - 成功解析到 `app`、`postgres`、`nginx` 三个服务

### 未完成 / 阻塞
- 当前环境没有 Docker：
  - `docker --version` -> `command not found`
  - `docker compose version` -> `command not found`
- 因此下面这些还没有真实完成：
  - `docker compose up --build -d`
  - PostgreSQL 容器态落库验收
  - Nginx 容器态反向代理验收
  - WebSocket 经 Nginx 的容器态验收

## 下一线程优先事项
1. 如果用户已安装 Docker，先执行真实容器验收：
   - `cp .env.example .env`
   - `docker compose up --build -d`
   - `curl http://127.0.0.1:8080/healthz`
   - `docker compose exec app python deploy/verify_websocket.py --url 'ws://nginx/ws/events?channel=run' --expect 1`
   - `curl -X POST http://127.0.0.1:8080/runs -H 'Content-Type: application/json' -d '{"symbol":"CF","target_date":"2026-04-01"}'`
   - 验证 `/reports` 与 PostgreSQL 落库
2. 如果用户要真实模型效果，再让用户提供 `ANTHROPIC_API_KEY`。
3. 如果继续生产化增强，优先做：
   - HTTPS / 域名
   - 简单鉴权
   - 监控与日志轮转
   - 备份与恢复脚本

## 新线程提示词
继续这个项目，先阅读 `/Users/ann/Documents/投研agent/memory/PROJECT_MEMORY.md` 和 `/Users/ann/Documents/投研agent/memory/DEPLOYMENT_MVP_HANDOFF.md`。当前代码已经补齐 Docker Compose MVP 部署文件、同进程触发 API、宿主机 cron 方案和本地联调验证；但这台机器还没有 Docker，所以尚未完成真实容器验收。请优先在 Docker 可用的前提下完成 `docker compose up`、PostgreSQL 落库、Nginx 代理、WebSocket 订阅和 API 触发的容器态实测，并把结果继续写回 memory。
