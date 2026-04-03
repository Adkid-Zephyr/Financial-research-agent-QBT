from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from report_review_agent.app.main import create_app


class ApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(create_app())

    def test_upload_markdown_review_returns_download_links(self):
        sample = """
# Sample Report

## Executive Summary
Cotton prices may remain resilient because inventories fell 3.2% week over week. (Source: Exchange)

## Analysis
Demand recovered because downstream operating rates rose to 74.5%. (Source: Industry Survey)

## Risks
Risk 1: export demand weakens.
Risk 2: policy changes arrive early.

## Conclusion
Base case remains constructive, but this is for reference only and does not constitute investment advice.
""".strip()

        response = self.client.post(
            "/api/reviews",
            files={"file": ("sample.md", sample.encode("utf-8"), "text/markdown")},
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertGreater(payload["overall_score"], 0)
        self.assertIn("markdown", payload["download_urls"])
        self.assertIn("pdf", payload["download_urls"])

    def test_upload_empty_file_is_rejected(self):
        response = self.client.post(
            "/api/reviews",
            files={"file": ("empty.md", b"", "text/markdown")},
        )
        self.assertEqual(response.status_code, 400)
