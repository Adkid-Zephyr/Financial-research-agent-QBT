from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
VARIETIES_DIR = BASE_DIR / "varieties"
VARIETY_PROMPTS_DIR = VARIETIES_DIR / "prompts"
PROMPTS_DIR = BASE_DIR / "futures_research" / "prompts"
CTP_CONTRACT_CATALOG_PATH = BASE_DIR / "futures_research" / "catalogs" / "ctp_contract_catalog.yaml"
LOG_DIR = BASE_DIR / "logs"
MEMORY_DIR = BASE_DIR / "memory"
OUTPUT_DIR = BASE_DIR / "outputs"

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
ANTHROPIC_BASE_URL = os.getenv("ANTHROPIC_BASE_URL", "")
DATABASE_URL = os.getenv("DATABASE_URL", "")
CTP_SNAPSHOT_BASE_URL = os.getenv("CTP_SNAPSHOT_BASE_URL", "https://pc-api.qibaotu.com")
CTP_SNAPSHOT_AUTH_KEY = os.getenv("CTP_SNAPSHOT_AUTH_KEY", os.getenv("QIBAOTU_API_KEY", ""))
CTP_SNAPSHOT_SKIP_CRYPTO = os.getenv("CTP_SNAPSHOT_SKIP_CRYPTO", "true").lower() in {
    "1",
    "true",
    "yes",
}
CTP_SNAPSHOT_SKIP_CHECK = os.getenv("CTP_SNAPSHOT_SKIP_CHECK", "true").lower() in {
    "1",
    "true",
    "yes",
}
CTP_SNAPSHOT_VERIFY_SSL = os.getenv("CTP_SNAPSHOT_VERIFY_SSL", "true").lower() in {
    "1",
    "true",
    "yes",
}
CTP_REQUEST_TIMEOUT_SECONDS = float(os.getenv("CTP_REQUEST_TIMEOUT_SECONDS", "5"))
LLM_MODEL = os.getenv("LLM_MODEL", "claude-sonnet-4-20250514")
LLM_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "4096"))
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.2"))
ANALYSIS_RENDER_MODE = os.getenv("ANALYSIS_RENDER_MODE", "hybrid").lower()
REPORT_RENDER_MODE = os.getenv("REPORT_RENDER_MODE", "hybrid").lower()
SUPPORTED_REPORT_RENDER_MODES = {"hybrid", "llm", "grounded_llm"}
ENABLE_CTP_CONTRACT_CATALOG = os.getenv("ENABLE_CTP_CONTRACT_CATALOG", "true").lower() in {
    "1",
    "true",
    "yes",
}
ENABLE_ANTHROPIC_WEB_SEARCH = os.getenv("ENABLE_ANTHROPIC_WEB_SEARCH", "false").lower() in {
    "1",
    "true",
    "yes",
}
ENABLE_REAL_DATA_SOURCES = os.getenv("ENABLE_REAL_DATA_SOURCES", "false").lower() in {
    "1",
    "true",
    "yes",
}
ENABLE_YAHOO_MARKET_SOURCE = os.getenv("ENABLE_YAHOO_MARKET_SOURCE", "false").lower() in {
    "1",
    "true",
    "yes",
}
YAHOO_MARKET_MAX_STALE_DAYS = int(os.getenv("YAHOO_MARKET_MAX_STALE_DAYS", "5"))
YAHOO_MARKET_LOOKBACK_DAYS = int(os.getenv("YAHOO_MARKET_LOOKBACK_DAYS", "10"))
ENABLE_AKSHARE_COMMODITY_SOURCE = os.getenv("ENABLE_AKSHARE_COMMODITY_SOURCE", "false").lower() in {
    "1",
    "true",
    "yes",
}
AKSHARE_COMMODITY_MAX_STALE_DAYS = int(os.getenv("AKSHARE_COMMODITY_MAX_STALE_DAYS", "10"))
DEFAULT_REPORT_WORD_TARGET = int(os.getenv("DEFAULT_REPORT_WORD_TARGET", "1800"))
MIN_PASS_SCORE = float(os.getenv("MIN_PASS_SCORE", "75"))
MAX_REVIEW_ROUNDS = int(os.getenv("MAX_REVIEW_ROUNDS", "2"))


def normalize_report_render_mode(value: object, default: str | None = None) -> str:
    fallback = (default or REPORT_RENDER_MODE or "hybrid").lower()
    normalized = str(value or fallback).strip().lower()
    if normalized not in SUPPORTED_REPORT_RENDER_MODES:
        return fallback if fallback in SUPPORTED_REPORT_RENDER_MODES else "hybrid"
    return normalized
