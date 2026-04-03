from __future__ import annotations

from typing import Any, Dict, Optional

from futures_research.models.review import ReviewResult
from futures_research.prompts.writer_prompt import (
    WRITER_SYSTEM_PROMPT,
    build_writer_user_prompt,
)
from futures_research.runtime import RuntimeContext


def _load_review_result(payload: Any) -> Optional[ReviewResult]:
    if payload is None:
        return None
    if isinstance(payload, ReviewResult):
        return payload
    return ReviewResult.model_validate(payload)


async def write_node(state: Dict[str, Any], runtime: RuntimeContext) -> Dict[str, Any]:
    variety_definition = runtime.variety_registry.get(state["variety_code"])
    review_result = _load_review_result(state.get("review_result"))
    next_round = int(state.get("review_round", 0)) + 1
    request_context = (state.get("raw_data") or {}).get("request_context", {})
    user_prompt = build_writer_user_prompt(
        variety_definition=variety_definition,
        prompt_repository=runtime.prompt_repository,
        analysis_result=state["analysis_result"],
        raw_data=state["raw_data"],
        review_result=review_result,
        next_round=next_round,
        request_context=request_context,
    )
    report_draft = await runtime.llm_client.generate_report(
        "%s\n\n%s" % (WRITER_SYSTEM_PROMPT, user_prompt),
        context={
            "variety_name": variety_definition.name,
            "contract": state["symbol"],
            "target_date": str(state["target_date"]),
            "key_factors": variety_definition.key_factors,
            "raw_data": state["raw_data"],
            "analysis_result": state["analysis_result"],
            "review_feedback": review_result.feedback if review_result else "",
            "blocking_issues": review_result.blocking_issues if review_result else [],
            "requested_review_round": next_round,
            "research_request": request_context,
        },
    )
    return {
        "current_step": "write",
        "report_draft": report_draft,
    }
