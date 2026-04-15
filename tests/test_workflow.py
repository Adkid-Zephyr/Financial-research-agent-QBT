import asyncio
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from futures_research import config
from futures_research.data_sources.base import DataSourceAdapter, DataSourceRegistry
from futures_research.agents.writer import write_node
from futures_research.llm import client as llm_client_module
from futures_research.main import run_research
from futures_research.models.source import SourcePayload
from futures_research.models.state import WorkflowState
from futures_research.runtime import build_runtime
from futures_research.storage import SqlAlchemyReportRepository
from futures_research.workflow.graph import build_workflow


class RevisionAwareLLMClient:
    def __init__(self):
        self.analysis_contexts = []
        self.report_contexts = []

    async def generate_analysis(self, prompt, context):
        del prompt
        self.analysis_contexts.append(context)
        requested_round = context.get("requested_review_round", 1)
        review_feedback = context.get("review_feedback", "")
        prefix = "[第%d轮修改]\n" % requested_round if review_feedback else ""
        return """
{prefix}## 核心观点
维持中性判断。

## 基本面分析
### 供给端
供给平稳。
### 需求端
需求平稳。
### 库存
库存可控。

## 国际联动
国际市场波动可控。

## 近期重要事件
1. 模拟事件一。

## 核心驱动因子
1. 因子一
2. 因子二

## 风险提示
1. 政策变化。

## 情绪判断
中性，置信度：中。
""".strip().format(prefix=prefix)

    async def generate_report(self, prompt, context):
        del prompt
        self.report_contexts.append(context)
        requested_round = context.get("requested_review_round", 1)
        if requested_round == 1:
            return """
# 标题
> **核心观点**：中性判断。

## 一、行情回顾
价格震荡。

## 二、基本面分析
### 供给端
供给平稳。
### 需求端
需求平稳。
### 库存与持仓
库存平稳。

## 三、国际市场
国际市场平稳。

## 四、近期重要资讯
- 资讯 1

## 五、核心驱动因子
1. 因子一

## 六、风险提示
1. 政策变化
""".strip()
        return """
# 标题
> **核心观点**：中性判断，库存与需求暂未失衡。  
> **情绪**：中性 | **置信度**：中

## 一、行情回顾
价格在 13500 元/吨附近，价差 120 元/吨。（来源：CTP snapshot API）

## 二、基本面分析
### 供给端
供给平稳。（来源：AkShare structured commodity data）
### 需求端
需求平稳。（来源：AkShare structured commodity data）
### 库存与持仓
持仓数据已由 CTP 快照登记，库存暂无可核验数据。（来源：CTP snapshot API；AkShare structured commodity data）

## 三、国际市场
ICE 与美元波动温和。（来源：Yahoo Finance via yfinance）

## 四、近期重要资讯
- 资讯 1（来源：CTP snapshot API）

## 五、核心驱动因子
1. 因子一
2. 因子二

## 六、风险提示
1. 政策变化
2. 需求不及预期

本报告由AI自动生成，仅供参考，不构成投资建议。
""".strip()


class RecordingReportLLMClient:
    def __init__(self):
        self.report_contexts = []

    async def generate_report(self, prompt, context):
        del prompt
        self.report_contexts.append(context)
        return "# LLM研报\n\n本报告由AI自动生成，仅供参考，不构成投资建议。"


class AlwaysFailLLMClient(RevisionAwareLLMClient):
    async def generate_report(self, prompt, context):
        del prompt
        self.report_contexts.append(context)
        return """
# 标题
> **核心观点**：中性判断。

## 一、行情回顾
价格震荡。

## 二、基本面分析
### 供给端
供给平稳。
### 需求端
需求平稳。
### 库存与持仓
库存平稳。

## 三、国际市场
国际市场平稳。

## 四、近期重要资讯
- 资讯 1

## 五、核心驱动因子
1. 因子一

## 六、风险提示
1. 政策变化
""".strip()


class HybridLLMClient:
    is_live = True

    def __init__(self):
        self.analysis_contexts = []

    async def generate_analysis(self, prompt, context):
        del prompt
        self.analysis_contexts.append(context)
        return """
{
  "sentiment": "偏多",
  "confidence": "中",
  "core_view": "盘面定价偏强，但仍需保留边界意识。",
  "supply_view": "供给侧仍需等待直接验证数据，当前只能保留框架观察。",
  "demand_view": "需求端缺少直接验证数据，暂不扩写为确定结论。",
  "inventory_view": "库存逻辑仍待真实数据补齐，当前只能确认盘面活跃度。",
  "international_view": "国际联动先保留框架提醒，不展开数值判断。",
  "event_view": "最新快照与期限结构已经可核验，其余事件仍待补充。",
  "key_factor_views": [
    "盘面涨跌说明资金定价偏强。",
    "期限结构提示近端仍带谨慎色彩。",
    "交易活跃度说明盘面并非无量波动。",
    "研究边界需要被明确写出。"
  ],
  "risk_views": [
    "旧快照不能替代今日事实。",
    "缺少基本面数字时，盘面判断不能等同于产业链结论。",
    "若后续真实数据与盘面背离，观点需要修正。"
  ]
}
""".strip()

    async def generate_report(self, prompt, context):
        raise AssertionError("Hybrid mode should not call generate_report for deterministic writer path.")


class ShortHybridLLMClient(HybridLLMClient):
    async def generate_analysis(self, prompt, context):
        del prompt
        self.analysis_contexts.append(context)
        return """
{
  "sentiment": "偏多",
  "confidence": "中",
  "core_view": "盘面定价偏强，但仍需保留边界意识。",
  "supply_view": "供给侧仍需等待直接验证数据，当前只能保留框架观察。",
  "demand_view": "需求端缺少直接验证数据，暂不扩写为确定结论。",
  "inventory_view": "库存逻辑仍待真实数据补齐，当前只能确认盘面活跃度。",
  "international_view": "国际联动先保留框架提醒，不展开数值判断。",
  "event_view": "最新快照与期限结构已经可核验，其余事件仍待补充。",
  "key_factor_views": [
    "盘面涨跌说明资金定价偏强。",
    "期限结构提示近端仍带谨慎色彩。"
  ],
  "risk_views": [
    "旧快照不能替代今日事实。"
  ]
}
""".strip()


class GroundedDraftLLMClient(HybridLLMClient):
    async def generate_report(self, prompt, context):
        del prompt, context
        return """
# 沪金期货日报 — AU2606 [2026-04-10]

> **核心观点**：AU2606 偏多，但这里故意写入 999 这个证据包外数字。[F1]
> **情绪**：偏多 | **置信度**：中

## 一、结论先行
AU2606 基于已核验盘面事实维持偏多观察，但 999 不应通过校验。[F1]

## 二、盘面定价与期限结构
最新价 750，价差 -2。[F1][F2]

## 三、外盘、宏观与期现联动
COMEX黄金作为外盘参照。[F3]

## 四、基本面验证与缺口
当前仍有数据缺口。[G1]

## 五、核心驱动因子
1. 盘面偏强。[F1]

## 六、风险提示
1. 数据缺口可能影响判断。[G1]

## 七、数据来源与合规说明
本报告由AI自动生成，仅供参考，不构成投资建议。
""".strip()


class FakeCTPSource(DataSourceAdapter):
    source_type = "ctp_snapshot"

    async def fetch(self, request, params=None):
        del params
        return SourcePayload(
            source_type=self.source_type,
            summary="fake ctp",
            highlights=[
                "CTP快照显示 au2606 最新价 750，涨跌 1，涨跌幅 0.13%，更新时间 2026-04-10 15:00:00。",
                "当前可核验持仓量 100，成交量 200。",
                "au2606-au2612 当前价差 -2。",
            ],
            metrics={
                "主数据合约ID": "au2606",
                "主力合约参考价": "750",
                "主力合约买一": "749.8",
                "主力合约卖一": "750.2",
                "主力合约涨跌": "1",
                "主力合约涨跌幅": "0.13%",
                "主力合约持仓量": "100",
                "主力合约成交量": "200",
                "主力合约交易日": "2026-04-10",
                "主力合约更新时间": "2026-04-10 15:00:00",
                "次数据合约ID": "au2612",
                "次主力合约参考价": "752",
                "近月-远月价差": "-2",
            },
            sources=["CTP snapshot API"],
            raw_items=[
                {
                    "item_type": "snapshot",
                    "role": "primary",
                    "instrument_id": "au2606",
                    "trading_day": "2026-04-10",
                    "update_time": "2026-04-10 15:00:00",
                    "source": "test",
                },
                {
                    "item_type": "snapshot",
                    "role": "secondary",
                    "instrument_id": "au2612",
                    "trading_day": "2026-04-10",
                    "update_time": "2026-04-10 15:00:00",
                    "source": "test",
                },
            ],
        )


class FakeYahooSource(DataSourceAdapter):
    source_type = "yahoo_market"

    async def fetch(self, request, params=None):
        del request, params
        return SourcePayload(
            source_type=self.source_type,
            summary="fake yahoo",
            highlights=[
                "Yahoo Finance via yfinance 显示 COMEX黄金（GC=F）截至 2026-04-10 收盘价 2400，涨跌 12，涨跌幅 0.5%。"
            ],
            metrics={
                "外盘/宏观:COMEX黄金:收盘价": "2400美元/盎司",
                "外盘/宏观:COMEX黄金:涨跌": "12美元/盎司",
                "外盘/宏观:COMEX黄金:涨跌幅": "0.5%",
                "外盘/宏观:COMEX黄金:数据日期": "2026-04-10",
            },
            sources=["Yahoo Finance via yfinance"],
            raw_items=[
                {
                    "item_type": "external_market",
                    "role": "international_market",
                    "ticker": "GC=F",
                    "name": "COMEX黄金",
                    "as_of_date": "2026-04-10",
                    "close": "2400",
                    "change": "12",
                    "change_pct": "0.5%",
                    "unit": "美元/盎司",
                    "source": "Yahoo Finance via yfinance",
                    "stale": "false",
                }
            ],
        )


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.api_key_patcher = patch.object(llm_client_module.config, "ANTHROPIC_API_KEY", "")
        self.base_url_patcher = patch.object(llm_client_module.config, "ANTHROPIC_BASE_URL", "")
        self.api_key_patcher.start()
        self.base_url_patcher.start()

    def tearDown(self):
        self.base_url_patcher.stop()
        self.api_key_patcher.stop()

    def test_end_to_end_workflow(self):
        state = asyncio.run(run_research("CF", date.today()))
        self.assertTrue(state.report_draft)
        self.assertIn("## 一、行情回顾", state.report_draft)
        self.assertIn("## 六、风险提示", state.report_draft)
        self.assertIsNotNone(state.review_result)

    def test_low_code_variety_from_yaml(self):
        state = asyncio.run(run_research("M", date.today()))
        self.assertEqual(state.variety_code, "M")
        self.assertEqual(state.variety, "豆粕")
        self.assertIn("豆粕", state.report_draft)
        self.assertTrue(state.review_result.passed)

    def test_new_variety_from_yaml_uses_precious_metals_configuration(self):
        state = asyncio.run(run_research("AU", date.today()))
        self.assertEqual(state.variety_code, "AU")
        self.assertEqual(state.variety, "沪金")
        self.assertEqual(state.symbol, "AU2606")
        self.assertIn("沪金", state.report_draft)
        self.assertTrue(state.review_result.passed)

    def test_registry_scan_lists_all_expected_varieties(self):
        runtime = build_runtime()
        codes = runtime.variety_registry.list_codes()
        self.assertGreaterEqual(len(codes), 60)
        for code in ["AG", "AL", "AU", "CF", "CU", "LC", "M", "SC", "IF", "TF", "ZN"]:
            self.assertIn(code, codes)
        self.assertEqual(runtime.variety_registry.get("AU2610").code, "AU")
        self.assertEqual(runtime.variety_registry.get("A2605").code, "A")

    def test_run_research_persists_report_when_repository_is_configured(self):
        with TemporaryDirectory() as temp_dir:
            database_path = Path(temp_dir) / "reports.db"
            repository = SqlAlchemyReportRepository(f"sqlite+pysqlite:///{database_path}")
            repository.initialize_schema()
            try:
                with patch("futures_research.main.build_report_repository", return_value=repository):
                    state = asyncio.run(run_research("CF", date.today()))
                persisted_state = repository.get_workflow_state(state.run_id)
                self.assertIsNotNone(persisted_state)
                self.assertEqual(persisted_state.run_id, state.run_id)
                self.assertEqual(persisted_state.final_report.summary, state.final_report.summary)
                self.assertEqual(persisted_state.review_result.total_score, state.review_result.total_score)
            finally:
                repository.close()

    def test_workflow_retries_once_after_failed_review_and_passes(self):
        runtime = build_runtime()
        fake_llm = RevisionAwareLLMClient()
        runtime.llm_client = fake_llm
        workflow = build_workflow(runtime)

        initial_state = WorkflowState(
            symbol="CF2605",
            variety_code="CF",
            variety="棉花",
            target_date=date.today(),
            max_review_rounds=2,
        )
        with patch.object(config, "ANALYSIS_RENDER_MODE", "llm"), patch.object(config, "REPORT_RENDER_MODE", "llm"):
            result = asyncio.run(workflow.ainvoke(initial_state.model_dump()))
        final_state = WorkflowState.model_validate(result)

        self.assertEqual(final_state.review_round, 2)
        self.assertEqual(len(final_state.review_history), 2)
        self.assertTrue(final_state.review_result.passed)
        self.assertEqual(len(fake_llm.analysis_contexts), 2)
        self.assertEqual(len(fake_llm.report_contexts), 2)
        self.assertTrue(fake_llm.analysis_contexts[1]["review_feedback"])
        self.assertTrue(fake_llm.report_contexts[1]["blocking_issues"])

    def test_workflow_stops_after_max_review_rounds_when_report_keeps_failing(self):
        runtime = build_runtime()
        fake_llm = AlwaysFailLLMClient()
        runtime.llm_client = fake_llm
        workflow = build_workflow(runtime)

        initial_state = WorkflowState(
            symbol="CF2605",
            variety_code="CF",
            variety="棉花",
            target_date=date.today(),
            max_review_rounds=2,
        )
        with patch.object(config, "ANALYSIS_RENDER_MODE", "llm"), patch.object(config, "REPORT_RENDER_MODE", "llm"):
            result = asyncio.run(workflow.ainvoke(initial_state.model_dump()))
        final_state = WorkflowState.model_validate(result)

        self.assertEqual(final_state.review_round, 2)
        self.assertEqual(len(final_state.review_history), 2)
        self.assertFalse(final_state.review_result.passed)
        self.assertEqual(len(fake_llm.analysis_contexts), 2)
        self.assertEqual(len(fake_llm.report_contexts), 2)
        self.assertIn("缺少 AI 免责声明", final_state.review_result.blocking_issues)

    def test_hybrid_mode_uses_llm_for_analysis_brief_but_keeps_report_numbers_deterministic(self):
        runtime = build_runtime()
        fake_llm = HybridLLMClient()
        runtime.llm_client = fake_llm
        workflow = build_workflow(runtime)

        initial_state = WorkflowState(
            symbol="CF2605",
            variety_code="CF",
            variety="棉花",
            target_date=date.today(),
            max_review_rounds=2,
        )
        with patch.object(config, "ANALYSIS_RENDER_MODE", "hybrid"), patch.object(config, "REPORT_RENDER_MODE", "hybrid"):
            result = asyncio.run(workflow.ainvoke(initial_state.model_dump()))
        final_state = WorkflowState.model_validate(result)

        self.assertEqual(len(fake_llm.analysis_contexts), 1)
        self.assertIn("analysis_brief", final_state.raw_data)
        self.assertIn("盘面定价偏强", final_state.report_draft)
        self.assertIn("CTP snapshot API", final_state.report_draft)

    def test_request_context_can_override_report_render_mode_for_single_run(self):
        runtime = build_runtime()
        fake_llm = RecordingReportLLMClient()
        runtime.llm_client = fake_llm
        state = {
            "symbol": "CF2605",
            "variety_code": "CF",
            "target_date": date.today(),
            "analysis_result": "维持中性观察。",
            "raw_data": {
                "request_context": {"report_render_mode": "llm"},
                "metrics": {},
                "sources": [],
                "data_gaps": [],
            },
            "review_round": 0,
        }

        with patch.object(config, "REPORT_RENDER_MODE", "hybrid"):
            result = asyncio.run(write_node(state, runtime))

        self.assertEqual(result["report_draft"], "# LLM研报\n\n本报告由AI自动生成，仅供参考，不构成投资建议。")
        self.assertEqual(len(fake_llm.report_contexts), 1)
        self.assertEqual(fake_llm.report_contexts[0]["contract"], "CF2605")

    def test_hybrid_workflow_embeds_yahoo_external_numbers_deterministically(self):
        runtime = build_runtime()
        registry = DataSourceRegistry()
        registry.register(FakeCTPSource())
        registry.register(FakeYahooSource())
        runtime.data_source_registry = registry
        fake_llm = HybridLLMClient()
        runtime.llm_client = fake_llm
        workflow = build_workflow(runtime)

        initial_state = WorkflowState(
            symbol="AU2606",
            variety_code="AU",
            variety="沪金",
            target_date=date(2026, 4, 10),
            max_review_rounds=2,
        )
        with patch.object(config, "ANALYSIS_RENDER_MODE", "hybrid"), patch.object(config, "REPORT_RENDER_MODE", "hybrid"):
            result = asyncio.run(workflow.ainvoke(initial_state.model_dump()))
        final_state = WorkflowState.model_validate(result)

        self.assertEqual(len(fake_llm.analysis_contexts), 1)
        self.assertIn("external_market_facts", fake_llm.analysis_contexts[0]["fact_pack"])
        self.assertIn("COMEX黄金", final_state.report_draft)
        self.assertIn("2400美元/盎司", final_state.report_draft)
        self.assertIn("Yahoo Finance via yfinance", final_state.report_draft)
        self.assertTrue(final_state.review_result.passed)

    def test_hybrid_mode_pads_short_llm_factor_lists(self):
        runtime = build_runtime()
        registry = DataSourceRegistry()
        registry.register(FakeCTPSource())
        registry.register(FakeYahooSource())
        runtime.data_source_registry = registry
        fake_llm = ShortHybridLLMClient()
        runtime.llm_client = fake_llm
        workflow = build_workflow(runtime)

        initial_state = WorkflowState(
            symbol="AU2606",
            variety_code="AU",
            variety="沪金",
            target_date=date(2026, 4, 10),
            max_review_rounds=2,
        )
        with patch.object(config, "ANALYSIS_RENDER_MODE", "hybrid"), patch.object(config, "REPORT_RENDER_MODE", "hybrid"):
            result = asyncio.run(workflow.ainvoke(initial_state.model_dump()))
        final_state = WorkflowState.model_validate(result)

        self.assertEqual(len(fake_llm.analysis_contexts), 1)
        self.assertEqual(len(final_state.raw_data["analysis_brief"]["key_factor_views"]), 4)
        self.assertEqual(len(final_state.raw_data["analysis_brief"]["risk_views"]), 3)
        self.assertIn("研究边界需要被明确写出", final_state.report_draft)
        self.assertIn("Yahoo Finance via yfinance", final_state.report_draft)
        self.assertTrue(final_state.review_result.passed)

    def test_grounded_llm_marks_draft_when_evidence_validation_fails(self):
        runtime = build_runtime()
        registry = DataSourceRegistry()
        registry.register(FakeCTPSource())
        registry.register(FakeYahooSource())
        runtime.data_source_registry = registry
        runtime.llm_client = GroundedDraftLLMClient()
        workflow = build_workflow(runtime)

        initial_state = WorkflowState(
            symbol="AU2606",
            variety_code="AU",
            variety="沪金",
            target_date=date(2026, 4, 10),
            max_review_rounds=1,
        )
        with patch.object(config, "ANALYSIS_RENDER_MODE", "hybrid"), patch.object(config, "REPORT_RENDER_MODE", "grounded_llm"):
            result = asyncio.run(workflow.ainvoke(initial_state.model_dump()))
        final_state = WorkflowState.model_validate(result)

        self.assertIn("999 这个证据包外数字", final_state.report_draft)
        self.assertIn("未通过合规审查，卡在第四步", final_state.report_draft)
        self.assertIn("数字或百分比未出现在证据包：999", final_state.report_draft)
        self.assertFalse(final_state.review_result.passed)
        self.assertIn("grounded LLM 第四步合规审查未通过", final_state.review_result.blocking_issues)


if __name__ == "__main__":
    unittest.main()
