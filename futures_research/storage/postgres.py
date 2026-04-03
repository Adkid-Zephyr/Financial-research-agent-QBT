from __future__ import annotations

from sqlalchemy import JSON, Column, Date, DateTime, Float, Integer, MetaData, String, Table, Text, create_engine
from sqlalchemy.engine import Engine

metadata = MetaData()

research_reports = Table(
    "research_reports",
    metadata,
    Column("run_id", String(36), primary_key=True),
    Column("report_id", String(36), nullable=True),
    Column("symbol", String(32), nullable=False, index=True),
    Column("variety_code", String(16), nullable=False, index=True),
    Column("variety", String(64), nullable=False),
    Column("target_date", Date, nullable=False, index=True),
    Column("current_step", String(32), nullable=False),
    Column("review_round", Integer, nullable=False),
    Column("max_review_rounds", Integer, nullable=False),
    Column("generated_at", DateTime, nullable=True, index=True),
    Column("final_score", Float, nullable=True),
    Column("summary", Text, nullable=True),
    Column("sentiment", String(16), nullable=True),
    Column("confidence", String(16), nullable=True),
    Column("report_draft", Text, nullable=False),
    Column("analysis_result", Text, nullable=False),
    Column("raw_data", JSON, nullable=False),
    Column("review_result", JSON, nullable=True),
    Column("review_history", JSON, nullable=False),
    Column("final_report", JSON, nullable=True),
    Column("key_factors", JSON, nullable=False),
    Column("risk_points", JSON, nullable=False),
    Column("data_sources", JSON, nullable=False),
    Column("data_sources_used", JSON, nullable=False),
    Column("error", Text, nullable=True),
)


def create_database_engine(database_url: str) -> Engine:
    return create_engine(database_url, future=True)


def initialize_database(engine: Engine) -> None:
    metadata.create_all(engine)
