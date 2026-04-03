import asyncio
from datetime import date, datetime
import unittest
from unittest.mock import patch
from uuid import uuid4

from futures_research.llm import client as llm_client_module
from futures_research.models.report import ResearchReport
from futures_research.models.review import ReviewResult
from futures_research.models.state import WorkflowState
from futures_research.scheduler import ResearchScheduler, run_batch_research


def build_state(
    requested_symbol: str,
    *,
    contract: str,
    variety_code: str,
    variety: str,
    score: float,
    passed: bool,
    error: str = None,
) -> WorkflowState:
    review = ReviewResult(
        round=1,
        total_score=score,
        passed=passed,
        dimension_scores={"logic_chain": min(score, 25.0)},
        feedback="批次调度测试反馈",
        blocking_issues=[],
    )
    report = ResearchReport(
        id=uuid4(),
        symbol=contract,
        variety_code=variety_code,
        variety=variety,
        target_date=date(2026, 4, 1),
        generated_at=datetime(2026, 4, 1, 9, 0, 0),
        review_rounds=1,
        final_score=score,
        content="# 报告",
        summary="%s日报" % variety,
        sentiment="偏多" if passed else "中性",
        confidence="中",
        key_factors=["供需"],
        risk_points=["天气"],
        data_sources=["mock"],
    )
    return WorkflowState(
        run_id=uuid4(),
        symbol=contract,
        variety_code=variety_code,
        variety=variety,
        target_date=date(2026, 4, 1),
        current_step="review",
        review_round=1,
        raw_data={"requested_symbol": requested_symbol},
        analysis_result="分析完成",
        report_draft=report.content,
        review_result=review,
        review_history=[review],
        final_report=report,
        data_sources_used=["mock"],
        error=error,
    )


class SchedulerTests(unittest.TestCase):
    def setUp(self):
        self.api_key_patcher = patch.object(llm_client_module.config, "ANTHROPIC_API_KEY", "")
        self.base_url_patcher = patch.object(llm_client_module.config, "ANTHROPIC_BASE_URL", "")
        self.api_key_patcher.start()
        self.base_url_patcher.start()

    def tearDown(self):
        self.base_url_patcher.stop()
        self.api_key_patcher.stop()

    def test_run_batch_research_aggregates_scores(self):
        states = {
            "CF": build_state("CF", contract="CF2605", variety_code="CF", variety="棉花", score=88.0, passed=True),
            "M": build_state("M", contract="M2609", variety_code="M", variety="豆粕", score=78.0, passed=True),
        }

        async def fake_runner(symbol: str, target_date: date) -> WorkflowState:
            self.assertEqual(target_date, date(2026, 4, 1))
            return states[symbol]

        summary = asyncio.run(
            run_batch_research(
                symbols=["cf", "M", "cf"],
                target_date=date(2026, 4, 1),
                concurrency=8,
                runner=fake_runner,
            )
        )

        self.assertEqual(summary.requested_symbols, ["CF", "M"])
        self.assertEqual(summary.total, 2)
        self.assertEqual(summary.succeeded, 2)
        self.assertEqual(summary.failed, 0)
        self.assertEqual(summary.passed, 2)
        self.assertEqual(summary.marginal, 0)
        self.assertEqual(summary.concurrency, 2)
        self.assertEqual(summary.average_score, 83.0)
        self.assertEqual(summary.items[0].resolved_symbol, "CF2605")
        self.assertEqual(summary.items[1].resolved_symbol, "M2609")

    def test_scheduler_keeps_failed_runs_in_batch_summary(self):
        async def fake_runner(symbol: str, target_date: date) -> WorkflowState:
            if symbol == "M":
                raise RuntimeError("mock runner failure")
            return build_state(symbol, contract="CF2605", variety_code="CF", variety="棉花", score=74.0, passed=False)

        scheduler = ResearchScheduler(runner=fake_runner)
        summary = asyncio.run(scheduler.run_batch(["CF", "M"], date(2026, 4, 1), concurrency=2))

        self.assertEqual(summary.total, 2)
        self.assertEqual(summary.succeeded, 1)
        self.assertEqual(summary.failed, 1)
        self.assertEqual(summary.passed, 0)
        self.assertEqual(summary.marginal, 1)
        self.assertEqual(summary.items[0].status, "marginal")
        self.assertEqual(summary.items[1].status, "failed")
        self.assertEqual(summary.items[1].error, "mock runner failure")

    def test_batch_scheduler_runs_real_workflow_for_multiple_varieties(self):
        summary = asyncio.run(run_batch_research(["CF", "M"], date.today(), concurrency=2))

        self.assertEqual(summary.total, 2)
        self.assertEqual(summary.failed, 0)
        self.assertEqual(summary.succeeded, 2)
        self.assertEqual([item.requested_symbol for item in summary.items], ["CF", "M"])
        self.assertTrue(all(item.run_id is not None for item in summary.items))
        self.assertTrue(all(item.final_score is not None for item in summary.items))

    def test_batch_scheduler_runs_real_workflow_for_new_varieties(self):
        summary = asyncio.run(run_batch_research(["AU", "LC"], date.today(), concurrency=2))

        self.assertEqual(summary.total, 2)
        self.assertEqual(summary.failed, 0)
        self.assertEqual([item.requested_symbol for item in summary.items], ["AU", "LC"])
        self.assertEqual([item.resolved_symbol for item in summary.items], ["AU2606", "LC2607"])
        self.assertTrue(all(item.final_score is not None for item in summary.items))


if __name__ == "__main__":
    unittest.main()
