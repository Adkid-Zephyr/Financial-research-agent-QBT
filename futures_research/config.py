from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
VARIETIES_DIR = BASE_DIR / "varieties"
VARIETY_PROMPTS_DIR = VARIETIES_DIR / "prompts"
PROMPTS_DIR = BASE_DIR / "futures_research" / "prompts"
LOG_DIR = BASE_DIR / "logs"
MEMORY_DIR = BASE_DIR / "memory"
OUTPUT_DIR = BASE_DIR / "outputs"

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
ANTHROPIC_BASE_URL = os.getenv("ANTHROPIC_BASE_URL", "")
DATABASE_URL = os.getenv("DATABASE_URL", "")
CTP_SNAPSHOT_BASE_URL = os.getenv("CTP_SNAPSHOT_BASE_URL", "http://192.168.152.69:8081")
CTP_REQUEST_TIMEOUT_SECONDS = float(os.getenv("CTP_REQUEST_TIMEOUT_SECONDS", "5"))
LLM_MODEL = os.getenv("LLM_MODEL", "claude-sonnet-4-20250514")
LLM_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "4096"))
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.2"))
ANALYSIS_RENDER_MODE = os.getenv("ANALYSIS_RENDER_MODE", "hybrid").lower()
REPORT_RENDER_MODE = os.getenv("REPORT_RENDER_MODE", "hybrid").lower()
ENABLE_ANTHROPIC_WEB_SEARCH = os.getenv("ENABLE_ANTHROPIC_WEB_SEARCH", "true").lower() in {
    "1",
    "true",
    "yes",
}
ENABLE_REAL_DATA_SOURCES = os.getenv("ENABLE_REAL_DATA_SOURCES", "false").lower() in {
    "1",
    "true",
    "yes",
}
DEFAULT_REPORT_WORD_TARGET = int(os.getenv("DEFAULT_REPORT_WORD_TARGET", "1800"))
MIN_PASS_SCORE = float(os.getenv("MIN_PASS_SCORE", "75"))
MAX_REVIEW_ROUNDS = int(os.getenv("MAX_REVIEW_ROUNDS", "2"))
