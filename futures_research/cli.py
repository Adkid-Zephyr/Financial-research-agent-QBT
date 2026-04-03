from __future__ import annotations

import argparse
import asyncio
from datetime import date

from futures_research.main import run_research
from futures_research.scheduler import run_batch_research
from futures_research.varieties import VarietyRegistry


def _parse_args():
    parser = argparse.ArgumentParser(description="Run futures research workflows.")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--symbol", help="Variety code like CF or exact contract like CF2605")
    group.add_argument("--symbols", help="Comma-separated symbols for batch runs, e.g. CF,M")
    group.add_argument("--all-varieties", action="store_true", help="Run all configured variety codes as one batch")
    parser.add_argument("--target-date", default=date.today().isoformat(), help="Target date in YYYY-MM-DD")
    parser.add_argument("--concurrency", type=int, default=2, help="Batch concurrency, defaults to 2")
    args = parser.parse_args()
    if not args.symbol and not args.symbols and not args.all_varieties:
        parser.error("one of --symbol, --symbols, or --all-varieties is required")
    return args


def _resolve_batch_symbols(args) -> list:
    if args.all_varieties:
        registry = VarietyRegistry()
        registry.scan()
        return registry.list_codes()
    return [item.strip() for item in args.symbols.split(",") if item.strip()]


def main() -> int:
    args = _parse_args()
    target_date = date.fromisoformat(args.target_date)
    if args.symbol:
        final_state = asyncio.run(run_research(symbol=args.symbol, target_date=target_date))
        report = final_state.final_report
        review = final_state.review_result
        if report is None or review is None:
            print("Workflow failed to produce a report.")
            return 1
        print(report.content)
        print("\n\n# 审核摘要")
        print("总分：%.1f / 100" % review.total_score)
        print("通过：%s" % ("是" if review.passed else "否"))
        print("反馈：%s" % review.feedback)
        return 0

    summary = asyncio.run(
        run_batch_research(
            symbols=_resolve_batch_symbols(args),
            target_date=target_date,
            concurrency=args.concurrency,
        )
    )
    print("# 批次摘要")
    print("目标日期：%s" % summary.target_date.isoformat())
    print("请求品种：%s" % ", ".join(summary.requested_symbols))
    print("总数：%s" % summary.total)
    print("通过：%s" % summary.passed)
    print("边缘通过：%s" % summary.marginal)
    print("失败：%s" % summary.failed)
    if summary.average_score is not None:
        print("平均分：%.2f" % summary.average_score)
    print("\n# 批次明细")
    for item in summary.items:
        score_text = "--" if item.final_score is None else "%.1f" % item.final_score
        print(
            "%s -> %s | %s | score=%s | run_id=%s%s"
            % (
                item.requested_symbol,
                item.resolved_symbol or "-",
                item.status,
                score_text,
                item.run_id or "-",
                "" if not item.error else " | error=%s" % item.error,
            )
        )
    return 0 if summary.failed == 0 else 1
