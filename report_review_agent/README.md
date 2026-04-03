# Report Review Agent

An isolated subproject for reviewing AI-generated research reports without changing the existing `futures_research/` project.

## What it does

- Accepts uploaded `.md`, `.txt`, and text-based `.pdf` research reports
- Scores report quality with a deterministic rubric
- Produces objective findings and concrete improvement actions
- Optionally uses an Anthropic-compatible model to improve editorial suggestions
- Exports the review package as Markdown, PDF, and JSON
- Provides a simple frontend for upload and download

## Quick start

```bash
cd /Users/ann/Documents/投研agent
.venv/bin/python report_review_agent/run.py
```

Then open [http://127.0.0.1:8020](http://127.0.0.1:8020).

## Environment variables

The app can run with deterministic scoring only. If you want model-enhanced suggestions, set:

```bash
REVIEW_AGENT_API_KEY=...
REVIEW_AGENT_BASE_URL=https://coding.dashscope.aliyuncs.com/apps/anthropic
REVIEW_AGENT_MODEL=kimi-k2.5
```

It also falls back to `ANTHROPIC_API_KEY`, `ANTHROPIC_BASE_URL`, and `LLM_MODEL` if present.

## Layout

```text
report_review_agent/
├── app/
├── memory/
├── outputs/
├── tests/
├── ARCHITECTURE.md
├── requirements.txt
└── run.py
```
