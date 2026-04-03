from __future__ import annotations

import unittest

from report_review_agent.app.heuristics import HeuristicReviewer
from report_review_agent.app.models import ParsedDocument


class HeuristicTests(unittest.TestCase):
    def setUp(self) -> None:
        self.reviewer = HeuristicReviewer()

    def test_heuristic_reviewer_flags_absolute_claims(self):
        document = ParsedDocument(
            filename="bad.md",
            format="markdown",
            content="""
# Report

## 核心观点
这个品种必涨，建议买入。
""".strip(),
            char_count=25,
        )
        result = self.reviewer.review(document)
        self.assertEqual(result.status, "fail")
        self.assertTrue(any(item.severity == "critical" for item in result.findings))


    def test_heuristic_reviewer_passes_well_formed_text(self):
        content = """
# Report

## Executive Summary
Inventories declined 2.4% while operating rates improved to 73.1%. (Source: Exchange)

## Analysis
Because supply tightened and demand remained stable, the base case improved.

## Risks
Demand could weaken and policy may shift.

## Conclusion
The base case is constructive. This report is for reference only and not investment advice.
""".strip()
        document = ParsedDocument(filename="good.md", format="markdown", content=content, char_count=len(content))
        result = self.reviewer.review(document)
        self.assertGreaterEqual(result.overall_score, 55)
        self.assertIn(result.status, {"revise", "pass"})
