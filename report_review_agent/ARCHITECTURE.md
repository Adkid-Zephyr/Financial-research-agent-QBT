# Report Review Agent Architecture

## Goal

Build a standalone report-reviewing agent that can objectively evaluate research reports from any source and return a structured review package with actionable improvement guidance.

## Constraints

- Must live in a new folder and not modify the existing `futures_research/` architecture
- Must accept at least Markdown and PDF uploads
- Must remain useful even when no external model is available
- Must offer a simple frontend upload entry point
- Must export review results as Markdown and PDF

## Design choice

This subproject uses a two-layer review pipeline:

1. Deterministic review engine
   - Handles file parsing
   - Computes objective rubric scores
   - Detects structural, evidence, risk, and compliance issues
   - Produces stable findings and pass/revise/fail status

2. Optional LLM editorial layer
   - Refines executive summary
   - Generates concise strengths
   - Suggests a rewrite plan and improved outline
   - Never overrides the deterministic score

This keeps scoring objective while still benefiting from model-generated editing guidance.

## Review flow

```text
Upload file
  -> parse document
  -> normalize text
  -> run deterministic rubric
  -> optional LLM editorial guidance
  -> assemble review package
  -> export markdown/json/pdf
  -> return API response and download links
```

## Rubric

Total score: 100

- Structure completeness: 20
- Evidence traceability: 25
- Reasoning clarity: 20
- Risk balance: 15
- Compliance and objectivity: 20

Blocking logic:

- Absolute certainty language around market direction or outcomes
- Explicit buy/sell/should-do advice
- Empty or unreadable upload

Status:

- `pass`: score >= 75 and no blocking issue
- `revise`: 55 <= score < 75 and no blocking issue
- `fail`: score < 55 or any blocking issue

## File compatibility

- `.md`: UTF-8/GBK tolerant decoding
- `.txt`: UTF-8/GBK tolerant decoding
- `.pdf`: text extraction via `pypdf`

Current PDF limitation:

- Scanned image PDFs are not OCRed in this MVP
- If extraction yields too little text, the app will tell the user the PDF is likely image-only

## Storage

Each review is stored under:

```text
report_review_agent/outputs/YYYY-MM-DD/<review_id>/
```

Artifacts:

- `source.<ext>`
- `review.md`
- `review.pdf`
- `review.json`

## Frontend

A simple static HTML page is served by FastAPI:

- upload one file
- show score, status, findings, actions
- download Markdown/PDF/JSON artifacts

## Future-safe extension points

- OCR parser for scanned PDFs
- DOCX parser
- custom rubrics by domain
- side-by-side rewritten draft generation
- human feedback loop and review history
