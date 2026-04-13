import asyncio
from datetime import date
import unittest
from unittest.mock import patch

import pandas as pd

from futures_research import config
from futures_research.data_sources.akshare_commodity_source import AkShareCommoditySource
from futures_research.models.source import DataFetchRequest


def _request():
    return DataFetchRequest(
        variety_code="AU",
        variety_name="沪金",
        contract="AU2606",
        contracts=["AU2606", "AU2612"],
        target_date=date(2026, 4, 10),
        exchange="SHFE",
        key_factors=[],
        news_keywords=[],
    )


class FakeAkShare:
    def futures_spot_price(self, date, vars_list):
        del date, vars_list
        return pd.DataFrame(
            [
                {
                    "date": "20260410",
                    "symbol": "AU",
                    "spot_price": 1041.78,
                    "dominant_contract": "au2606",
                    "dominant_contract_price": 1048.36,
                    "dom_basis": 6.58,
                    "dom_basis_rate": 0.006316,
                    "near_contract": "au2604",
                    "near_basis": 3.84,
                }
            ]
        )

    def spot_hist_sge(self, symbol):
        del symbol
        return pd.DataFrame(
            [
                {"date": "2026-04-09", "open": 1060.0, "close": 1036.0, "low": 1036.0, "high": 1060.0},
                {"date": "2026-04-10", "open": 1047.0, "close": 1047.23, "low": 1043.0, "high": 1055.0},
            ]
        )

    def futures_comex_inventory(self, symbol):
        return pd.DataFrame(
            [
                {
                    "日期": "2026-04-09",
                    "COMEX%s库存量-吨" % symbol: 1200.5,
                    "COMEX%s库存量-盎司" % symbol: 38600000,
                },
                {
                    "日期": "2026-04-10",
                    "COMEX%s库存量-吨" % symbol: 1198.25,
                    "COMEX%s库存量-盎司" % symbol: 38527600,
                },
            ]
        )


class AkShareCommoditySourceTests(unittest.TestCase):
    def test_fetch_configured_modules_outputs_fundamental_payload(self):
        source = AkShareCommoditySource()

        with (
            patch.object(config, "ENABLE_AKSHARE_COMMODITY_SOURCE", True),
            patch.object(source, "_load_akshare", return_value=FakeAkShare()),
        ):
            payload = asyncio.run(
                source.fetch(
                    _request(),
                    params={
                        "modules": [
                            {"type": "spot_basis", "symbol": "AU", "name": "沪金现货与基差"},
                            {
                                "type": "sge_spot",
                                "symbol": "Au99.99",
                                "name": "上海黄金交易所Au99.99",
                                "unit": "元/克",
                            },
                            {"type": "comex_inventory", "symbol": "黄金", "name": "COMEX黄金库存"},
                        ]
                    },
                )
            )

        self.assertEqual(len(payload.raw_items), 3)
        self.assertIn("AkShare: 生意社现货与基差", payload.sources)
        self.assertIn("AkShare: 上海黄金交易所历史行情", payload.sources)
        self.assertIn("AkShare: 东方财富COMEX库存", payload.sources)
        self.assertEqual(payload.raw_items[0]["item_type"], "spot_basis")
        self.assertEqual(payload.raw_items[1]["item_type"], "domestic_spot")
        self.assertEqual(payload.raw_items[2]["item_type"], "inventory")
        self.assertIn("基本面:沪金现货与基差:主力基差", payload.metrics)

    def test_stale_sge_data_becomes_gap_not_fact(self):
        class StaleAkShare(FakeAkShare):
            def spot_hist_sge(self, symbol):
                del symbol
                return pd.DataFrame(
                    [{"date": "2026-03-01", "open": 1, "close": 2, "low": 1, "high": 3}]
                )

        source = AkShareCommoditySource()
        with (
            patch.object(config, "ENABLE_AKSHARE_COMMODITY_SOURCE", True),
            patch.object(source, "_load_akshare", return_value=StaleAkShare()),
        ):
            payload = asyncio.run(
                source.fetch(
                    _request(),
                    params={
                        "max_stale_days": 2,
                        "modules": [{"type": "sge_spot", "symbol": "Au99.99", "name": "上海黄金交易所Au99.99"}],
                    },
                )
            )

        self.assertEqual(payload.raw_items, [])
        self.assertTrue(payload.data_gaps)
        self.assertIn("超过 2 天", payload.data_gaps[0])


if __name__ == "__main__":
    unittest.main()
