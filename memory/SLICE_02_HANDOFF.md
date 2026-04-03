# 切片2交付摘要

## 切片范围
- 保持四个 Agent 节点逻辑不变。
- 在 `run_research()` 工作流完成后新增 PostgreSQL 持久化。
- 新增 FastAPI 只读查询接口与对应测试。

## 已实现类名和公开方法签名

### Workflow
- `futures_research.main.run_research(symbol: str, target_date: date) -> WorkflowState`
  - 签名未变；当 `DATABASE_URL` 已配置时，工作流结束后自动持久化。

### Storage
- `futures_research.storage.postgres.create_database_engine(database_url: str) -> Engine`
- `futures_research.storage.postgres.initialize_database(engine: Engine) -> None`
- `futures_research.storage.report_repository.SqlAlchemyReportRepository.initialize_schema() -> None`
- `futures_research.storage.report_repository.SqlAlchemyReportRepository.save_workflow_state(state: WorkflowState) -> None`
- `futures_research.storage.report_repository.SqlAlchemyReportRepository.list_reports(...) -> List[ReportSummary]`
- `futures_research.storage.report_repository.SqlAlchemyReportRepository.get_workflow_state(run_id: UUID) -> Optional[WorkflowState]`
- `futures_research.storage.report_repository.build_report_repository(database_url: Optional[str] = None) -> Optional[ReportRepository]`

### API
- `futures_research.api.app.create_app(repository: Optional[ReportRepository] = None) -> FastAPI`

## 存储模型摘要
- 新增表：`research_reports`
- 主键：`run_id`
- 核心索引字段：
  - `symbol`
  - `variety_code`
  - `target_date`
  - `generated_at`
- 持久化内容：
  - 工作流主状态字段：`current_step`、`review_round`、`analysis_result`、`report_draft`、`error`
  - 原始上下文：`raw_data`、`data_sources_used`
  - 审核结果：`review_result`、`review_history`
  - 最终研报：`final_report`、`final_score`、`summary`、`sentiment`、`confidence`

## 对外暴露的 API 路由
- `GET /healthz`
  - 返回服务状态与存储是否启用。
- `GET /reports`
  - 查询参数：`symbol`、`variety_code`、`target_date`、`limit`、`offset`
  - 返回 `ReportSummary[]`
  - 用途：列表页、按品种/日期筛选、最近报告浏览
- `GET /reports/{run_id}`
  - 返回完整 `WorkflowState`
  - 用途：按单次运行查看原始数据摘要、审核结果与最终研报全文

## 运行说明
- 启用持久化：
  - 设置 `DATABASE_URL=postgresql+psycopg://user:password@host:5432/dbname`
- 启动 API：
  - `.venv/bin/uvicorn futures_research.api:app --host 0.0.0.0 --port 8000`
- 未设置 `DATABASE_URL` 时：
  - `run_research()` 仍可执行，但不会落库。
  - `/reports*` 路由会返回 `503`。

## 新增测试覆盖
- `tests/test_workflow.py`
  - 新增 `run_research()` 持久化测试，验证工作流完成后可从仓库读回同一 `run_id`。
- `tests/test_api.py`
  - 覆盖 `GET /reports`
  - 覆盖 `GET /reports/{run_id}`

## 当前验收结论
- `2026-04-01` 执行 `.venv/bin/python -m unittest discover -s tests`
  - 8 个用例全部通过。
- `2026-04-01` 执行 `.venv/bin/python run.py --symbol CF`
  - 终端成功输出完整 Markdown 研报与审核摘要。
- `2026-04-01` 执行临时仓库烟测
  - 使用 `SqlAlchemyReportRepository(sqlite+pysqlite://...)` patch 到 `build_report_repository()`
  - `run_research("CF", date.today())` 成功写入并读回持久化结果。

## 切片3建议边界
- 新增多品种调度入口，但保持单品种 `run_research()` 作为可复用原子能力。
- 调度层优先做串行/批量执行与结果聚合，不要提前引入复杂编排。
- API 可继续沿用只读风格，再补“批次查询”而不是直接上写接口。

## 新线程提示词
继续这个项目，从切片2已完成状态开始，先阅读 `/Users/ann/Documents/投研agent/memory/PROJECT_MEMORY.md` 和 `/Users/ann/Documents/投研agent/memory/SLICE_02_HANDOFF.md`，然后进入切片3：在保持单品种 `run_research()` 能力稳定的前提下，增加多品种批量调度入口、批次结果聚合与相应测试，并把新的接口摘要和验收结果写回 memory 文档。
