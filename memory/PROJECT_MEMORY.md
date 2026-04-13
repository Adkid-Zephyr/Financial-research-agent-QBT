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
- 主项目当前已切换到真实数据优先模式：运行时只注册 `ctp_snapshot` 数据源，不再让 `mock` / `web_search_20250305` 进入正式工作流。
- `2026-04-13` 已在 Phase 1 范围内补充可开关的外盘/宏观与商品基本面结构化数据源：`yahoo_market` 与 `akshare_commodity`。默认关闭，显式设置 `ENABLE_YAHOO_MARKET_SOURCE=true` / `ENABLE_AKSHARE_COMMODITY_SOURCE=true` 后才注册运行。
- `yahoo_market` 只用于外盘/宏观辅助事实，不作为交易所正式行情源；当前 AU/AG 配置覆盖 COMEX 金银、美元指数、美国 10 年期国债收益率、USD/CNY。
- `akshare_commodity` 只接入可核验结构化字段；当前 AU/AG 配置覆盖生意社现货与基差、上海黄金交易所现货日线、东方财富 COMEX 库存。SHFE/DCE 仓单接口在本轮探针中不稳定，未纳入正式正文。
- reviewer 来源白名单已扩展到 `Yahoo Finance via yfinance` 与 `AkShare`，但仍硬拦截 `Mock` 与 `web_search_20250305`；外盘/基本面数字若缺少对应来源标注会被 blocking。
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
- 当前真实行情接口为 `CTP_SNAPSHOT_BASE_URL=http://192.168.152.69:8081`，稳定查询路径为 `/api/snapshots?instruments=...`。
- 合约规范化策略已切到“多候选回退 + 最新交易日优先”：
  - SHFE / DCE / INE 通常优先小写合约
  - GFEX 需要同时尝试大小写，并按最新交易日优先选中实时快照
  - CZCE 需要同时尝试全码与短码，例如 `CF2605 -> CF605`
- 默认分析与写作模式改为 deterministic，避免正文数字被 LLM 脑补；若显式切回 `llm` 模式而又没有 live client，则直接报错，不再静默回退 mock 文案。

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
- `2026-04-10` 排查 8025 端口“像是在跑旧后端”问题后确认：根因不是端口残留，而是当前工作区里的 `futures_research/api/app.py` 与静态前端文件本身尚未包含 `started_at`、前端新版状态卡和事件卡片样式。
- `2026-04-10` 已为 `GET /healthz` 补充 `started_at`、`process_id`、`cwd` 字段，并为所有 GET 响应加上 `Cache-Control: no-store`，避免浏览器继续缓存旧首页和旧静态资源造成误判。
- `2026-04-10` 已更新 `futures_research/api/static/` 前端：顶部新增“后端启动时间”卡片，WebSocket 日志改为固定高度、卡片式事件流，报告详情区新增显式当前 `run_id`。
- `2026-04-10` 已把前端误回退的问题修正：恢复单篇删除、多选删除、报告列表中的生成时间展示，以及详情区的字符数 / 估算 tokens / 审核轮次统计。
- `2026-04-10` 已在后端补 `DELETE /reports/{run_id}` 与 `POST /reports/delete-batch`，删除时会同步移除本地 markdown / pdf 产物。
- `2026-04-10` 已把主项目工作区补齐到真实数据版本：新增 `futures_research/data_sources/ctp_snapshot_source.py`，运行时只注册该源；`CF/M/AU/AG/CU/AL/LC/SI` 的 YAML 已全部切到 `ctp_snapshot`。
- `2026-04-10` `aggregate_node` 已补 `research_workflow` 元信息，包含 `principle`、`analysis_order`、`verified_facts`、`can_write_formal_report`、`blocking_reason`。
- `2026-04-10` `review_node` 新增硬拦截：若正文或源列表包含 `Mock` 或 `web_search_20250305`，直接记为 blocking issue，避免旧路径混回正式报告。
- `2026-04-13` 已扩展数据源配置接口：`DataSourceConfig` 支持 `params`，`DataSourceAdapter.fetch()` 支持可选参数，`SourcePayload` 支持 `data_gaps`，`DataSourceRegistry.fetch_many()` 可按 YAML 配置传参。
- `2026-04-13` 新增 `futures_research/data_sources/yahoo_market_source.py`，使用 `yfinance` 拉取 Yahoo Finance 结构化日线行情；失败、缺依赖、空数据或过期数据只进入 `data_gaps`，不阻断 CTP 主流程。
- `2026-04-13` 新增 `futures_research/data_sources/akshare_commodity_source.py`，使用 `akshare` 拉取商品基本面结构化数据；当前实现模块包括 `spot_basis`、`sge_spot`、`comex_inventory`。
- `2026-04-13` `aggregate_node` 新增 `raw_data.external_market_facts` 与 `raw_data.fundamental_facts`，并在 CTP 快照交易日与目标日期不一致时，不再把 CTP highlights 放入 `verified_facts`。
- `2026-04-13` `analyzer` 的 hybrid fact pack 已加入 `external_market_facts` 与 `fundamental_facts`，LLM 仍禁止新增数字、日期、来源、机构名或网址。
- `2026-04-13` 修复 hybrid analyzer 对 LLM JSON 列表长度的脆弱依赖：`key_factor_views` 会规范为 4 条、`risk_views` 会规范为 3 条，缺失项只用不含数字和来源标签的确定性兜底文本补齐，避免 `_render_analysis_markdown` 因短列表 `IndexError` 中断。
- `2026-04-13` `writer` 已增强“国际市场”与“基本面分析”：外盘/宏观数字由程序嵌入，基本面新增“现货与基差”段，COMEX 库存写入“库存与持仓”；若 CTP 交易日不匹配，行情回顾中的 CTP 价格/持仓/成交量写为“暂无可核验数据”。
- `2026-04-13` `writer` 对 `analysis_brief.key_factor_views` / `risk_views` 改为安全读取，即使旧状态或异常 LLM 输出里列表不足，也不会再在确定性正文生成阶段崩溃。
- `2026-04-13` AU/AG YAML 已加入 `yahoo_market` 与 `akshare_commodity` 配置；其他品种暂不打开 AkShare 仓单/库存，后续需要逐交易所逐接口验收。

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
- `2026-04-10` 执行 `.venv/bin/python -m unittest tests.test_api`：6 个用例全部通过，覆盖新版 `/healthz` 字段与首页禁缓存头。
- `2026-04-10` 临时启动 `uvicorn futures_research.api.app:app --port 8031` 并验证：
  - `GET /healthz` 返回 `started_at` / `process_id` / `cwd`
  - `GET /` 已包含 `started-at-status`、`current-run-id`、`console-stream`
  - `GET /static/app.js` 返回 `Cache-Control: no-store, no-cache, must-revalidate, max-age=0`
- `2026-04-10` 执行 `.venv/bin/python deploy/verify_websocket.py --url 'ws://127.0.0.1:8031/ws/events?channel=run' --expect 4`，并配合 `POST /runs`：成功收到 `subscribed -> run_started -> step_started(aggregate) -> step_started(analyze)`。
- `2026-04-10` 已替换 8025 端口上的旧 `uvicorn` 进程，当前监听 PID 为新进程；`GET http://127.0.0.1:8025/healthz` 已返回新版字段。
- `2026-04-10` 执行 `.venv/bin/python deploy/verify_websocket.py --url 'ws://127.0.0.1:8025/ws/events?channel=run' --expect 4`，并配合 `POST /runs`：确认正式测试端口的 WebSocket 路由可用。
- `2026-04-10` 执行 `.venv/bin/python run.py --symbol CF --target-date 2026-04-10`：新报告正文只包含 `CTP snapshot API` 来源，棉花主数据合约自动解析为 `CF605`，不再出现 `MockExchangeBulletin`。
- `2026-04-10` 执行 `.venv/bin/python run.py --symbol LC --target-date 2026-04-10`：主数据合约自动解析为 `lc2607`，正文只包含实时快照数字和数据缺口说明。
- `2026-04-10` 执行 `.venv/bin/python run.py --symbols AU,AG,M,SI --target-date 2026-04-10 --concurrency 2`：4 个品种全部通过，最新生成 Markdown 均只包含 `CTP snapshot API` 来源。
- `2026-04-10` 执行 `.venv/bin/python -m unittest discover -s tests`：24 个用例全部通过。
- `2026-04-10` 已再次重启 `127.0.0.1:8025` 上的 uvicorn，新进程 PID 为 `69853`；`POST /runs` + `WS /ws/events?channel=run` 已在新代码下联调通过。
- `2026-04-10` 执行 `DELETE /reports/{run_id}` 真机验收：成功删除一篇刚生成的测试报告，列表首项已切换到下一条记录。
- `2026-04-13` 执行 `.venv/bin/python -m pip install 'yfinance>=0.2.60'` 与 `.venv/bin/python -m pip install 'akshare>=1.17.0'`，当前 `.venv` 已具备 yfinance 与 AkShare。
- `2026-04-13` yfinance 探针成功拉取 `GC=F`、`SI=F`、`DX-Y.NYB`、`^TNX`、`CNY=X` 日线；确认 yfinance 可补外盘/宏观行情，但不适合补真实商品库存、仓单、基差、开工率或供需平衡表。
- `2026-04-13` AkShare 探针确认 `futures_spot_price` 可返回 AU/AG/CU/AL/CF/M/LC/SI 的现货价格、主力合约、基差、基差率；`spot_hist_sge` 可返回上金所 AU/AG 现货日线；`futures_comex_inventory` 可返回 COMEX 金银库存；CZCE/GFEX 仓单接口可用，SHFE/DCE 仓单接口本轮返回 JSON 解析错误，暂不接正文。
- `2026-04-13` 执行 `.venv/bin/python -m unittest discover -s tests`：37 个用例全部通过，新增覆盖 yfinance adapter、AkShare adapter、来源白名单、未登记来源拦截、hybrid writer 确定性嵌入外盘/基本面数字。
- `2026-04-13` 执行 `ENABLE_YAHOO_MARKET_SOURCE=true ENABLE_AKSHARE_COMMODITY_SOURCE=true ANTHROPIC_API_KEY='' ANTHROPIC_BASE_URL='' .venv/bin/python run.py --symbol AU --target-date 2026-04-10`：成功生成包含 yfinance 外盘/宏观与 AkShare 现货基差/上金所现货/COMEX库存的新报告；最新样稿路径为 `outputs/2026-04-10/AU_AU2606_5e72e1c8.md` 与 `.pdf`。
- `2026-04-13` 验证目标日期 `2026-04-10` 与 CTP 最新快照交易日 `2026-04-13` 不一致时，报告不会把 CTP 价格、持仓量、成交量写成目标日事实，只写“暂无可核验数据”，同时允许 yfinance/AkShare 按各自可得日期引用。
- `2026-04-13` 执行 `.venv/bin/python -m unittest tests.test_workflow`：10 个用例全部通过，新增复现用例覆盖 live hybrid LLM 只返回 2 条 `key_factor_views` 和 1 条 `risk_views` 时仍能完成工作流。
- `2026-04-13` 执行 `.venv/bin/python -m unittest discover -s tests`：38 个用例全部通过。
- `2026-04-13` 执行 `ENABLE_YAHOO_MARKET_SOURCE=true ENABLE_AKSHARE_COMMODITY_SOURCE=true .venv/bin/python run.py --symbol AU --target-date 2026-04-10`：成功生成包含 Yahoo Finance 与 AkShare 结构化事实的 AU 报告，审核通过，确认修复后不会再因 analyzer 短列表崩溃。
- `2026-04-13` 已重启本地 `127.0.0.1:8025` FastAPI 服务到新代码，启用 `ENABLE_YAHOO_MARKET_SOURCE=true` 与 `ENABLE_AKSHARE_COMMODITY_SOURCE=true`；`GET /healthz` 返回 `web_search_enabled=false`，`POST /runs` 触发 AU 后台运行成功落库，最新报告数据源包含 CTP、Yahoo Finance 与 AkShare。

## 接口摘要
- 切片1详见 `memory/SLICE_01_HANDOFF.md`。
- 切片2详见 `memory/SLICE_02_HANDOFF.md`。
- 切片3详见 `memory/SLICE_03_HANDOFF.md`。
- 切片4详见 `memory/SLICE_04_HANDOFF.md`。
- 切片5详见 `memory/SLICE_05_HANDOFF.md`。
- 部署增强详见 `memory/DEPLOYMENT_MVP_HANDOFF.md`。

## 新线程接续提示词
- Phase 1 已完成；当前已补上 Docker Compose MVP 部署文件、同进程触发 API、真实 CTP 快照链路、hybrid LLM 写作约束、yfinance 外盘/宏观结构化数据源、AkShare 商品基本面结构化数据源。继续工作前请先阅读 `memory/PROJECT_MEMORY.md`、`README.md` 和必要时的 `memory/DEPLOYMENT_MVP_HANDOFF.md`。
