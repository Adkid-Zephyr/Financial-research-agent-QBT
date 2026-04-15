# Docker Compose MVP 部署说明

本部署方案面向 Phase 1 的单机 MVP，目标是优先保证以下能力可用：

- FastAPI REST API
- WebSocket 实时事件订阅
- PostgreSQL 持久化
- 单品种 CLI 触发
- 批量 CLI 触发
- 宿主机 cron 定时触发

当前方案不引入 Redis、Celery、消息队列或额外鉴权层，也不扩展到 Phase 2。

补充说明：

- CLI 仍然保留，适合手工执行与排障
- 为了让 WebSocket 订阅在部署态真正收到事件，新增了同进程触发路由 `POST /runs` 与 `POST /batches`
- 宿主机 cron 默认改为调用触发 API，而不是 `docker compose exec` 新开进程

## 1. 部署组件

- `app`
  - 基于当前 Python 项目构建的应用容器
  - 同时承载 FastAPI、WebSocket、CLI 执行环境
- `postgres`
  - 持久化研报与工作流状态
- `nginx`
  - 统一对外暴露 HTTP / WebSocket 入口

## 2. 新增文件

- `Dockerfile`
- `docker-compose.yml`
- `.env.example`
- `deploy/app/start.sh`
- `deploy/cron/run_batch.sh`
- `deploy/nginx/default.conf`
- `deploy/verify_websocket.py`

## 3. 初始化

在项目根目录执行：

```bash
cp .env.example .env
```

如果你暂时没有 `ANTHROPIC_API_KEY`，可以保持为空。当前项目会自动回退到 mock 生成流程，便于先验证部署链路。

如需启用真实 Anthropic 调用，请在 `.env` 中填写：

```dotenv
ANTHROPIC_API_KEY=<百炼 Coding Plan key>
ANTHROPIC_BASE_URL=https://coding.dashscope.aliyuncs.com/apps/anthropic
LLM_MODEL=kimi-k2.5
```

默认 `ANALYSIS_RENDER_MODE=hybrid`、`REPORT_RENDER_MODE=hybrid`。该模式下，配置 key 后分析环节会调用模型生成结构化观点 brief，研报正文仍由确定性模板写入可核验数字。若需要分析和研报撰写都走模型调用，部署环境中设置：

```dotenv
ANALYSIS_RENDER_MODE=llm
REPORT_RENDER_MODE=llm
```

CTP 快照主链路已切换到期宝图 PC API。部署环境需要在 `.env` 或 GitLab CI/CD Variables 的 `DEPLOY_ENV_FILE` 中配置：

```dotenv
CTP_SNAPSHOT_BASE_URL=https://pc-api.qibaotu.com
CTP_SNAPSHOT_AUTH_KEY=<内部测试 header key>
CTP_SNAPSHOT_SKIP_CRYPTO=true
CTP_SNAPSHOT_SKIP_CHECK=true
ENABLE_YAHOO_MARKET_SOURCE=true
ENABLE_AKSHARE_COMMODITY_SOURCE=true
```

`CTP_SNAPSHOT_AUTH_KEY` 属于内部联调用 header，不要放入前端代码或公开文档。

## 4. 启动服务

```bash
docker compose up --build -d
```

查看状态：

```bash
docker compose ps
```

查看应用日志：

```bash
docker compose logs -f app
```

## 5. 对外访问

默认通过 Nginx 对外暴露在：

- 前端控制台：`http://127.0.0.1:8080/`
- API 根地址：`http://127.0.0.1:8080`
- 健康检查：`http://127.0.0.1:8080/healthz`
- 报告列表：`http://127.0.0.1:8080/reports`
- 单品种触发：`POST http://127.0.0.1:8080/runs`
- 批量触发：`POST http://127.0.0.1:8080/batches`
- WebSocket：`ws://127.0.0.1:8080/ws/events`

如需修改外部端口，调整 `.env` 中的 `NGINX_PORT`。

## 6. 部署后手动触发

单品种：

```bash
docker compose exec app python run.py --symbol CF
docker compose exec app python run.py --symbol CF --contract CF2609
```

批量：

```bash
docker compose exec app python run.py --symbols CF,M --target-date 2026-04-01 --concurrency 2
```

全品种：

```bash
docker compose exec app python run.py --all-varieties
```

同进程 API 触发单品种：

```bash
curl -X POST http://127.0.0.1:8080/runs \
  -H 'Content-Type: application/json' \
  -d '{"symbol":"CF","contract":"CF2609","target_date":"2026-04-01"}'
```

同进程 API 触发批量：

```bash
curl -X POST http://127.0.0.1:8080/batches \
  -H 'Content-Type: application/json' \
  -d '{"symbols":["CF","M"],"target_date":"2026-04-01","concurrency":2}'
```

输出说明：

- Markdown 文件保存在宿主机 `outputs/`
- 运行日志保存在宿主机 `logs/`
- PostgreSQL 数据保存在命名卷 `postgres_data`

浏览器前端说明：

- 打开首页后，页面会自动显示 API / WebSocket 地址
- 先执行健康检查，再连接 WebSocket
- 页面内置“测试流程”和“使用手册”，可以直接按顺序完成验收
- 若数据库未配置，报告列表区域会提示当前只支持流程验证

## 7. WebSocket 验证

只验证路由可连接：

```bash
docker compose exec app python deploy/verify_websocket.py \
  --url ws://nginx/ws/events?channel=run \
  --expect 1
```

验证订阅后能收到运行事件：

终端 A：

```bash
docker compose exec app python deploy/verify_websocket.py \
  --url ws://nginx/ws/events?channel=run \
  --expect 3
```

终端 B：

```bash
curl -X POST http://127.0.0.1:8080/runs \
  -H 'Content-Type: application/json' \
  -d '{"symbol":"CF","target_date":"2026-04-01"}'
```

预期终端 A 至少收到：

- `subscribed`
- `run_started`
- `step_started`

## 8. 宿主机 cron 最小方案

先给脚本执行权限：

```bash
chmod +x deploy/cron/run_batch.sh
```

手动先跑一次：

```bash
./deploy/cron/run_batch.sh --all-varieties
```

示例：每个交易日 17:30 触发全品种批量执行

```cron
30 17 * * 1-5 cd /Users/ann/Documents/投研agent && ./deploy/cron/run_batch.sh --all-varieties >> /Users/ann/Documents/投研agent/logs/cron.log 2>&1
```

示例：每天 18:00 只跑棉花

```cron
0 18 * * * cd /Users/ann/Documents/投研agent && ./deploy/cron/run_batch.sh --symbol CF >> /Users/ann/Documents/投研agent/logs/cron.log 2>&1
```

## 9. 停止与清理

停止服务：

```bash
docker compose down
```

停止并删除数据库卷：

```bash
docker compose down -v
```

## 10. MVP 架构说明

当前部署链路为：

```text
client -> nginx -> fastapi/websocket(app) -> postgres
                           |
                           -> python run.py CLI / batch runner
```

设计取舍：

- `app` 既负责 API，也负责 CLI 任务触发，减少额外服务数量
- `nginx` 统一处理 HTTP 与 WebSocket 代理，便于后续加鉴权或 HTTPS
- 定时执行先交给宿主机 `cron` 调用触发 API，避免在 MVP 阶段过早引入 Celery / Redis
- 未配置真实模型密钥时仍可用 mock 流程验证整条部署链

## 11. GitLab CI/CD（main 自动打包 + 自动部署）

仓库已支持 GitLab CI/CD，入口文件：

- `.gitlab-ci.yml`
- `deploy/ci/deploy_main.sh`

流水线阶段：

- `test`
  - 创建虚拟环境并安装：
    - `requirements.txt`
    - `report_review_agent/requirements.txt`
  - 执行：
    - `DATABASE_URL='' python -m unittest discover -s tests -v`
    - `DATABASE_URL='' python -m unittest discover -s report_review_agent/tests -v`
- `package-main`（仅 `main`）
  - 打包代码为 `dist/<project>-<sha>.tar.gz`
  - 生成 `sha256` 校验文件并作为 artifact 保存
- `deploy-main`（仅 `main`）
  - 使用 `deploy/ci/deploy_main.sh` 自动部署到 `/opt/apps/...`

Runner 约束：

- 全局指定 `tags: [demo-shell]`
- 需确保该 runner 具备：
  - `python3` / `pip`
  - `tar`
  - （可选）`docker compose` 或 `docker-compose`
  - （可选）`systemctl`

默认部署目录：

- `/opt/apps/research-report-agent`
- 发布结构：
  - `/opt/apps/research-report-agent/releases/<commit>`
  - `/opt/apps/research-report-agent/current`（软链指向当前版本）
  - `/opt/apps/research-report-agent/shared/.env`（可选）
  - `/opt/apps/research-report-agent/shared/{outputs,logs,memory}`

建议在 GitLab CI/CD Variables 配置：

- `DEPLOY_USE_SUDO`
  - `true` 时部署脚本用 `sudo` 执行写入 `/opt`、重启服务等操作
- `DEPLOY_PATH`
  - 自定义部署目录；默认 `/opt/apps/research-report-agent`
- `DEPLOY_ENV_FILE`
  - 多行 `.env` 内容，部署时写入 `shared/.env`
  - 若不提供该变量，部署脚本会自动使用仓库内 `.env.example` 生成 `.env`（兜底保证 Docker Compose 可启动）
- `DEPLOY_WITH_DOCKER_COMPOSE`
  - 默认 `true`；若不希望部署阶段执行 `docker compose up -d --build`，设为 `false`
- `SYSTEMD_SERVICE`
  - 可选，填写后部署完成会执行 `systemctl restart <service>`
