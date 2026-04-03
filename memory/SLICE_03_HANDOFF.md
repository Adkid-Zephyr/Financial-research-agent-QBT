# 切片3交付摘要

## 切片范围
- 保持单品种 `run_research()` 作为原子能力不变。
- 新增多品种批量调度入口与批次级结果聚合。
- 扩展 CLI，支持单品种与批量运行共存。
- 补充批量调度测试与真实批量烟测。

## 已实现类名和公开方法签名

### Scheduler
- `futures_research.scheduler.ResearchScheduler.__init__(runner: BatchRunner = run_research) -> None`
- `futures_research.scheduler.ResearchScheduler.run_batch(symbols: Sequence[str], target_date: date, concurrency: int = 2) -> BatchResearchSummary`
- `futures_research.scheduler.run_batch_research(symbols: Sequence[str], target_date: date, concurrency: int = 2, runner: BatchRunner = run_research) -> BatchResearchSummary`

### CLI
- `futures_research.cli.main() -> int`
  - 兼容旧入口：`python run.py --symbol CF`
  - 新增批量入口：`python run.py --symbols CF,M --concurrency 2`
  - 新增全品种入口：`python run.py --all-varieties --concurrency 2`

## 关键 Pydantic 数据结构字段

### `BatchResearchItem`
- `requested_symbol`
- `resolved_symbol`
- `variety_code`
- `variety`
- `run_id`
- `final_score`
- `review_passed`
- `status`
- `error`

### `BatchResearchSummary`
- `batch_id`
- `target_date`
- `requested_symbols`
- `started_at`
- `completed_at`
- `concurrency`
- `total`
- `succeeded`
- `failed`
- `passed`
- `marginal`
- `average_score`
- `items`

## 对外暴露的 API 路由
- 本切片未新增 REST 路由。
- 继续沿用切片2接口：
  - `GET /healthz`
  - `GET /reports`
  - `GET /reports/{run_id}`

## 运行说明
- 单品种保持不变：
  - `.venv/bin/python run.py --symbol CF --target-date 2026-04-01`
- 批量运行：
  - `.venv/bin/python run.py --symbols CF,M --target-date 2026-04-01 --concurrency 2`
- 全品种运行：
  - `.venv/bin/python run.py --all-varieties --target-date 2026-04-01 --concurrency 2`

## 新增测试覆盖
- `tests/test_scheduler.py`
  - 覆盖批量结果聚合
  - 覆盖批次内单条失败不影响其他品种继续执行
  - 覆盖真实多品种批量工作流烟测

## 当前验收结论
- `2026-04-01` 执行 `.venv/bin/python -m unittest tests.test_scheduler tests.test_workflow`
  - 6 个用例全部通过。
- `2026-04-01` 执行 `.venv/bin/python -m unittest discover -s tests`
  - 11 个用例全部通过。
- `2026-04-01` 执行 `.venv/bin/python run.py --symbol CF --target-date 2026-04-01`
  - 单品种 CLI 入口保持可用，成功输出完整研报与审核摘要。
- `2026-04-01` 执行 `.venv/bin/python run.py --symbols CF,M --target-date 2026-04-01 --concurrency 2`
  - 成功输出批次摘要与逐品种运行明细，`CF` 与 `M` 均完成。

## 切片4建议边界
- 在 LangGraph 中激活 `review -> analyze/publish` 条件边，形成最多两轮审核重写循环。
- 将审核反馈显式注入 analyzer / writer 上下文，避免简单重复生成。
- 补充 reviewer 不通过场景、二轮改写场景与最大轮次兜底场景测试。
- 保持切片3的批量调度入口不变，只复用新的单次工作流能力。

## 新线程提示词
继续这个项目，从切片3已完成状态开始，先阅读 `/Users/ann/Documents/投研agent/memory/PROJECT_MEMORY.md` 和 `/Users/ann/Documents/投研agent/memory/SLICE_03_HANDOFF.md`，然后进入切片4：在不破坏现有单品种与批量调度入口的前提下，激活 LangGraph 中 review 节点的条件边与最多两轮审核重写循环，补充对应测试，并把新的接口摘要和验收结果写回 memory 文档。
