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

    def test_ask_report_uses_saved_report_sources(self):
        response = self.client.post(
            f"/reports/{self.sample_state.run_id}/ask",
            json={"question": "这份报告的数据来源是什么？"},
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("已登记的结构化来源", payload["answer"])
        self.assertEqual(payload["source_refs"], ["mock"])

    def test_frontend_root_page(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("问一句，得到一份有数据边界的期货日报", response.text)
        self.assertIn("contract-select", response.text)
        self.assertIn("/admin", response.text)
        self.assertEqual(response.headers["cache-control"], "no-store, no-cache, must-revalidate, max-age=0")

    def test_admin_page_keeps_existing_workbench(self):
        response = self.client.get("/admin")
        self.assertEqual(response.status_code, 200)
        self.assertIn("期货投研 Agent 测试控制台", response.text)
        self.assertIn("batch-run-form", response.text)
        self.assertIn("admin-contract-select", response.text)
        self.assertEqual(response.headers["cache-control"], "no-store, no-cache, must-revalidate, max-age=0")

    def test_healthz_exposes_llm_status(self):
        response = self.client.get("/healthz")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("llm_model", payload)
        self.assertIn("llm_base_url", payload)
        self.assertIn("started_at", payload)
        self.assertIn("process_id", payload)

    def test_list_varieties_exposes_configured_contracts(self):
        response = self.client.get("/varieties")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        cf = next(item for item in payload if item["code"] == "CF")
        self.assertEqual(cf["default_contract"], "CF2605")
        self.assertIn("CF2609", cf["contracts"])
        au = next(item for item in payload if item["code"] == "AU")
        self.assertIn("AU2604", au["contracts"])
        sc = next(item for item in payload if item["code"] == "SC")
        self.assertEqual(sc["exchange"], "INE")
        self.assertIn("SC2812", sc["contracts"])

    def test_trigger_single_run(self):
        called = threading.Event()
        received = {}

        async def fake_runner(symbol, target_date, research_profile=None):
            received["symbol"] = symbol
            received["target_date"] = target_date
            received["research_profile"] = research_profile
            called.set()
            return self.sample_state

        client = TestClient(create_app(self.repository))
        try:
            client.app.state.run_single = fake_runner

            response = client.post(
                "/runs",
                json={
                    "symbol": "cf",
                    "target_date": "2026-04-01",
                    "research_profile": {"persona": "hedging", "user_focus": "关注基差"},
                },
            )
            self.assertEqual(response.status_code, 202)
            self.assertEqual(response.json()["requested_symbol"], "CF")
            self.assertEqual(response.json()["selected_report_render_mode"], "hybrid")
            self.assertTrue(called.wait(2))
            self.assertEqual(received["symbol"], "CF")
            self.assertEqual(received["target_date"], date(2026, 4, 1))
            self.assertEqual(received["research_profile"]["persona"], "hedging")
            self.assertNotIn("report_render_mode", received["research_profile"])
        finally:
            client.close()

    def test_trigger_single_run_accepts_report_render_mode(self):
        called = threading.Event()
        received = {}

        async def fake_runner(symbol, target_date, research_profile=None):
            received["symbol"] = symbol
            received["target_date"] = target_date
            received["research_profile"] = research_profile
            called.set()
            return self.sample_state

        client = TestClient(create_app(self.repository))
        try:
            client.app.state.run_single = fake_runner

            response = client.post(
                "/runs",
                json={
                    "symbol": "au",
                    "contract": "AU2610",
                    "target_date": "2026-04-01",
                    "report_render_mode": "grounded_llm",
                    "research_profile": {"persona": "institution"},
                },
            )
            self.assertEqual(response.status_code, 202)
            self.assertEqual(response.json()["selected_contract"], "AU2610")
            self.assertEqual(response.json()["selected_report_render_mode"], "grounded_llm")
            self.assertTrue(called.wait(2))
            self.assertEqual(received["symbol"], "AU2610")
            self.assertEqual(received["research_profile"]["report_render_mode"], "grounded_llm")
        finally:
            client.close()

    def test_trigger_single_run_rejects_unknown_report_render_mode(self):
        response = self.client.post(
            "/runs",
            json={"symbol": "cf", "target_date": "2026-04-01", "report_render_mode": "freehand"},
        )
        self.assertEqual(response.status_code, 422)

    def test_trigger_single_run_accepts_selected_contract(self):
        called = threading.Event()
        received = {}

        async def fake_runner(symbol, target_date, research_profile=None):
            received["symbol"] = symbol
            received["target_date"] = target_date
            received["research_profile"] = research_profile
            called.set()
            return self.sample_state

        client = TestClient(create_app(self.repository))
        try:
            client.app.state.run_single = fake_runner

            response = client.post(
                "/runs",
                json={"symbol": "cf", "contract": "cf2609", "target_date": "2026-04-01"},
            )
            self.assertEqual(response.status_code, 202)
            self.assertEqual(response.json()["requested_symbol"], "CF")
            self.assertEqual(response.json()["selected_contract"], "CF2609")
            self.assertTrue(called.wait(2))
            self.assertEqual(received["symbol"], "CF2609")
        finally:
            client.close()

    def test_trigger_single_run_accepts_non_default_catalog_contract(self):
        called = threading.Event()
        received = {}

        async def fake_runner(symbol, target_date, research_profile=None):
            received["symbol"] = symbol
            received["target_date"] = target_date
            received["research_profile"] = research_profile
            called.set()
            return self.sample_state

        client = TestClient(create_app(self.repository))
        try:
            client.app.state.run_single = fake_runner

            response = client.post(
                "/runs",
                json={"symbol": "AG", "contract": "AG2607", "target_date": "2026-04-01"},
            )
            self.assertEqual(response.status_code, 202)
            self.assertEqual(response.json()["requested_symbol"], "AG")
            self.assertEqual(response.json()["selected_contract"], "AG2607")
            self.assertTrue(called.wait(2))
            self.assertEqual(received["symbol"], "AG2607")
        finally:
            client.close()

    def test_trigger_single_run_rejects_unknown_selected_contract(self):
        response = self.client.post(
            "/runs",
            json={"symbol": "cf", "contract": "CF9999", "target_date": "2026-04-01"},
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("Available contracts", response.json()["detail"])

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
