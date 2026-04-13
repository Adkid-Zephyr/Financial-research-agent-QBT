from __future__ import annotations

import asyncio
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

from futures_research import config
from futures_research.data_sources.base import DataSourceAdapter
from futures_research.models.source import DataFetchRequest, SourcePayload


class YahooMarketSource(DataSourceAdapter):
    source_type = "yahoo_market"
    source_label = "Yahoo Finance via yfinance"

    async def fetch(self, request: DataFetchRequest, params: Dict[str, Any] | None = None) -> SourcePayload:
        params = params or {}
        if not config.ENABLE_YAHOO_MARKET_SOURCE:
            return SourcePayload(
                source_type=self.source_type,
                summary="Yahoo Finance 外盘/宏观数据源未启用。",
                data_gaps=["Yahoo Finance 外盘/宏观数据源未启用。"],
            )

        assets = params.get("assets") or []
        if not assets:
            return SourcePayload(
                source_type=self.source_type,
                summary="未配置 Yahoo Finance 外盘/宏观资产映射。",
                data_gaps=["未配置 Yahoo Finance 外盘/宏观资产映射。"],
            )

        try:
            self._load_yfinance()
        except Exception:
            return SourcePayload(
                source_type=self.source_type,
                summary="当前环境未安装 yfinance，外盘/宏观数据待补充。",
                data_gaps=["当前环境未安装 yfinance，外盘/宏观数据待补充。"],
            )

        max_stale_days = int(params.get("max_stale_days", config.YAHOO_MARKET_MAX_STALE_DAYS))
        lookback_days = int(params.get("lookback_days", config.YAHOO_MARKET_LOOKBACK_DAYS))
        target_date = request.target_date
        start_date = target_date - timedelta(days=lookback_days)
        end_date = target_date + timedelta(days=1)

        highlights: List[str] = []
        raw_items: List[Dict[str, str]] = []
        metrics: Dict[str, str] = {}
        data_gaps: List[str] = []

        for asset in assets:
            item = await self._fetch_asset(
                asset=asset,
                target_date=target_date,
                start_date=start_date,
                end_date=end_date,
                max_stale_days=max_stale_days,
            )
            if item is None:
                data_gaps.append("{name} 外盘/宏观数据暂无可核验数据。".format(name=self._asset_name(asset)))
                continue
            if item.get("stale") == "true":
                data_gaps.append(
                    "{name} 最新可得数据截至 {as_of_date}，与目标日期 {target_date} 相差超过 {max_stale_days} 天。".format(
                        name=item["name"],
                        as_of_date=item["as_of_date"],
                        target_date=target_date,
                        max_stale_days=max_stale_days,
                    )
                )
                continue
            raw_items.append(item)
            prefix = "外盘/宏观:{name}".format(name=item["name"])
            metrics["{prefix}:收盘价".format(prefix=prefix)] = self._with_unit(item["close"], item.get("unit", ""))
            metrics["{prefix}:涨跌".format(prefix=prefix)] = self._with_unit(item["change"], item.get("unit", ""))
            metrics["{prefix}:涨跌幅".format(prefix=prefix)] = item["change_pct"]
            metrics["{prefix}:数据日期".format(prefix=prefix)] = item["as_of_date"]
            highlights.append(
                "{source} 显示 {name}（{ticker}）截至 {as_of_date} 收盘价 {close}，涨跌 {change}，涨跌幅 {change_pct}。".format(
                    source=self.source_label,
                    name=item["name"],
                    ticker=item["ticker"],
                    as_of_date=item["as_of_date"],
                    close=self._with_unit(item["close"], item.get("unit", "")),
                    change=self._with_unit(item["change"], item.get("unit", "")),
                    change_pct=item["change_pct"],
                )
            )

        if raw_items:
            summary = "已获取 {count} 个 Yahoo Finance 外盘/宏观结构化行情。".format(count=len(raw_items))
            sources = [self.source_label]
        else:
            summary = "未获取到可用于正文引用的 Yahoo Finance 外盘/宏观结构化行情。"
            sources = []

        return SourcePayload(
            source_type=self.source_type,
            summary=summary,
            highlights=highlights,
            metrics=metrics,
            sources=sources,
            raw_items=raw_items,
            data_gaps=data_gaps,
        )

    async def _fetch_asset(
        self,
        *,
        asset: Dict[str, Any],
        target_date: date,
        start_date: date,
        end_date: date,
        max_stale_days: int,
    ) -> Optional[Dict[str, str]]:
        ticker = str(asset.get("ticker") or asset.get("code") or "").strip()
        if not ticker:
            return None
        try:
            rows = await asyncio.to_thread(self._fetch_history_rows, ticker, start_date, end_date)
        except Exception:
            return None
        if not rows:
            return None

        valid_rows = [row for row in rows if row["as_of_date"] <= target_date]
        if not valid_rows:
            return None
        latest = valid_rows[-1]
        previous = valid_rows[-2] if len(valid_rows) >= 2 else None
        stale_days = (target_date - latest["as_of_date"]).days
        close = latest["close"]
        previous_close = previous["close"] if previous else None
        change = None if previous_close in (None, 0) else close - previous_close
        change_pct = None if change is None or previous_close in (None, 0) else change / previous_close * 100
        return {
            "item_type": "external_market",
            "role": str(asset.get("role") or "macro_external"),
            "ticker": ticker,
            "name": self._asset_name(asset),
            "as_of_date": latest["as_of_date"].isoformat(),
            "close": self._fmt(close),
            "change": self._fmt(change),
            "change_pct": self._fmt_pct(change_pct),
            "unit": str(asset.get("unit") or ""),
            "source": self.source_label,
            "stale": "true" if stale_days > max_stale_days else "false",
        }

    def _fetch_history_rows(self, ticker: str, start_date: date, end_date: date) -> List[Dict[str, Any]]:
        yf = self._load_yfinance()
        history = yf.Ticker(ticker).history(
            start=start_date.isoformat(),
            end=end_date.isoformat(),
            interval="1d",
            auto_adjust=False,
        )
        if getattr(history, "empty", True):
            return []
        rows: List[Dict[str, Any]] = []
        for index, row in history.iterrows():
            close = row.get("Close")
            if close is None:
                continue
            as_of_date = self._coerce_date(index)
            if as_of_date is None:
                continue
            rows.append({"as_of_date": as_of_date, "close": float(close)})
        rows.sort(key=lambda item: item["as_of_date"])
        return rows

    @staticmethod
    def _load_yfinance():
        import yfinance as yf  # type: ignore

        return yf

    @staticmethod
    def _asset_name(asset: Dict[str, Any]) -> str:
        return str(asset.get("name") or asset.get("ticker") or asset.get("code") or "未知资产")

    @staticmethod
    def _coerce_date(value: Any) -> Optional[date]:
        if hasattr(value, "date"):
            return value.date()
        if isinstance(value, str):
            return datetime.fromisoformat(value[:10]).date()
        return None

    @staticmethod
    def _fmt(value: Any) -> str:
        if value is None:
            return "暂无"
        number = float(value)
        if number.is_integer():
            return str(int(number))
        return ("%.4f" % number).rstrip("0").rstrip(".")

    @classmethod
    def _fmt_pct(cls, value: Any) -> str:
        if value is None:
            return "暂无"
        return "{value}%".format(value=cls._fmt(value))

    @staticmethod
    def _with_unit(value: str, unit: str) -> str:
        return "{value}{unit}".format(value=value, unit=unit) if unit and value != "暂无" else value
