from __future__ import annotations

import asyncio
import json
from typing import Any

from report_review_agent.app import config
from report_review_agent.app.heuristics import HeuristicSnapshot
from report_review_agent.app.models import ImprovementAction, ParsedDocument

try:
    from anthropic import Anthropic
except ImportError:  # pragma: no cover
    Anthropic = None


class GuidanceGenerator:
    def __init__(self) -> None:
        self._client = None
        if config.REVIEW_AGENT_API_KEY and Anthropic:
            self._client = Anthropic(
                api_key=config.REVIEW_AGENT_API_KEY,
                base_url=config.REVIEW_AGENT_BASE_URL or None,
            )

    @property
    def is_live(self) -> bool:
        return self._client is not None

    async def generate(self, document: ParsedDocument, snapshot: HeuristicSnapshot) -> dict[str, Any]:
        if self.is_live:
            try:
                return await asyncio.to_thread(self._call_model, document, snapshot)
            except Exception:
                return self._fallback(snapshot)
        return self._fallback(snapshot)

    def _call_model(self, document: ParsedDocument, snapshot: HeuristicSnapshot) -> dict[str, Any]:
        prompt = """
You are an objective editorial quality reviewer for research reports.

Your job:
1. Read the uploaded report content.
2. Read the deterministic audit snapshot.
3. Do not change the provided score.
4. Produce concise, concrete revision guidance in JSON only.

Return JSON with this exact shape:
{
  "executive_summary": "string",
  "strengths": ["string"],
  "improvement_actions": [
    {
      "priority": 1,
      "title": "string",
      "action": "string",
      "target_sections": ["string"]
    }
  ],
  "suggested_outline": ["string"]
}

Rules:
- Be objective.
- Focus on rewrite instructions, not praise.
- Write all user-facing content in Simplified Chinese.
- Do not output markdown.
- Do not output any text outside JSON.
""".strip()

        message = self._client.messages.create(
            model=config.REVIEW_AGENT_MODEL,
            max_tokens=config.REVIEW_AGENT_MAX_TOKENS,
            temperature=config.REVIEW_AGENT_TEMPERATURE,
            messages=[
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "document_filename": document.filename,
                            "document_format": document.format,
                            "deterministic_review": {
                                "overall_score": snapshot.overall_score,
                                "status": snapshot.status,
                                "strengths": snapshot.strengths,
                                "findings": [item.model_dump() for item in snapshot.findings],
                                "dimension_scores": [item.model_dump() for item in snapshot.dimension_scores],
                                "improvement_actions": [item.model_dump() for item in snapshot.improvement_actions],
                            },
                            "document_excerpt": document.content[:10000],
                            "instructions": prompt,
                        },
                        ensure_ascii=False,
                    ),
                }
            ],
        )

        parts = [getattr(block, "text", "") for block in message.content]
        text = "\n".join(part for part in parts if part).strip()
        payload = json.loads(text)
        return {
            "executive_summary": payload.get("executive_summary", snapshot.executive_summary),
            "strengths": payload.get("strengths") or snapshot.strengths,
            "improvement_actions": payload.get("improvement_actions") or [item.model_dump() for item in snapshot.improvement_actions],
            "suggested_outline": payload.get("suggested_outline") or snapshot.suggested_outline,
        }

    def _fallback(self, snapshot: HeuristicSnapshot) -> dict[str, Any]:
        return {
            "executive_summary": snapshot.executive_summary,
            "strengths": snapshot.strengths,
            "improvement_actions": [item.model_dump() for item in snapshot.improvement_actions],
            "suggested_outline": snapshot.suggested_outline,
        }


def coerce_actions(raw_actions: list[dict[str, Any]] | None) -> list[ImprovementAction]:
    if not raw_actions:
        return []
    actions: list[ImprovementAction] = []
    for index, item in enumerate(raw_actions, start=1):
        try:
            actions.append(
                ImprovementAction(
                    priority=int(item.get("priority", index)),
                    title=str(item.get("title", f"Action {index}")).strip(),
                    action=str(item.get("action", "")).strip(),
                    target_sections=[str(value).strip() for value in item.get("target_sections", []) if str(value).strip()],
                )
            )
        except Exception:
            continue
    return actions
