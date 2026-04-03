from __future__ import annotations

from langgraph.graph import END, StateGraph

from futures_research import config
from futures_research.agents.aggregator import aggregate_node
from futures_research.agents.analyzer import analyze_node
from futures_research.agents.reviewer import review_node
from futures_research.agents.writer import write_node
from futures_research.events import get_current_batch_id, publish_event
from futures_research.runtime import RuntimeContext
from futures_research.workflow.state import WorkflowGraphState


def _run_event_base(state: WorkflowGraphState) -> dict:
    return {
        "channel": "run",
        "run_id": state.get("run_id"),
        "batch_id": get_current_batch_id(),
        "resolved_symbol": state.get("symbol"),
        "variety_code": state.get("variety_code"),
        "variety": state.get("variety"),
        "target_date": state.get("target_date"),
    }


def _emit_step_started(state: WorkflowGraphState, step: str) -> None:
    publish_event(
        event_type="step_started",
        step=step,
        review_round=int(state.get("review_round", 0)),
        **_run_event_base(state),
    )


def _route_after_review(state: WorkflowGraphState) -> str:
    review_result = state.get("review_result") or {}
    if review_result.get("passed"):
        return "end"
    review_round = int(state.get("review_round", 0))
    max_review_rounds = int(state.get("max_review_rounds", config.MAX_REVIEW_ROUNDS))
    if review_round < max_review_rounds:
        return "analyze"
    return "end"


def build_workflow(runtime: RuntimeContext):
    graph = StateGraph(WorkflowGraphState)

    async def aggregate_step(state):
        _emit_step_started(state, "aggregate")
        return await aggregate_node(state, runtime)

    async def analyze_step(state):
        _emit_step_started(state, "analyze")
        return await analyze_node(state, runtime)

    async def write_step(state):
        _emit_step_started(state, "write")
        return await write_node(state, runtime)

    async def review_step(state):
        _emit_step_started(state, "review")
        result = await review_node(state, runtime)
        review_result = result.get("review_result") or {}
        publish_event(
            event_type="review_round_completed",
            step="review",
            review_round=review_result.get("round"),
            payload={
                "passed": review_result.get("passed", False),
                "total_score": review_result.get("total_score"),
                "blocking_issues": review_result.get("blocking_issues", []),
            },
            **_run_event_base(state),
        )
        return result

    graph.add_node("aggregate", aggregate_step)
    graph.add_node("analyze", analyze_step)
    graph.add_node("write", write_step)
    graph.add_node("review", review_step)

    graph.set_entry_point("aggregate")
    graph.add_edge("aggregate", "analyze")
    graph.add_edge("analyze", "write")
    graph.add_edge("write", "review")
    graph.add_conditional_edges(
        "review",
        _route_after_review,
        {
            "analyze": "analyze",
            "end": END,
        },
    )
    return graph.compile()
