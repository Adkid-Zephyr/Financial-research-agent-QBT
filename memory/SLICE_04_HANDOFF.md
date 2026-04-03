# 切片4交付摘要

## 切片范围
- 激活 LangGraph 中 `review` 节点的条件边，形成最多两轮审核重写循环。
- 将上一轮审核反馈显式注入 analyzer / writer，确保二轮改写具备针对性。
- 补充循环相关测试，并验证单品种与批量 CLI 入口未受破坏。

## 已实现类名和公开方法签名

### Workflow
- `futures_research.workflow.graph.build_workflow(runtime: RuntimeContext)`
  - 工作流路径调整为 `aggregate -> analyze -> write -> review -> (analyze | end)`
- `futures_research.workflow.graph._route_after_review(state: WorkflowGraphState) -> str`
  - 路由规则：通过则结束；未通过且 `review_round < max_review_rounds` 时回到 `analyze`；否则结束

### Agents
- `futures_research.agents.analyzer.analyze_node(state: Dict[str, Any], runtime: RuntimeContext) -> Dict[str, Any]`
  - 新增向 LLM context 注入 `review_feedback`、`blocking_issues`、`requested_review_round`
- `futures_research.agents.writer.write_node(state: Dict[str, Any], runtime: RuntimeContext) -> Dict[str, Any]`
  - 新增向 LLM context 注入 `review_feedback`、`blocking_issues`、`requested_review_round`

## 关键 Pydantic 数据结构字段

### `WorkflowState`
- `review_round`
- `max_review_rounds`
- `review_result`
- `review_history`
- `final_report`

说明：
- `max_review_rounds` 默认值已提升为 `2`
- `review_history` 现在覆盖最多两轮审核记录，最终 `final_report.review_rounds` 与最后一轮审核保持一致

## 对外暴露的 API 路由
- 本切片未新增 REST 路由。
- 继续沿用切片2接口：
  - `GET /healthz`
  - `GET /reports`
  - `GET /reports/{run_id}`

## 运行说明
- 单品种运行：
  - `.venv/bin/python run.py --symbol CF --target-date 2026-04-01`
- 批量运行：
  - `.venv/bin/python run.py --symbols CF,M --target-date 2026-04-01 --concurrency 2`

## 新增测试覆盖
- `tests/test_workflow.py`
  - 覆盖首轮审核未通过后二轮改写并通过
  - 覆盖连续未通过时在最大审核轮次后兜底结束
- `tests/test_reviewer.py`
  - 补充审核轮次与审核历史记录断言

## 当前验收结论
- `2026-04-01` 执行 `.venv/bin/python -m unittest tests.test_reviewer tests.test_workflow`
  - 8 个用例全部通过。
- `2026-04-01` 执行 `.venv/bin/python -m unittest discover -s tests`
  - 13 个用例全部通过。
- `2026-04-01` 执行 `.venv/bin/python run.py --symbol CF --target-date 2026-04-01`
  - 单品种 CLI 入口保持可用，成功输出完整研报与审核摘要。
- `2026-04-01` 执行 `.venv/bin/python run.py --symbols CF,M --target-date 2026-04-01 --concurrency 2`
  - 批量 CLI 入口保持可用，`CF` 与 `M` 均完成并通过。

## 切片5建议边界
- 新增独立的 WebSocket 推送模块，不修改 Agent 层。
- 优先复用切片2的 FastAPI 应用，增加任务运行过程事件流与结果推送。
- 推送事件至少覆盖：批次开始、单品种开始、审核轮次变更、单品种完成、批次完成、异常。
- 保持现有 REST 路由、`run_research()` 签名、`ResearchScheduler` 批量入口不变。

## 新线程提示词
继续这个项目，从切片4已完成状态开始，先阅读 `/Users/ann/Documents/投研agent/memory/PROJECT_MEMORY.md` 和 `/Users/ann/Documents/投研agent/memory/SLICE_04_HANDOFF.md`，然后进入切片5：在不修改 Agent 层的前提下，为现有 FastAPI 应用补充独立的 WebSocket 实时推送模块，支持单品种与批量任务的运行事件广播，补充对应测试，并把新的接口摘要和验收结果写回 memory 文档。
