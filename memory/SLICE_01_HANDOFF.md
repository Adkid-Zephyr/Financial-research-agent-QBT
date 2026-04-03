# 切片1交付摘要

## 已实现类名和公开方法签名

### CLI / 入口
- `futures_research.main.run_research(symbol: str, target_date: date) -> WorkflowState`
- `futures_research.cli.main() -> int`

### 运行时与配置
- `futures_research.runtime.build_runtime() -> RuntimeContext`
- `futures_research.varieties.VarietyRegistry.scan() -> None`
- `futures_research.varieties.VarietyRegistry.register(variety: VarietyDefinition) -> None`
- `futures_research.varieties.VarietyRegistry.get(symbol_or_code: str) -> VarietyDefinition`
- `futures_research.varieties.VarietyRegistry.resolve_contract(symbol_or_code: str) -> str`

### 数据源
- `futures_research.data_sources.base.DataSourceRegistry.register(adapter: DataSourceAdapter) -> None`
- `futures_research.data_sources.base.DataSourceRegistry.get(source_type: str) -> DataSourceAdapter`
- `futures_research.data_sources.base.DataSourceRegistry.fetch_many(request: DataFetchRequest, source_types: Iterable[str]) -> List[SourcePayload]`
- `futures_research.data_sources.mock_source.MockDataSource.fetch(request: DataFetchRequest) -> SourcePayload`
- `futures_research.data_sources.web_search_source.WebSearchSource.fetch(request: DataFetchRequest) -> SourcePayload`

### Prompt
- `futures_research.prompts.loader.PromptRepository.load_market_template(variety_definition: VarietyDefinition) -> str`
- `futures_research.prompts.analyzer_prompt.build_analyzer_user_prompt(...) -> str`
- `futures_research.prompts.writer_prompt.build_writer_user_prompt(...) -> str`

### LLM
- `futures_research.llm.client.LLMClient.generate_analysis(prompt: str, context: Dict[str, Any]) -> str`
- `futures_research.llm.client.LLMClient.generate_report(prompt: str, context: Dict[str, Any]) -> str`

### Agent 节点
- `futures_research.agents.aggregator.aggregate_node(state: Dict[str, Any], runtime: RuntimeContext) -> Dict[str, Any]`
- `futures_research.agents.analyzer.analyze_node(state: Dict[str, Any], runtime: RuntimeContext) -> Dict[str, Any]`
- `futures_research.agents.writer.write_node(state: Dict[str, Any], runtime: RuntimeContext) -> Dict[str, Any]`
- `futures_research.agents.reviewer.review_node(state: Dict[str, Any], runtime: RuntimeContext) -> Dict[str, Any]`

### Workflow
- `futures_research.workflow.graph.build_workflow(runtime: RuntimeContext)`

## 关键 Pydantic 数据结构字段

### `VarietyDefinition`
- `code`
- `name`
- `exchange`
- `contracts`
- `key_factors`
- `news_keywords`
- `data_sources`
- `prompt_template`

### `WorkflowState`
- `run_id`
- `symbol`
- `variety_code`
- `variety`
- `target_date`
- `current_step`
- `review_round`
- `raw_data`
- `analysis_result`
- `report_draft`
- `review_result`
- `review_history`
- `final_report`
- `data_sources_used`
- `error`

### `ResearchReport`
- `symbol`
- `variety_code`
- `variety`
- `target_date`
- `generated_at`
- `review_rounds`
- `final_score`
- `content`
- `summary`
- `sentiment`
- `confidence`
- `key_factors`
- `risk_points`
- `data_sources`

### `ReviewResult`
- `round`
- `total_score`
- `passed`
- `dimension_scores`
- `feedback`
- `blocking_issues`

## 对外暴露的 API 路由
- 切片1尚未引入 REST API。

## 当前验收结论
- `python run.py --symbol CF` 已能在终端输出完整 Markdown 研报。
- `python run.py --symbol M` 已验证纯 YAML 新增品种可直接运行。
- Reviewer 独立测试已覆盖：
  - 绝对化表述一票否决
  - 缺失来源导致 `data_quality < 10`
  - 完整研报通过
- Workflow 测试已覆盖：
  - `CF` 端到端生成
  - `M` 纯配置品种扩展
- 低代码示例已新增 `varieties/M.yaml`，下一步可执行 `python run.py --symbol M` 验证豆粕无需改 Python 代码。

## 切片2建议边界
- 在不修改 Agent 逻辑的前提下增加存储层。
- 从 SQLite/本地输出切到 PostgreSQL + FastAPI GET。
- 建议新增模块：
  - `storage/postgres.py`
  - `storage/report_repository.py`
  - `api/app.py`
  - `api/routes/reports.py`

## 新线程提示词
继续这个项目，从切片1已完成状态开始，先阅读 `/Users/ann/Documents/投研agent/memory/PROJECT_MEMORY.md` 和 `/Users/ann/Documents/投研agent/memory/SLICE_01_HANDOFF.md`，然后进入切片2：在不修改任何 Agent 逻辑的前提下，为现有 `run_research()` 工作流增加 PostgreSQL 存储和 FastAPI 只读查询接口，补充相应测试，并把新的接口摘要和验收结果写回 memory 文档。
