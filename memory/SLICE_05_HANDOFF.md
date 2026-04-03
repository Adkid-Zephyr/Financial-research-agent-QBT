# 切片5交付摘要

## 切片范围
- 为现有 FastAPI 应用补充独立的 WebSocket 实时推送模块。
- 在不修改 Agent 层文件的前提下，为单品种与批量任务增加运行事件广播。
- 将项目运行环境从 Python 3.9 升级到 Python 3.11，并完成回归验证。

## 已实现类名和公开方法签名

### 事件层
- `futures_research.events.EventBus.subscribe(channel: EventChannel | None = None, run_id: UUID | None = None, batch_id: UUID | None = None) -> EventSubscription`
- `futures_research.events.EventBus.unsubscribe(subscription_id: UUID) -> None`
- `futures_research.events.EventBus.publish(event: RuntimeEvent) -> None`
- `futures_research.events.publish_event(**payload) -> RuntimeEvent`
- `futures_research.events.batch_event_context(batch_id: UUID)`
- `futures_research.events.get_current_batch_id() -> UUID | None`

### API
- `futures_research.api.app.create_app(repository: Optional[ReportRepository] = None, event_bus: Optional[EventBus] = None) -> FastAPI`
- `futures_research.api.routes.events.websocket_events(websocket: WebSocket)`

### 编排层事件注入
- `futures_research.main.run_research(symbol: str, target_date: date) -> WorkflowState`
  - 保持原签名不变；新增 `run_started` / `run_completed` / `run_failed` 广播
- `futures_research.workflow.graph.build_workflow(runtime: RuntimeContext)`
  - 保持 Agent 调用逻辑不变；新增 `step_started` 与 `review_round_completed` 广播
- `futures_research.scheduler.ResearchScheduler.run_batch(symbols: Sequence[str], target_date: date, concurrency: int = 2) -> BatchResearchSummary`
  - 保持原批量入口不变；新增 `batch_started` / `batch_completed` / `batch_failed` 广播

## 关键 Pydantic 数据结构字段

### `RuntimeEvent`
- `event_id`
- `channel`
- `event_type`
- `created_at`
- `run_id`
- `batch_id`
- `requested_symbol`
- `resolved_symbol`
- `variety_code`
- `variety`
- `target_date`
- `step`
- `review_round`
- `payload`

### `EventSubscription`
- `subscription_id`
- `channel`
- `run_id`
- `batch_id`
- `queue`

说明：
- `queue` 为线程安全队列，用于跨线程向 WebSocket 推送事件。
- `channel` 当前分为 `run` 与 `batch` 两类。

## 对外暴露的 API 路由
- `GET /healthz`
- `GET /reports`
- `GET /reports/{run_id}`
- `WS /ws/events`

### `WS /ws/events` 查询参数
- `channel`
  - 可选值：`run`、`batch`
- `run_id`
  - 可选，订阅指定单品种运行事件
- `batch_id`
  - 可选，订阅指定批次事件

### WebSocket 事件类型
- 单品种运行：
  - `run_started`
  - `step_started`
  - `review_round_completed`
  - `run_completed`
  - `run_failed`
- 批量运行：
  - `batch_started`
  - `batch_item_started`
  - `batch_item_completed`
  - `batch_item_failed`
  - `batch_completed`
  - `batch_failed`

## Python 3.11 运行说明
- 主解释器：
  - `.tools/python311/bin/python3.11`
- 当前项目虚拟环境：
  - `.venv`
- 历史 Python 3.9 虚拟环境备份：
  - `.venv-py39-backup`

说明：
- 当前主支持版本为 Python 3.11.9。
- `.venv-py39-backup` 仅作为历史回滚参考，不再作为受支持运行环境。

## 新增测试覆盖
- `tests/test_websocket.py`
  - 覆盖单品种运行的 WebSocket 事件序列广播
  - 覆盖批量运行的 WebSocket 批次事件广播

## 当前验收结论
- `2026-04-01` 执行 `.venv/bin/python --version`
  - 输出 `Python 3.11.9`
- `2026-04-01` 执行 `.venv/bin/python -m unittest discover -s tests`
  - 15 个用例全部通过
- `2026-04-01` 执行 `.venv/bin/python run.py --symbol CF --target-date 2026-04-01`
  - 单品种 CLI 入口通过，成功输出完整研报与审核摘要
- `2026-04-01` 执行 `.venv/bin/python run.py --symbols CF,M --target-date 2026-04-01 --concurrency 2`
  - 批量 CLI 入口通过，两个品种全部完成并通过
- `2026-04-01` 执行 FastAPI WebSocket 烟测
  - 成功收到 `run_started -> step_started -> review_round_completed -> run_completed` 实时事件

## 项目现状
- Phase 1 五个切片均已完成。
- 当前没有未完成的 Phase 1 阻塞项。
- 后续若继续，建议进入 Phase 2、自定义指标接入、生产部署、监控告警或权限/鉴权增强。

## 新线程提示词
继续这个项目，先阅读 `/Users/ann/Documents/投研agent/memory/PROJECT_MEMORY.md` 和 `/Users/ann/Documents/投研agent/memory/SLICE_05_HANDOFF.md`，然后基于当前 Phase 1 已完成状态，帮助我推进下一阶段工作（如果是 Phase 2，就优先设计并实现自定义指标接入与策略信号占位接口；如果是部署方向，就优先梳理生产化部署、监控和鉴权方案），并把新的决策、执行日志、验收结果持续写回 memory 文档。
