# 期货自动投研 Agent 记忆文档

## 项目目标
- 按垂直切片推进自动投研 Agent。
- 当前状态：Phase 1 五个切片已全部完成。
- Phase 1 之后已进入 MVP 部署增强阶段，目标是在不做大重构的前提下补齐单机 Docker Compose 部署。

## 用户约束
- 必须分切片开发，不一次性实现全部模块。
- 新品种接入必须纯配置，不修改 Python 代码。
- 需要将计划、执行日志、评估、任务分割长期保存在本地，便于新线程续接。

## 切片定义
1. 脚手架 + 单品种单次研报生成
2. 研报存储 + REST API
3. 多品种调度
4. 审核 Agent 强化 + 重写循环
5. WebSocket 实时推送

## 当前决定
- 切片1只实现线性 LangGraph：aggregate -> analyze -> write -> review。
- 数据层默认只启用 MockDataSource，但保留 web_search 数据源与 Anthropic tool 接口。
- 切片2采用 SQLAlchemy + PostgreSQL DSN 方式接入存储；未配置 `DATABASE_URL` 时保持工作流可运行但不落库。
- 切片2只新增工作流后置持久化与 FastAPI 只读查询，不修改任何 Agent 节点逻辑。
- 切片3新增批量调度入口时，不修改 `run_research()` 签名，不触碰 Agent 逻辑与已有 API 路由。
- 批量入口当前采用异步并发调度与结果聚合实现，作为切片4/5的复用基础。
- 切片4在不新增 publish 节点的前提下，使用 `review -> analyze/end` 条件边完成最多两轮审核重写循环，由最后一次 `review` 产出最终 `final_report`。
- analyzer / writer 必须显式接收上一轮审核反馈、阻断问题和目标轮次，避免二轮改写退化为无反馈重生成。
- 切片5通过独立事件总线 + FastAPI WebSocket 路由实现实时广播，不修改 Agent 层文件。
- Python 3.11 仍是当前默认开发/验收版本；`2026-04-02` 已完成 Python 3.14.3 适配验证，项目代码与测试可跑通，但 LangGraph / langchain-core 依赖链在导入时仍会触发 `pydantic.v1` 的 Python 3.14 上游兼容性告警，因此暂不把 Python 3.14 标记为“正式主支持版本”。
- 本地 Python 3.11.9 运行时通过 `.tools/python311/bin/python3.11` 提供，不依赖系统 Python 3.11。
- 部署阶段优先采用单机 Compose：`app + postgres + nginx`，不引入 Redis/Celery。
- 为了让部署态 WebSocket 真正收到运行事件，新增同进程触发 API：`POST /runs`、`POST /batches`；宿主机 cron 默认调用这两个路由，而不是 `docker compose exec app python run.py ...` 新开进程。
- CLI 入口保持可用，用于人工排障与手工执行；部署态实时订阅优先走 API 触发。
- 本地手工测试环境默认改为 SQLite 文件库 `sqlite+pysqlite:///./futures_research_local.db`，这样不开 Docker 也能在 UI 中查看报告存储。
- 当前 LLM 接入已切换为阿里云百炼 Anthropic 兼容端，基础配置为 `ANTHROPIC_BASE_URL=https://coding.dashscope.aliyuncs.com/apps/anthropic`，模型 ID 使用官方名称 `kimi-k2.5`。
- `2026-04-03` 开始为“公司客户端前的网页测试入口”做前端重构，优先在现有 FastAPI + 静态页架构上完成产品化研究入口，而不是引入新的前端构建体系。
- 这轮前端改造不扩 Phase 2，继续使用 Phase 1 现有工作流与 mock 数据链路，但允许把用户自定义研究诉求注入到 prompt 和最终报告中。
- 为了支持“先梳理需求、再生成研报”的交互，新增研究偏好模型与 API：`/research/options` 用于加载品种/周期/身份元数据，`/research/preview` 用于生成研究诉求摘要。
- 单品种触发 API `POST /runs` 现已支持 `research_profile`，并在响应中返回 `run_id` 与 `resolved_symbol`，方便网页前端按一次具体任务订阅事件、查询详情和展示下载链接。

## 实际执行日志
- 已创建项目脚手架、低代码品种配置扫描器、DataSourceRegistry、MockDataSource、PromptRepository、LangGraph 线性图。
- 已接入 Anthropic SDK 封装；存在 API Key 时可走真实模型，默认无 Key 时回退为本地 mock 生成器。
- 已完成 reviewer 的本地可测试评分逻辑，保证切片1稳定验收。
- 已修复 LangGraph 异步节点包装问题。
- 已新增 `storage/` 层，支持将 `WorkflowState` 与 `ResearchReport` 持久化到 `research_reports` 表。
- 已在 `run_research()` 末尾接入存储工厂，配置 `DATABASE_URL` 后自动建表并保存本次研究结果。
- 已新增 FastAPI 应用与只读查询路由，支持报告列表筛选与按 `run_id` 查看完整详情。
- 已补充 API / 存储测试，覆盖工作流持久化、列表查询、详情查询。
- 已新增 `BatchResearchItem` / `BatchResearchSummary` 批次模型，以及 `ResearchScheduler` 批量调度器。
- 已在 `scheduler.py` 中实现多品种并发批量执行、失败隔离与批次级统计聚合。
- 已扩展 CLI，支持 `--symbols` 与 `--all-varieties` 批量运行，同时保持 `--symbol` 单品种入口兼容。
- 已补充批量调度测试与真实批量烟测，确认 `CF`、`M` 两个 YAML 品种可在同一批次内完成运行。
- 已激活 LangGraph 中 `review` 节点的条件边，审核通过时结束，未通过且未达上限时回到 `analyze`，最多执行两轮审核。
- 已将审核反馈、阻断问题与目标轮次注入 analyzer / writer prompt 和 LLM context，二轮修改可感知上一轮问题。
- 已补充工作流测试，覆盖“首轮不过后二轮通过”与“持续不过到上限后兜底结束”两种切片4核心路径。
- 已新增 `futures_research.events` 事件层，提供线程安全内存事件总线、统一事件模型与批次上下文注入。
- 已在 `run_research()`、`workflow.graph` 包装层与 `ResearchScheduler` 中注入运行事件，覆盖单品种开始、步骤开始、审核轮次完成、单品种完成/失败、批次开始、批次子任务开始/完成/失败、批次完成/失败。
- 已新增 `WS /ws/events` 路由，支持按 `channel`、`run_id`、`batch_id` 过滤订阅。
- 已补充 `tests/test_websocket.py`，用真实 WebSocket 连接验证单品种与批量事件广播。
- 已从 Python.org 的 `python-3.11.9-macos11.pkg` 提取本地 3.11 运行时到 `.tools/python311/`，并修正 Framework / OpenSSL 动态库引用，使其可在项目目录内独立运行。
- 已重建 `.venv` 为 Python 3.11.9 并重新安装依赖。
- 已新增 `Dockerfile`、`docker-compose.yml`、`.env.example`、`deploy/nginx/default.conf`、`deploy/app/start.sh`、`deploy/cron/run_batch.sh`、`deploy/verify_websocket.py`、`DEPLOYMENT.md`。
- 已为部署态补充最小手动触发 API，新增 `futures_research.api.routes.runs`，支持后台触发单品种与批量任务。
- 已把 `deploy/cron/run_batch.sh` 切换为调用 `POST /runs` / `POST /batches`，从而让 WebSocket 订阅与计划任务在同一 `app` 进程内打通。
- 已将 `websockets>=12.0` 加入依赖，用于部署后的 WebSocket 烟测脚本。
- 已新增零构建测试前端，入口为 `GET /`，静态资源位于 `futures_research/api/static/`，覆盖健康检查、单品种/批量触发、WebSocket 事件、报告查询、测试流程和使用手册。
- 已在 UI 顶部补充“打开报告存储”和“打开接口文档”直达入口，方便测试时跳转到 `/reports` 与 `/docs`。
- 已按纯配置方式新增 6 个测试品种：`AU`、`AG`、`CU`、`AL`、`LC`、`SI`。
- 已新增两类品种模板：`precious_metals_futures`（贵金属）与 `industrial_materials_futures`（有色/新能源材料）。
- 已修复 reviewer 对免责声明和“存在一定支撑”类表述的误判，支持 `AI生成` / `AI辅助生成` / `人工智能生成` 等变体。
- 已将 UI 默认批量品种列表示例更新为 `CF,M,AU,AG,CU,AL,LC,SI`，便于直接测试扩展后的品种集。
- 已完成 Python 3.14.3 适配修补：将 `scheduler.py` 中的 `datetime.utcnow()` 替换为 `datetime.now(UTC)`，并为 SQLAlchemy 仓储补充 `close()`/engine dispose，同时把 FastAPI 应用关闭逻辑切换到 `lifespan`，消除 3.14 下的 `DeprecationWarning` 与 SQLite `ResourceWarning`。
- 已新增 `futures_research.models.research` 与 `futures_research.research_profile`，用于统一管理研究周期、身份视角、前端元数据输出、研究需求摘要与 prompt 注入上下文。
- 已将 `run_research()` 扩展为可接收 `research_profile` 与预生成 `run_id`，并把 `request_context` 注入到初始 `WorkflowState.raw_data` 中，供后续聚合、分析、写作、存储、详情查询统一复用。
- 已将 `aggregate/analyze/write` 三段工作流接入用户偏好：Mock 数据摘要会体现身份/周期/重点；分析和写作 prompt 会显式读取“研究周期、身份视角、用户关注点、AI 梳理要点、写作导向”。
- 已增强本地 mock LLM 输出，使无真实模型时也能在报告中体现 `短线/中线/长线`、`散户短线高胜率交易者/供应商/期货部门/...` 等差异，便于网页端直接演示。
- 已重写 `futures_research/api/static/index.html`、`app.js`、`styles.css`，将原“验收控制台”升级为产品化的“期货研报工作台”：
  - 顶部参数条：品种、合约、研究周期、日期
  - 中央大输入框：一句话描述研报诉求
  - 底部身份卡片：切换散户短线、大户、供应商、期货部门、投机者等视角
  - 需求梳理卡片：展示 AI 摘要、关键关注点、写作导向、模板提示
  - 运行状态侧栏：健康状态、WebSocket、事件日志、当前任务状态
  - 最近一次生成结果：展示摘要、评分、情绪与 Markdown/PDF 下载
  - 历史报告和批量触发面板：保留原有调试能力
- 已补充 API / 工作流测试覆盖：
  - 新增 `/research/options` 与 `/research/preview` 接口测试
  - 更新 `POST /runs` 测试，验证 `research_profile`、`run_id`、`resolved_symbol`
  - 新增工作流测试，验证自定义研究偏好能进入 `WorkflowState.raw_data.request_context` 并影响生成报告
- 已修复 `WS /ws/events` 在服务关闭时把正常 `CancelledError` 打成异常日志的问题，停止本地 `uvicorn` 或容器时日志会更干净。

## 自测结果
- `.venv/bin/python run.py --symbol CF`：成功输出完整 Markdown 研报和审核摘要。
- `.venv/bin/python run.py --symbol M`：在仅新增 `varieties/M.yaml` 的情况下成功输出豆粕研报，未修改任何 Python 代码。
- `.venv/bin/python -m unittest tests.test_reviewer tests.test_workflow`：5 个用例全部通过。
- 已重新安装 `urllib3<2`，当前回归命令已不再打印 LibreSSL 兼容警告。
- `2026-04-01` 执行 `.venv/bin/python -m unittest discover -s tests`：8 个用例全部通过，覆盖 reviewer、workflow、storage、API。
- `2026-04-01` 执行 `.venv/bin/python run.py --symbol CF`：CLI 主流程保持可用，终端输出完整研报与审核摘要。
- `2026-04-01` 执行临时 SQLite 仓库烟测：在 patch `build_report_repository()` 后，`run_research("CF", date.today())` 成功写入并可按 `run_id` 读回；生产接入使用 `DATABASE_URL=postgresql+psycopg://...`。
- `2026-04-01` 执行 `.venv/bin/python -m unittest tests.test_scheduler tests.test_workflow`：6 个用例全部通过，覆盖批量聚合、批次失败隔离与真实多品种烟测。
- `2026-04-01` 执行 `.venv/bin/python -m unittest discover -s tests`：11 个用例全部通过。
- `2026-04-01` 执行 `.venv/bin/python run.py --symbols CF,M --target-date 2026-04-01 --concurrency 2`：成功输出批次摘要与逐品种明细，批次通过数为 2，失败数为 0。
- `2026-04-01` 执行 `.venv/bin/python -m unittest tests.test_reviewer tests.test_workflow`：8 个用例全部通过，覆盖 reviewer 基线与切片4循环场景。
- `2026-04-01` 执行 `.venv/bin/python -m unittest discover -s tests`：13 个用例全部通过。
- `2026-04-01` 执行 `.venv/bin/python run.py --symbol CF --target-date 2026-04-01`：单品种 CLI 入口保持可用，成功输出完整研报与审核摘要。
- `2026-04-01` 执行 `.venv/bin/python run.py --symbols CF,M --target-date 2026-04-01 --concurrency 2`：批量 CLI 入口保持可用，`CF` 与 `M` 均通过。
- `2026-04-01` 执行 `.venv/bin/python --version`：当前项目虚拟环境为 Python 3.11.9。
- `2026-04-01` 执行 `.venv/bin/python -m unittest discover -s tests`：15 个用例全部通过，新增覆盖 WebSocket 广播。
- `2026-04-01` 执行 `.venv/bin/python run.py --symbol CF --target-date 2026-04-01`：Python 3.11 环境下单品种 CLI 入口保持可用。
- `2026-04-01` 执行 `.venv/bin/python run.py --symbols CF,M --target-date 2026-04-01 --concurrency 2`：Python 3.11 环境下批量 CLI 入口保持可用。
- `2026-04-01` 执行 FastAPI `WebSocket /ws/events?channel=run` 烟测：成功收到 `run_started -> step_started*4 -> review_round_completed -> run_completed` 事件序列。
- `2026-04-01` 执行 `DATABASE_URL='' .venv/bin/python -m unittest discover -s tests`：17 个用例全部通过，覆盖 reviewer、workflow、storage、API、scheduler、websocket、trigger routes。
- `2026-04-01` 执行 `DATABASE_URL='' .venv/bin/python run.py --symbol CF --target-date 2026-04-01`：单品种 CLI 入口保持可用。
- `2026-04-01` 执行 `DATABASE_URL='' .venv/bin/python run.py --symbols CF,M --target-date 2026-04-01 --concurrency 2`：批量 CLI 入口保持可用。
- `2026-04-01` 本地 `uvicorn` 烟测 `http://127.0.0.1:8011/healthz`：返回 `{"status":"ok","storage_enabled":false}`。
- `2026-04-01` 本地 `POST http://127.0.0.1:8011/runs`：返回 `{"status":"accepted","requested_symbol":"CF","target_date":"2026-04-01"}`。
- `2026-04-01` 本地 `POST http://127.0.0.1:8011/batches`：返回 `{"status":"accepted","requested_symbols":["CF","M"],"target_date":"2026-04-01","concurrency":2}`。
- `2026-04-01` 本地 `deploy/verify_websocket.py --url 'ws://127.0.0.1:8011/ws/events?channel=run' --expect 4`：收到 `subscribed -> run_started -> step_started(aggregate) -> step_started(analyze)`。
- `2026-04-01` 本地 `deploy/verify_websocket.py --url 'ws://127.0.0.1:8011/ws/events?channel=batch' --expect 4`：收到 `subscribed -> batch_started -> batch_item_started(CF) -> batch_item_started(M)`。
- `2026-04-01` 本地 `deploy/verify_websocket.py --url 'ws://127.0.0.1:8012/ws/events?channel=run' --expect 8`：收到完整序列 `subscribed -> run_started -> step_started(aggregate/analyze/write/review) -> review_round_completed -> run_completed`。
- `2026-04-01` 执行 YAML 结构检查：`docker-compose.yml` 成功解析，服务包含 `app`、`postgres`、`nginx`，卷包含 `postgres_data`。
- `2026-04-01` 尝试执行 `docker --version` 与 `docker compose version`：当前环境均返回 `command not found`，因此尚未完成真正的容器启动验收。
- `2026-04-01` 执行 `DATABASE_URL='' .venv/bin/python -m unittest discover -s tests`：新增前端首页测试后共 `18` 个用例全部通过。
- `2026-04-01` 本地 `uvicorn` 烟测 `http://127.0.0.1:8013/` 与 `/static/app.js`：首页与静态资源均可正常访问。
- `2026-04-01` 执行百炼 Anthropic 兼容端最小连通性探针：返回 `pong`，确认 `kimi-k2.5` 与 `https://coding.dashscope.aliyuncs.com/apps/anthropic` 可响应。
- `2026-04-01` 执行 `.venv/bin/python -m unittest discover -s tests`：新增多品种配置与 reviewer 兼容性回归后共 `22` 个用例全部通过。
- `2026-04-01` 执行 mock 批量烟测 `ANTHROPIC_API_KEY='' ANTHROPIC_BASE_URL='' .venv/bin/python run.py --symbols AU,AG,CU,AL,LC,SI --target-date 2026-04-01 --concurrency 2`：6 个品种全部通过。
- `2026-04-01` 执行真实单品种烟测：
  - `AU` 成功生成沪金日报（早期一次因免责声明误判未通过，reviewer 已修复）
  - `AG` 成功生成并通过
  - `LC` 成功生成并通过
  - `SI` 成功生成并通过
- `2026-04-01` 本地 UI/接口验证：`GET /reports?limit=20` 返回的品种代码集合已包含 `LC, AG, SI, AL, CU, AU, M, CF`。
- `2026-04-02` 执行 `/tmp/futures-research-py314/bin/pip list` 与 `/tmp/futures-research-py314/bin/pip check`：Python 3.14.3 临时环境依赖安装完成，`No broken requirements found.`。
- `2026-04-02` 执行 `DATABASE_URL='' /tmp/futures-research-py314/bin/python -m unittest discover -s tests`：24 个用例全部通过。
- `2026-04-02` 执行 `DATABASE_URL='' /tmp/futures-research-py314/bin/python -W error::DeprecationWarning -W error::ResourceWarning -m unittest discover -s tests`：24 个用例全部通过，确认项目代码层面的 3.14 弃用/资源警告已清理。
- `2026-04-02` 执行 `ANTHROPIC_API_KEY='' ANTHROPIC_BASE_URL='' DATABASE_URL='' /tmp/futures-research-py314/bin/python run.py --symbol CF --target-date 2026-04-02`：CLI 单品种入口成功输出完整研报与审核摘要，但启动阶段仍出现 `langchain_core` 触发的 `Core Pydantic V1 functionality isn't compatible with Python 3.14 or greater.` 上游 `UserWarning`。
- `2026-04-02` 执行 `DATABASE_URL='' .venv/bin/python -m unittest discover -s tests`：Python 3.11.9 主环境回归通过，24 个用例全部通过。
- `2026-04-03` 执行 `.venv/bin/python -m unittest tests.test_api tests.test_workflow tests.test_websocket`：18 个用例全部通过，覆盖新研究入口 API、工作流定制偏好透传和现有 WebSocket 广播。
- `2026-04-03` 执行 `node --check futures_research/api/static/app.js`：前端脚本通过语法检查。
- `2026-04-03` 执行本地 `uvicorn` 烟测（`DATABASE_URL=sqlite+pysqlite:///./futures_research_local.db`，端口 `8021`）：
  - `GET /healthz` 返回 `status=ok` 且 `storage_enabled=true`
  - `GET /research/options` 返回 8 个品种、3 个研究周期、5 个身份视角
  - `POST /research/preview` 成功返回棉花 `CF2605` 的摘要、关键点、写作导向与模板提示
  - `GET /` 返回新的“期货研报工作台”静态首页
- `2026-04-03` 执行真实触发烟测：
  - `POST /runs` 提交 `CF2605 + short_term + retail_day_trader + 自定义关注点`，返回 `run_id=5394c6bc-c5f2-475c-8e7a-60fa92a91537`
  - `WS /ws/events?channel=run` 收到完整事件序列：`subscribed -> run_started -> step_started*4 -> review_round_completed -> run_completed`
  - `GET /reports/5394c6bc-c5f2-475c-8e7a-60fa92a91537` 可读回完整详情，`raw_data.request_context`、Markdown/PDF 下载地址均存在
  - `GET /outputs/2026-04-03/CF_CF2605_5394c6bc.md` 与 `.pdf` 均返回 `200 OK`
- `2026-04-03` 使用阿里百炼 Anthropic 兼容端做真实激活：
  - 最小探针 `messages.create(model='kimi-k2.5')` 返回 `pong`
  - 本地服务以 `ANTHROPIC_BASE_URL=https://coding.dashscope.aliyuncs.com/apps/anthropic`、`LLM_MODEL=kimi-k2.5`、`ENABLE_ANTHROPIC_WEB_SEARCH=false` 启动成功
  - `GET /healthz` 返回真实百炼 base URL
  - `POST /research/preview` 成功返回真实模型生成的摘要、关键点与写作导向
  - `POST /runs` 触发 `run_id=a190b6d9-752f-4d29-8e51-9fba655c9c14` 的真实模型研报生成
  - WebSocket 观测到首轮审核未过后自动进入第二轮重写，并在第二轮审核通过，最终 `review_round=2`、`final_score=100`
  - `GET /reports/a190b6d9-752f-4d29-8e51-9fba655c9c14` 返回完整详情，Markdown/PDF 下载地址可用

## 接口摘要
- 切片1详见 `memory/SLICE_01_HANDOFF.md`。
- 切片2详见 `memory/SLICE_02_HANDOFF.md`。
- 切片3详见 `memory/SLICE_03_HANDOFF.md`。
- 切片4详见 `memory/SLICE_04_HANDOFF.md`。
- 切片5详见 `memory/SLICE_05_HANDOFF.md`。
- 部署增强详见 `memory/DEPLOYMENT_MVP_HANDOFF.md`。
- 前端研究入口重构详见 `memory/FRONTEND_STUDIO_HANDOFF.md`。

## 新线程接续提示词
- Phase 1 已完成；当前已补上 Docker Compose MVP 部署文件与同进程触发 API。继续工作前请先阅读 `memory/PROJECT_MEMORY.md` 和 `memory/DEPLOYMENT_MVP_HANDOFF.md`。如果 Docker 已安装，优先完成真实 `docker compose up`、PostgreSQL 持久化、Nginx 代理与 WebSocket 的容器态验收；如果继续扩展生产化，则在现有基础上推进 HTTPS、鉴权、监控告警和运维脚本。
- 当前还额外完成了一版“期货研报工作台”前端研究入口。若在新线程继续，请先阅读 `memory/PROJECT_MEMORY.md` 和 `memory/FRONTEND_STUDIO_HANDOFF.md`，然后优先做以下其一：
  - 继续打磨网页前端的交互细节、视觉层级与多轮需求确认体验
  - 开始把这套前端交互拆成可嵌入公司客户端的接口契约和组件边界
  - 将研究偏好进一步注入真实 LLM 提示词/模板体系，而不只是在 mock 演示链路中生效
