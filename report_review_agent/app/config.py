from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parents[1]
STATIC_DIR = BASE_DIR / "app" / "static"
OUTPUT_DIR = BASE_DIR / "outputs"
MEMORY_DIR = BASE_DIR / "memory"

REVIEW_AGENT_API_KEY = os.getenv("REVIEW_AGENT_API_KEY", os.getenv("ANTHROPIC_API_KEY", ""))
REVIEW_AGENT_BASE_URL = os.getenv("REVIEW_AGENT_BASE_URL", os.getenv("ANTHROPIC_BASE_URL", ""))
REVIEW_AGENT_MODEL = os.getenv("REVIEW_AGENT_MODEL", os.getenv("LLM_MODEL", "claude-sonnet-4-20250514"))
REVIEW_AGENT_MAX_TOKENS = int(os.getenv("REVIEW_AGENT_MAX_TOKENS", "2500"))
REVIEW_AGENT_TEMPERATURE = float(os.getenv("REVIEW_AGENT_TEMPERATURE", "0.1"))

PASS_THRESHOLD = float(os.getenv("REVIEW_AGENT_PASS_THRESHOLD", "75"))
REVISE_THRESHOLD = float(os.getenv("REVIEW_AGENT_REVISE_THRESHOLD", "55"))
MIN_PDF_TEXT_CHARS = int(os.getenv("REVIEW_AGENT_MIN_PDF_TEXT_CHARS", "80"))

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
MEMORY_DIR.mkdir(parents=True, exist_ok=True)
