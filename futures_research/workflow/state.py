from __future__ import annotations

from typing import Any, Dict, List, Optional, TypedDict


class WorkflowGraphState(TypedDict, total=False):
    run_id: str
    symbol: str
    variety_code: str
    variety: str
    target_date: str
    current_step: str
    review_round: int
    max_review_rounds: int
    raw_data: Dict[str, Any]
    analysis_result: str
    report_draft: str
    review_result: Optional[Dict[str, Any]]
    review_history: List[Dict[str, Any]]
    final_report: Optional[Dict[str, Any]]
    data_sources_used: List[str]
    error: Optional[str]
