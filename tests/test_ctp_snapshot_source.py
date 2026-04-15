import asyncio
from datetime import date, datetime
import unittest
from unittest.mock import patch

from futures_research import config
from futures_research.data_sources.ctp_snapshot_source import CTPSnapshotSource
from futures_research.models.source import DataFetchRequest


def _request():
    return DataFetchRequest(
        variety_code="AU",
        variety_name="沪金",
        contract="AU2606",
        contracts=["AU2606", "AU2612"],
        target_date=date(2026, 4, 15),
        exchange="SHFE",
        key_factors=[],
        news_keywords=[],
    )


def _soymeal_request():
    return DataFetchRequest(
        variety_code="M",
        variety_name="豆粕",
        contract="M2605",
        contracts=["M2605"],
        target_date=date(2026, 4, 15),
        exchange="DCE",
        key_factors=[],
        news_keywords=[],
    )


class CTPSnapshotSourceTests(unittest.TestCase):
    def test_build_candidates_prefers_direct_qibaotu_contract_key(self):
        source = CTPSnapshotSource(base_url="https://pc-api.qibaotu.com")

        with patch.object(
            source,
            "_search_contracts",
            return_value=[{"key": "aumain:shfe", "symbol": "au2606", "name": "沪金主连"}],
        ):
            candidates = source._build_contract_candidates("AU2606", "SHFE")

        self.assertEqual(candidates[0].key, "au2606:shfe")
        self.assertEqual(candidates[0].instrument_id, "AU2606")
        self.assertIn("aumain:shfe", [candidate.key for candidate in candidates])

    def test_fetch_maps_qibaotu_trade_bill_and_transaction_payloads(self):
        source = CTPSnapshotSource(base_url="https://pc-api.qibaotu.com")
        timestamp = int(datetime(2026, 4, 15, 14, 30, 0).timestamp())

        def fake_post_json(path, payload):
            if path == "/api/upgrade/market/search":
                return {"success": True, "data": {"list": []}}
            if path == "/api/transaction/latestTrade":
                if payload["key"] == "au2606:shfe":
                    return {
                        "success": True,
                        "data": {
                            "tickerData": {
                                "lastPrice": "1065.62",
                                "changeValue": "19.58",
                                "degree": "1.87",
                                "high": "1070.92",
                                "low": "1050",
                                "open": "1050",
                                "turnoverFiat": "192717785600",
                            }
                        },
                    }
                return {"success": True, "data": {"tickerData": {}}}
            if path == "/api/transaction/billData":
                return {
                    "success": True,
                    "data": {
                        "bill": {
                            "asks": [["1065.82", "4"]],
                            "bids": [["1065.62", "1"]],
                        }
                    },
                }
            if path == "/api/transaction/latestTransactionData":
                return {
                    "success": True,
                    "data": {
                        "tradeList": [
                            {"side": "buy", "price": "1065.96", "volume": "6", "interestChg": "0", "time": timestamp},
                            {"side": "sell", "price": "1065.92", "volume": "9", "interestChg": "-4", "time": timestamp - 1},
                        ]
                    },
                }
            raise AssertionError("unexpected path %s" % path)

        with (
            patch.object(config, "CTP_SNAPSHOT_AUTH_KEY", "test-key"),
            patch.object(source, "_post_json", side_effect=fake_post_json),
        ):
            payload = asyncio.run(source.fetch(_request()))

        self.assertEqual(payload.metrics["主力合约参考价"], "1065.62")
        self.assertEqual(payload.metrics["主力合约买一"], "1065.62")
        self.assertEqual(payload.metrics["主力合约卖一"], "1065.82")
        self.assertEqual(payload.metrics["主力合约成交量"], "暂无")
        self.assertEqual(payload.metrics["主力合约最新逐笔成交量"], "15")
        self.assertEqual(payload.metrics["主力合约成交额"], "192,717,785,600")
        self.assertEqual(payload.raw_items[0]["qibaotu_key"], "au2606:shfe")
        self.assertEqual(payload.raw_items[0]["volume"], "暂无")
        self.assertEqual(payload.raw_items[0]["recent_trade_volume"], "15")
        self.assertIn("CTP snapshot API: https://pc-api.qibaotu.com", payload.sources)

    def test_exact_contract_beats_later_fuzzy_search_result(self):
        source = CTPSnapshotSource(base_url="https://pc-api.qibaotu.com")
        timestamp = int(datetime(2026, 4, 15, 14, 30, 0).timestamp())

        def fake_post_json(path, payload):
            if path == "/api/upgrade/market/search":
                return {
                    "success": True,
                    "data": {
                        "list": [
                            {"key": "m2605:dce", "symbol": "m2605", "exchangeKey": "dce", "name": "豆粕2605"},
                            {"key": "jmmain:dce", "symbol": "jm2605", "exchangeKey": "dce", "name": "焦煤主连"},
                        ]
                    },
                }
            if path == "/api/transaction/latestTrade":
                if payload["key"] == "m2605:dce":
                    return {"success": True, "data": {"tickerData": {"lastPrice": "2835", "turnoverFiat": "1"}}}
                if payload["key"] == "jmmain:dce":
                    return {"success": True, "data": {"tickerData": {"lastPrice": "1080", "turnoverFiat": "2"}}}
                return {"success": True, "data": {"tickerData": {}}}
            if path == "/api/transaction/billData":
                return {"success": True, "data": {"bill": {"asks": [], "bids": []}}}
            if path == "/api/transaction/latestTransactionData":
                key_offset = 100 if payload["key"] == "jmmain:dce" else 0
                return {
                    "success": True,
                    "data": {"tradeList": [{"volume": "1", "time": timestamp + key_offset}]},
                }
            raise AssertionError("unexpected path %s" % path)

        with patch.object(source, "_post_json", side_effect=fake_post_json):
            payload = asyncio.run(source.fetch(_soymeal_request()))

        self.assertEqual(payload.raw_items[0]["instrument_id"], "M2605")
        self.assertEqual(payload.raw_items[0]["qibaotu_key"], "m2605:dce")
        self.assertEqual(payload.metrics["主力合约参考价"], "2835")


if __name__ == "__main__":
    unittest.main()
