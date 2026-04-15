from __future__ import annotations

import asyncio
import json
import re
import ssl
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional
from urllib.request import Request, urlopen

from futures_research import config
from futures_research.data_sources.base import DataSourceAdapter
from futures_research.models.source import DataFetchRequest, SourcePayload


@dataclass(frozen=True)
class QibaotuContract:
    key: str
    instrument_id: str
    exchange: str
    name: str = ""


class CTPSnapshotSource(DataSourceAdapter):
    source_type = "ctp_snapshot"

    _EXCHANGE_KEYS = {
        "CFFEX": "cffex",
        "CZCE": "czce",
        "DCE": "dce",
        "GFEX": "gfex",
        "INE": "ine",
        "SHFE": "shfe",
    }

    def __init__(self, base_url: str | None = None):
        self.base_url = (base_url or config.CTP_SNAPSHOT_BASE_URL).rstrip("/")
        self._ssl_context = self._build_ssl_context()

    async def fetch(self, request: DataFetchRequest, params: Dict[str, Any] | None = None) -> SourcePayload:
        del params
        errors: List[str] = []
        primary_snapshot = await self._resolve_best_snapshot(
            contract=request.contract,
            exchange=request.exchange,
            target_date=str(request.target_date),
            errors=errors,
        )

        secondary_snapshot = None
        for candidate_contract in request.contracts:
            if candidate_contract == request.contract:
                continue
            secondary_snapshot = await self._resolve_best_snapshot(
                contract=candidate_contract,
                exchange=request.exchange,
                target_date=str(request.target_date),
                errors=errors,
            )
            if secondary_snapshot is not None:
                break

        metrics: Dict[str, str] = {}
        highlights: List[str] = []
        raw_items: List[Dict[str, str]] = []
        data_gaps: List[str] = []
        summary = "未从 CTP 快照接口获取到可核验的盘面数据。"

        if primary_snapshot is not None:
            metrics.update(
                {
                    "主数据合约ID": primary_snapshot["instrument_id"],
                    "主力合约参考价": self._fmt(primary_snapshot.get("price")),
                    "主力合约买一": self._fmt(primary_snapshot.get("bid")),
                    "主力合约卖一": self._fmt(primary_snapshot.get("ask")),
                    "主力合约涨跌": self._fmt(primary_snapshot.get("change")),
                    "主力合约涨跌幅": self._fmt_pct(primary_snapshot.get("change_pct")),
                    "主力合约持仓量": self._fmt_int(primary_snapshot.get("open_interest")),
                    "主力合约成交量": self._fmt_int(primary_snapshot.get("volume")),
                    "主力合约最新逐笔成交量": self._fmt_int(primary_snapshot.get("recent_trade_volume")),
                    "主力合约成交额": self._fmt_int(primary_snapshot.get("turnover")),
                    "主力合约交易日": str(primary_snapshot.get("trading_day") or ""),
                    "主力合约更新时间": str(primary_snapshot.get("update_time") or ""),
                }
            )
            highlights.extend(
                [
                    "CTP快照显示 {instrument_id} 最新价 {price}，涨跌 {change}，涨跌幅 {change_pct}，更新时间 {update_time}。".format(
                        instrument_id=primary_snapshot["instrument_id"],
                        price=self._fmt(primary_snapshot.get("price")),
                        change=self._fmt(primary_snapshot.get("change")),
                        change_pct=self._fmt_pct(primary_snapshot.get("change_pct")),
                        update_time=primary_snapshot.get("update_time") or "未知",
                    ),
                    "当前可核验买一 {bid}，卖一 {ask}，成交额 {turnover}。".format(
                        bid=self._fmt(primary_snapshot.get("bid")),
                        ask=self._fmt(primary_snapshot.get("ask")),
                        turnover=self._fmt_int(primary_snapshot.get("turnover")),
                    ),
                ]
            )
            raw_items.append(self._snapshot_to_raw_item("primary", request.contract, primary_snapshot))
            summary = "已从 CTP 快照接口获取 {contract} 的实时盘面数据。".format(contract=request.contract)

        if secondary_snapshot is not None:
            spread = (primary_snapshot or {}).get("price")
            secondary_price = secondary_snapshot.get("price")
            metrics["次数据合约ID"] = secondary_snapshot["instrument_id"]
            metrics["次主力合约参考价"] = self._fmt(secondary_price)
            if spread is not None and secondary_price is not None:
                metrics["近月-远月价差"] = self._fmt(spread - secondary_price)
                highlights.append(
                    "{primary}-{secondary} 当前价差 {spread}。".format(
                        primary=(primary_snapshot or {}).get("instrument_id", request.contract),
                        secondary=secondary_snapshot["instrument_id"],
                        spread=self._fmt(spread - secondary_price),
                    )
                )
            raw_items.append(self._snapshot_to_raw_item("secondary", secondary_snapshot["instrument_id"], secondary_snapshot))

        if primary_snapshot is None and errors:
            data_gaps.append("CTP快照接口请求失败或返回空数据：{error}".format(error=errors[-1]))

        return SourcePayload(
            source_type=self.source_type,
            summary=summary,
            highlights=highlights,
            metrics=metrics,
            sources=["CTP snapshot API: {base}".format(base=self.base_url)],
            raw_items=raw_items,
            data_gaps=data_gaps,
        )

    async def _resolve_best_snapshot(
        self,
        *,
        contract: str,
        exchange: str,
        target_date: str,
        errors: List[str],
    ) -> Optional[Dict[str, Any]]:
        candidates = self._build_contract_candidates(contract, exchange)
        matches: List[Dict[str, Any]] = []
        for candidate in candidates:
            try:
                item = await asyncio.to_thread(self._fetch_qibaotu_snapshot, candidate)
            except Exception as exc:
                errors.append("{instrument}: {error}".format(instrument=candidate.instrument_id, error=exc))
                continue
            if item is not None:
                item["_queried_instrument"] = candidate.instrument_id
                matches.append(item)
        if not matches:
            return None
        return max(
            matches,
            key=lambda item: self._snapshot_score(
                item,
                expected_contract=contract,
                expected_exchange=exchange,
                target_date=target_date,
            ),
        )

    def _fetch_qibaotu_snapshot(self, contract: QibaotuContract) -> Optional[Dict[str, Any]]:
        trade_payload = self._post_json("/api/transaction/latestTrade", {"key": contract.key})
        ticker = ((trade_payload.get("data") or {}).get("tickerData") or {}) if trade_payload else {}
        if not self._has_value(ticker.get("lastPrice")):
            return None

        bill_payload = self._post_json("/api/transaction/billData", {"key": contract.key, "size": 5})
        bill = ((bill_payload.get("data") or {}).get("bill") or {}) if bill_payload else {}
        bid = self._first_price(bill.get("bids"))
        ask = self._first_price(bill.get("asks"))

        transactions_payload = self._post_json("/api/transaction/latestTransactionData", {"key": contract.key, "size": 20})
        trade_list = ((transactions_payload.get("data") or {}).get("tradeList") or []) if transactions_payload else []
        latest_trade = trade_list[0] if trade_list else {}
        timestamp = self._to_float(latest_trade.get("time"))
        update_time = self._format_timestamp(latest_trade.get("time"))
        trading_day = update_time[:10] if update_time else ""
        recent_volume = sum(self._to_float(item.get("volume")) or 0.0 for item in trade_list)

        return {
            "instrument_id": contract.instrument_id,
            "exchange": contract.exchange.upper(),
            "trading_day": trading_day,
            "update_time": update_time,
            "price": self._to_float(ticker.get("lastPrice")),
            "bid": bid,
            "ask": ask,
            "change": self._to_float(ticker.get("changeValue")),
            "change_pct": self._to_float(ticker.get("degree")),
            "open_interest": None,
            "volume": None,
            "recent_trade_volume": recent_volume or None,
            "turnover": self._to_float(ticker.get("turnoverFiat")),
            "open": self._to_float(ticker.get("open")),
            "high": self._to_float(ticker.get("high")),
            "low": self._to_float(ticker.get("low")),
            "timestamp": timestamp or 0.0,
            "source": "qibaotu_pc_api",
            "qibaotu_key": contract.key,
            "qibaotu_name": contract.name,
        }

    def _build_contract_candidates(self, contract: str, exchange: str) -> List[QibaotuContract]:
        normalized = contract.strip()
        exchange_key = self._exchange_key(exchange)
        candidates: List[QibaotuContract] = []

        def add(key: str, instrument_id: str | None = None, name: str = "") -> None:
            if not key:
                return
            resolved_instrument = instrument_id or self._instrument_from_key(key) or normalized
            candidate = QibaotuContract(key=key, instrument_id=resolved_instrument.upper(), exchange=exchange, name=name)
            if candidate not in candidates:
                candidates.append(candidate)

        if ":" in normalized:
            add(normalized.lower())
        if exchange_key:
            add("{symbol}:{exchange}".format(symbol=normalized.lower(), exchange=exchange_key))
            short_symbol = self._czce_short_symbol(normalized, exchange)
            if short_symbol:
                add("{symbol}:{exchange}".format(symbol=short_symbol.lower(), exchange=exchange_key))

        for item in self._search_contracts(normalized, exchange):
            key = str(item.get("key") or "")
            symbol = str(item.get("symbol") or "")
            name = str(item.get("name") or "")
            if key:
                add(key.lower(), instrument_id=symbol or None, name=name)
            if symbol and exchange_key:
                add("{symbol}:{exchange}".format(symbol=symbol.lower(), exchange=exchange_key), instrument_id=symbol, name=name)
        return candidates

    def _search_contracts(self, keyword: str, exchange: str) -> List[Dict[str, Any]]:
        try:
            payload = self._post_json(
                "/api/upgrade/market/search",
                {"key": keyword, "currPage": 1, "pageSize": 20},
            )
        except Exception:
            return []
        data = payload.get("data") or {}
        items = data.get("list") or []
        exchange_key = self._exchange_key(exchange)
        normalized_keyword = keyword.lower()
        keyword_is_contract = re.match(r"^[a-zA-Z]+\d+$", keyword) is not None
        filtered = []
        for item in items:
            item_exchange = str(item.get("exchangeKey") or "").lower()
            symbol = str(item.get("symbol") or "").lower()
            key = str(item.get("key") or "").lower()
            if exchange_key and item_exchange != exchange_key:
                continue
            if keyword_is_contract and symbol != normalized_keyword and self._instrument_from_key(key).lower() != normalized_keyword:
                continue
            if symbol == normalized_keyword or normalized_keyword in {key, self._instrument_from_key(key).lower()}:
                filtered.insert(0, item)
            else:
                filtered.append(item)
        return filtered

    def _post_json(self, path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        request = Request(
            "{base}{path}".format(base=self.base_url, path=path),
            data=json.dumps(payload).encode("utf-8"),
            headers=self._headers(),
            method="POST",
        )
        kwargs: Dict[str, Any] = {"timeout": config.CTP_REQUEST_TIMEOUT_SECONDS}
        if self._ssl_context is not None:
            kwargs["context"] = self._ssl_context
        with urlopen(request, **kwargs) as response:
            body = json.loads(response.read().decode("utf-8"))
        if not body.get("success"):
            raise RuntimeError("{path} returned {status}: {message}".format(
                path=path,
                status=body.get("status"),
                message=body.get("message") or "unknown error",
            ))
        return body

    def _headers(self) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if config.CTP_SNAPSHOT_AUTH_KEY:
            headers["x-qibaotu-key"] = config.CTP_SNAPSHOT_AUTH_KEY
        if config.CTP_SNAPSHOT_SKIP_CRYPTO:
            headers["x-skip-crypto"] = "1"
        if config.CTP_SNAPSHOT_SKIP_CHECK:
            headers["x-skip-check"] = "1"
        return headers

    def _build_ssl_context(self) -> ssl.SSLContext | None:
        if not config.CTP_SNAPSHOT_VERIFY_SSL:
            context = ssl.create_default_context()
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE
            return context
        try:
            import certifi
        except Exception:
            return None
        return ssl.create_default_context(cafile=certifi.where())

    def _snapshot_score(
        self,
        item: Dict[str, Any],
        *,
        expected_contract: str,
        expected_exchange: str,
        target_date: str,
    ) -> tuple:
        trading_day = str(item.get("trading_day") or "")
        expected_instrument = expected_contract.upper()
        actual_instrument = str(item.get("instrument_id") or "").upper()
        queried_instrument = str(item.get("_queried_instrument") or "").upper()
        return (
            trading_day == target_date,
            actual_instrument == expected_instrument,
            queried_instrument == expected_instrument,
            str(item.get("exchange") or "").upper() == expected_exchange.upper(),
            self._has_value(item.get("price")),
            float(item.get("timestamp") or 0.0),
        )

    def _snapshot_to_raw_item(self, role: str, requested_contract: str, snapshot: Dict[str, Any]) -> Dict[str, str]:
        return {
            "item_type": "snapshot",
            "role": role,
            "requested_contract": requested_contract,
            "instrument_id": str(snapshot.get("instrument_id") or ""),
            "exchange": str(snapshot.get("exchange") or ""),
            "trading_day": str(snapshot.get("trading_day") or ""),
            "update_time": str(snapshot.get("update_time") or ""),
            "price": self._fmt(snapshot.get("price")),
            "bid": self._fmt(snapshot.get("bid")),
            "ask": self._fmt(snapshot.get("ask")),
            "change": self._fmt(snapshot.get("change")),
            "change_pct": self._fmt_pct(snapshot.get("change_pct")),
            "open_interest": self._fmt_int(snapshot.get("open_interest")),
            "volume": self._fmt_int(snapshot.get("volume")),
            "recent_trade_volume": self._fmt_int(snapshot.get("recent_trade_volume")),
            "turnover": self._fmt_int(snapshot.get("turnover")),
            "open": self._fmt(snapshot.get("open")),
            "high": self._fmt(snapshot.get("high")),
            "low": self._fmt(snapshot.get("low")),
            "source": str(snapshot.get("source") or ""),
            "qibaotu_key": str(snapshot.get("qibaotu_key") or ""),
            "qibaotu_name": str(snapshot.get("qibaotu_name") or ""),
            "queried_instrument": str(snapshot.get("_queried_instrument") or ""),
        }

    def _exchange_key(self, exchange: str) -> str:
        return self._EXCHANGE_KEYS.get(exchange.upper(), exchange.lower())

    @staticmethod
    def _instrument_from_key(key: str) -> str:
        return key.split(":", 1)[0] if ":" in key else key

    @staticmethod
    def _czce_short_symbol(contract: str, exchange: str) -> str:
        match = re.match(r"^([A-Za-z]+)(\d+)$", contract.strip())
        if not match or exchange.upper() != "CZCE":
            return ""
        letters, digits = match.groups()
        if len(digits) == 4:
            return "{letters}{digits}".format(letters=letters, digits=digits[1:])
        return ""

    @staticmethod
    def _first_price(items: Any) -> Optional[float]:
        if not items:
            return None
        first = items[0]
        if isinstance(first, (list, tuple)) and first:
            return CTPSnapshotSource._to_float(first[0])
        if isinstance(first, dict):
            return CTPSnapshotSource._to_float(first.get("price"))
        return None

    @staticmethod
    def _format_timestamp(value: Any) -> str:
        number = CTPSnapshotSource._to_float(value)
        if number is None:
            return ""
        if number > 10_000_000_000:
            number = number / 1000
        return datetime.fromtimestamp(number).strftime("%Y-%m-%d %H:%M:%S")

    @staticmethod
    def _has_value(value: Any) -> bool:
        return value is not None and value != ""

    @staticmethod
    def _to_float(value: Any) -> Optional[float]:
        if value is None or value == "":
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _fmt(value: Any) -> str:
        if value is None or value == "":
            return "暂无"
        number = float(value)
        if number.is_integer():
            return str(int(number))
        return ("%.2f" % number).rstrip("0").rstrip(".")

    @staticmethod
    def _fmt_int(value: Any) -> str:
        if value is None or value == "":
            return "暂无"
        return "{:,}".format(int(float(value)))

    @staticmethod
    def _fmt_pct(value: Any) -> str:
        if value is None or value == "":
            return "暂无"
        return "{value}%".format(value=CTPSnapshotSource._fmt(value))
