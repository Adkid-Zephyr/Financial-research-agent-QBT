from datetime import date, datetime
from pathlib import Path
from tempfile import TemporaryDirectory
import threading
import unittest
from uuid import uuid4

from fastapi.testclient import TestClient

from futures_research.api import create_app
from futures_research.models.report import ResearchReport
from futures_research.models.review import ReviewResult
from futures_research.models.state import WorkflowState
from futures_research.storage import SqlAlchemyReportRepository


def build_sample_state() -> WorkflowState:
    review = ReviewResult(
        round=1,
        total_score=86.0,
        passed=True,
        dimension_scores={"logic_chain": 20.0},
        feedback="结构完整，可进入后续发布或存储环节。",
        blocking_issues=[],
    )
    report = ResearchReport(
        id=uuid4(),
        symbol="CF2609",
        variety_code="CF",
        variety="棉花",
        target_date=date(2026, 4, 1),
        generated_at=datetime(2026, 4, 1, 9, 30, 0),
        review_rounds=1,
        final_score=86.0,
        content="# 棉花日报\n\n## 六、风险提示\n1. 天气",
        summary="郑棉短期维持震荡偏强。",
        sentiment="偏多",
        confidence="中",
        key_factors=["库存去化"],
        risk_points=["天气扰动"],
        data_sources=["mock"],
    )
    return WorkflowState(
        run_id=uuid4(),
        symbol="CF2609",
        variety_code="CF",
        variety="棉花",
        target_date=date(2026, 4, 1),
        current_step="review",
        review_round=1,
        raw_data={"sources": ["mock"], "metrics": {"basis": "-120"}},
        analysis_result="供需边际改善。",
        report_draft=report.content,
        review_result=review,
        review_history=[review],
        final_report=report,
        data_sources_used=["mock"],
    )


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = TemporaryDirectory()
        database_path = Path(self.temp_dir.name) / "reports.db"
        self.repository = SqlAlchemyReportRepository(f"sqlite+pysqlite:///{database_path}")
        self.repository.initialize_schema()
        self.sample_state = build_sample_state()
        self.repository.save_workflow_state(self.sample_state)
        self.client = TestClient(create_app(self.repository))

    def tearDown(self):
        self.client.close()
        self.repository.close()
        self.temp_dir.cleanup()

    def test_list_reports(self):
        response = self.client.get("/reports", params={"variety_code": "CF"})
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(len(payload), 1)
        self.assertEqual(payload[0]["symbol"], "CF2609")
        self.assertTrue(payload[0]["review_passed"])
        self.assertIn("generated_at", payload[0])
        self.assertIn("estimated_tokens", payload[0])

    def test_get_report_detail(self):
        response = self.client.get(f"/reports/{self.sample_state.run_id}")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["run_id"], str(self.sample_state.run_id))
        self.assertEqual(payload["final_report"]["summary"], "郑棉短期维持震荡偏强。")
        self.assertEqual(payload["review_result"]["total_score"], 86.0)

    def test_frontend_root_page(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("期货投研 Agent 测试控制台", response.text)
        self.assertEqual(response.headers["cache-control"], "no-store, no-cache, must-revalidate, max-age=0")

    def test_healthz_exposes_llm_status(self):
        response = self.client.get("/healthz")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("llm_model", payload)
        self.assertIn("llm_base_url", payload)
        self.assertIn("started_at", payload)
        self.assertIn("process_id", payload)

    def test_trigger_single_run(self):
        called = threading.Event()
        received = {}

        async def fake_runner(symbol, target_date):
            received["symbol"] = symbol
            received["target_date"] = target_date
            called.set()
            return self.sample_state

        client = TestClient(create_app(self.repository))
        try:
            client.app.state.run_single = fake_runner

            response = client.post("/runs", json={"symbol": "cf", "target_date": "2026-04-01"})
            self.assertEqual(response.status_code, 202)
            self.assertEqual(response.json()["requested_symbol"], "CF")
            self.assertTrue(called.wait(2))
            self.assertEqual(received["symbol"], "CF")
            self.assertEqual(received["target_date"], date(2026, 4, 1))
        finally:
            client.close()

    def test_trigger_batch_run(self):
        called = threading.Event()
        received = {}

        async def fake_batch_runner(symbols, target_date, concurrency):
            received["symbols"] = symbols
            received["target_date"] = target_date
            received["concurrency"] = concurrency
            called.set()
            from futures_research.models.batch import BatchResearchSummary

            return BatchResearchSummary(
                batch_id=uuid4(),
                target_date=target_date,
                requested_symbols=symbols,
                started_at=datetime(2026, 4, 1, 9, 0, 0),
                completed_at=datetime(2026, 4, 1, 9, 1, 0),
                concurrency=concurrency,
                total=len(symbols),
                succeeded=len(symbols),
                failed=0,
                passed=len(symbols),
                marginal=0,
                average_score=88.0,
                items=[],
            )

        client = TestClient(create_app(self.repository))
        try:
            client.app.state.run_batch = fake_batch_runner

            response = client.post(
                "/batches",
                json={"symbols": ["cf", "m"], "target_date": "2026-04-01", "concurrency": 3},
            )
            self.assertEqual(response.status_code, 202)
            self.assertEqual(response.json()["requested_symbols"], ["CF", "M"])
            self.assertTrue(called.wait(2))
            self.assertEqual(received["symbols"], ["CF", "M"])
            self.assertEqual(received["target_date"], date(2026, 4, 1))
            self.assertEqual(received["concurrency"], 3)
        finally:
            client.close()

    def test_delete_single_report(self):
        response = self.client.delete(f"/reports/{self.sample_state.run_id}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["deleted"], 1)
        self.assertIsNone(self.repository.get_workflow_state(self.sample_state.run_id))

    def test_delete_reports_batch(self):
        second_state = build_sample_state()
        self.repository.save_workflow_state(second_state)

        response = self.client.post(
            "/reports/delete-batch",
            json={"run_ids": [str(self.sample_state.run_id), str(second_state.run_id)]},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["deleted"], 2)
        self.assertIsNone(self.repository.get_workflow_state(self.sample_state.run_id))
        self.assertIsNone(self.repository.get_workflow_state(second_state.run_id))


if __name__ == "__main__":
    unittest.main()
