# Report Review Agent Handoff 01

## Scope completed
- Created a brand new isolated subproject under `report_review_agent/`
- Did not modify the existing `futures_research/` project files
- Implemented a working upload-review-export MVP

## Public modules and entry points

- `report_review_agent/run.py`
  - `main() -> None`

- `report_review_agent.app.main`
  - `create_app() -> FastAPI`

- `report_review_agent.app.service`
  - `ReviewService.review_upload(filename: str, payload: bytes) -> StoredReviewBundle`
  - `ReviewService.load_review(review_id: str) -> StoredReviewBundle`
  - `ReviewService.artifact_path(review_id: str, kind: str)`

- `report_review_agent.app.parsers`
  - `parse_document(filename: str, payload: bytes) -> ParsedDocument`

- `report_review_agent.app.heuristics`
  - `HeuristicReviewer.review(document: ParsedDocument) -> HeuristicSnapshot`

## Key Pydantic structures

- `ParsedDocument`
  - `filename`
  - `format`
  - `content`
  - `char_count`
  - `page_count`
  - `metadata`

- `ReviewFinding`
  - `severity`
  - `title`
  - `detail`
  - `recommendation`
  - `evidence`
  - `target_sections`

- `ImprovementAction`
  - `priority`
  - `title`
  - `action`
  - `target_sections`

- `ReviewResult`
  - `review_id`
  - `created_at`
  - `filename`
  - `document_format`
  - `overall_score`
  - `status`
  - `passed`
  - `executive_summary`
  - `strengths`
  - `dimension_scores`
  - `findings`
  - `improvement_actions`
  - `suggested_outline`
  - `metadata`
  - `artifacts`

## API routes

- `GET /`
  - upload frontend
- `GET /healthz`
  - health check
- `POST /api/reviews`
  - upload one file and create review package
- `GET /api/reviews/{review_id}`
  - read one saved review summary
- `GET /api/reviews/{review_id}/artifacts/{kind}`
  - download `markdown`, `pdf`, `json`, or `source`

## Storage layout

```text
report_review_agent/outputs/YYYY-MM-DD/<review_id>/
├── review.json
├── review.md
├── review.pdf
└── source.<ext>
```

## Current limitations
- PDF parser only supports text-based PDFs
- No OCR for scanned image PDFs
- No DOCX support yet
- Deterministic scoring is authoritative; LLM only improves wording of guidance

## Local run command

```bash
cd /Users/ann/Documents/投研agent
.venv/bin/python report_review_agent/run.py
```

Open:

```text
http://127.0.0.1:8020
```

## Next thread prompt

继续 `report_review_agent` 子项目。先阅读 `/Users/ann/Documents/投研agent/report_review_agent/memory/PROJECT_MEMORY.md`、`/Users/ann/Documents/投研agent/report_review_agent/memory/HANDOFF_01.md` 和 `/Users/ann/Documents/投研agent/report_review_agent/ARCHITECTURE.md`，然后在不改动现有 `futures_research/` 项目的前提下，继续增强这个独立评审 Agent。优先方向：1）增加 DOCX 与 OCR 能力；2）优化评分维度与行业化模板；3）支持“评审后自动生成修订版草案”；4）继续把新的决策、日志与验收结果写回 `report_review_agent/memory/`。
