# Report Review Agent Memory

## Goal
- Build a standalone review agent in a new folder only.
- Do not modify the existing `futures_research/` project architecture or files.
- Accept uploaded report files and generate an objective review package in Markdown and PDF.

## Current decisions
- The subproject lives in `report_review_agent/`.
- The scoring engine is deterministic and does not depend on an external model.
- An optional Anthropic-compatible model is used only for editorial guidance, not for score authority.
- Supported upload types in MVP: `.md`, `.txt`, `.pdf`.
- PDF support is limited to text-based PDFs; scanned OCR PDFs are out of scope for this first version.
- Frontend is a static HTML page served by FastAPI.
- Review outputs are stored per run under `report_review_agent/outputs/YYYY-MM-DD/<review_id>/`.

## Implemented modules
- `app/parsers.py`: upload parsing and file normalization
- `app/heuristics.py`: deterministic rubric and findings generation
- `app/llm.py`: optional editorial suggestion layer
- `app/service.py`: orchestration and artifact generation
- `app/exporters.py`: Markdown/PDF/JSON export
- `app/main.py`: FastAPI API and static frontend

## Validation plan
- Unit test deterministic reviewer behavior
- API test upload flow and artifact links
- Local smoke run with a real markdown report from the workspace

## Validation results
- `2026-04-03` ran `DATABASE_URL='' .venv/bin/python -m unittest discover -s report_review_agent/tests -v`
  - 4 tests passed
- `2026-04-03` ran `.venv/bin/python report_review_agent/run.py`
  - local server started at `http://127.0.0.1:8020`
- `2026-04-03` ran `GET /healthz`
  - returned `{"status":"ok","llm_guidance_live":true,...}`
- `2026-04-03` uploaded an existing markdown report through `POST /api/reviews`
  - returned score `81.0`, status `pass`, and valid artifact URLs
- `2026-04-03` uploaded an existing PDF report through `POST /api/reviews`
  - returned score `81.0`, status `pass`, and valid artifact URLs
- `2026-04-03` downloaded generated review artifacts
  - markdown preview returned expected Chinese review content
  - PDF artifact saved successfully with file size `5.1K`

## Next handoff focus
- If continuing, first read this file and `report_review_agent/ARCHITECTURE.md`.
- Then verify live upload flow, artifact downloads, and whether model-enhanced guidance is active.
