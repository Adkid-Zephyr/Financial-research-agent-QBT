from datetime import date
import unittest

from futures_research.agents.reviewer import review_node
from futures_research.runtime import build_runtime


class ReviewerTests(unittest.IsolatedAsyncioTestCase):
    async def test_absolute_prediction_triggers_blocking_issue(self):
        runtime = build_runtime()
        state = {
            "symbol": "CF2605",
            "variety_code": "CF",
            "variety": "棉花",
            "target_date": date.today(),
            "report_draft": "# 标题\n必涨。\n本报告由AI自动生成，仅供参考，不构成投资建议。",
            "raw_data": {"sources": ["CTP snapshot API"]},
            "review_round": 0,
            "review_history": [],
        }
        result = await review_node(state, runtime)
        self.assertFalse(result["review_result"]["passed"])
        self.assertTrue(result["review_result"]["blocking_issues"])

    async def test_missing_sources_penalizes_data_quality(self):
        runtime = build_runtime()
        state = {
            "symbol": "CF2605",
            "variety_code": "CF",
            "variety": "棉花",
            "target_date": date.today(),
            "report_draft": """
# 标题
> **核心观点**：中性。

## 一、行情回顾
价格在 13500 附近。

## 二、基本面分析
### 供给端
平稳。
### 需求端
平稳。
### 库存与持仓
库存 50 万吨。

## 三、国际市场
外盘平稳。

## 四、近期重要资讯
- 资讯 1

## 五、核心驱动因子
1. 因子一

## 六、风险提示
1. 政策变化

本报告由AI自动生成，仅供参考，不构成投资建议。
""".strip(),
            "raw_data": {"sources": ["CTP snapshot API"]},
            "review_round": 0,
            "review_history": [],
        }
        result = await review_node(state, runtime)
        self.assertLess(result["review_result"]["dimension_scores"]["data_quality"], 10)

    async def test_complete_report_passes(self):
        runtime = build_runtime()
        state = {
            "symbol": "CF2605",
            "variety_code": "CF",
            "variety": "棉花",
            "target_date": date.today(),
            "report_draft": """
# 标题
> **核心观点**：中性偏多。  
> **情绪**：中性偏多 | **置信度**：中

## 一、行情回顾
价格在 13500 元/吨附近，价差 120 元/吨。（来源：CTP snapshot API）

## 二、基本面分析
### 供给端
供给平稳。（来源：CTP snapshot API）
### 需求端
需求平稳。（来源：CTP snapshot API）
### 库存与持仓
库存 50 万吨，持仓变化 4%。（来源：CTP snapshot API）

## 三、国际市场
ICE 与美元波动温和。（来源：CTP snapshot API）

## 四、近期重要资讯
- 资讯 1（来源：CTP snapshot API）

## 五、核心驱动因子
1. 因子一
2. 因子二

## 六、风险提示
1. 政策变化
2. 需求不及预期

本报告由AI自动生成，仅供参考，不构成投资建议。
""".strip(),
            "raw_data": {"sources": ["CTP snapshot API"]},
            "review_round": 0,
            "review_history": [],
        }
        result = await review_node(state, runtime)
        self.assertGreaterEqual(result["review_result"]["total_score"], 75)
        self.assertTrue(result["review_result"]["passed"])
        self.assertEqual(result["review_result"]["round"], 1)
        self.assertEqual(len(result["review_history"]), 1)

    async def test_disclaimer_variant_is_accepted(self):
        runtime = build_runtime()
        state = {
            "symbol": "AU2606",
            "variety_code": "AU",
            "variety": "沪金",
            "target_date": date.today(),
            "report_draft": """
# 标题
> **核心观点**：中性偏多。  
> **情绪**：中性偏多 | **置信度**：中

## 一、行情回顾
价格在 750 元/克附近，价差 3 元/克。（来源：CTP snapshot API）

## 二、基本面分析
### 供给端
供给平稳。（来源：CTP snapshot API）
### 需求端
避险需求存在。（来源：CTP snapshot API）
### 库存与持仓
库存 12 吨，持仓变化 2%。（来源：CTP snapshot API）

## 三、国际市场
COMEX 黄金与美元波动温和。（来源：CTP snapshot API）

## 四、近期重要资讯
- 资讯 1（来源：CTP snapshot API）

## 五、核心驱动因子
1. 因子一
2. 因子二

## 六、风险提示
1. 美元反弹
2. 避险情绪回落

本报告由AI生成，内容仅供参考，不构成任何投资建议。
""".strip(),
            "raw_data": {"sources": ["CTP snapshot API"]},
            "review_round": 0,
            "review_history": [],
        }
        result = await review_node(state, runtime)
        self.assertTrue(result["review_result"]["passed"])
        self.assertNotIn("缺少 AI 免责声明", result["review_result"]["blocking_issues"])

    async def test_phrase_with_yiding_is_not_misclassified_as_absolute_prediction(self):
        runtime = build_runtime()
        state = {
            "symbol": "AG2606",
            "variety_code": "AG",
            "variety": "沪银",
            "target_date": date.today(),
            "report_draft": """
# 标题
> **核心观点**：中性偏多。  
> **情绪**：中性偏多 | **置信度**：中

## 一、行情回顾
价格在 7000 元/吨附近，存在一定支撑。（来源：CTP snapshot API）

## 二、基本面分析
### 供给端
供给平稳。（来源：CTP snapshot API）
### 需求端
需求平稳。（来源：CTP snapshot API）
### 库存与持仓
库存 50 万吨，持仓变化 4%。（来源：CTP snapshot API）

## 三、国际市场
外盘波动温和。（来源：CTP snapshot API）

## 四、近期重要资讯
- 资讯 1（来源：CTP snapshot API）

## 五、核心驱动因子
1. 因子一
2. 因子二

## 六、风险提示
1. 政策变化
2. 需求不及预期

本报告由AI辅助生成，内容仅供参考，不构成任何投资建议。
""".strip(),
            "raw_data": {"sources": ["CTP snapshot API"]},
            "review_round": 0,
            "review_history": [],
        }
        result = await review_node(state, runtime)
        self.assertTrue(result["review_result"]["passed"])
        self.assertNotIn("存在绝对化预测表述", result["review_result"]["blocking_issues"])

    async def test_unknown_source_triggers_blocking_issue(self):
        runtime = build_runtime()
        state = {
            "symbol": "AU2606",
            "variety_code": "AU",
            "variety": "沪金",
            "target_date": date.today(),
            "report_draft": """
# 标题
> **核心观点**：中性。  
> **情绪**：中性 | **置信度**：中

## 一、行情回顾
价格在 750 附近。（来源：UnknownWire）

## 二、基本面分析
### 供给端
暂无可核验数据。（来源：CTP snapshot API）
### 需求端
暂无可核验数据。（来源：CTP snapshot API）
### 库存与持仓
持仓 100，成交 200。（来源：CTP snapshot API）

## 三、国际市场
外盘波动温和。（来源：UnknownWire）

## 四、近期重要资讯
- 资讯 1（来源：CTP snapshot API）

## 五、核心驱动因子
1. 因子一
2. 因子二

## 六、风险提示
1. 美元波动
2. 需求不及预期

本报告由AI自动生成，仅供参考，不构成投资建议。
""".strip(),
            "raw_data": {"sources": ["CTP snapshot API"]},
            "review_round": 0,
            "review_history": [],
        }
        result = await review_node(state, runtime)
        self.assertFalse(result["review_result"]["passed"])
        self.assertTrue(
            any("包含未登记数据来源" in item for item in result["review_result"]["blocking_issues"])
        )

    async def test_yahoo_market_source_is_accepted_when_external_facts_exist(self):
        runtime = build_runtime()
        state = {
            "symbol": "AU2606",
            "variety_code": "AU",
            "variety": "沪金",
            "target_date": date.today(),
            "report_draft": """
# 标题
> **核心观点**：中性。  
> **情绪**：中性 | **置信度**：中

## 一、行情回顾
价格在 750 附近。（来源：CTP snapshot API）

## 二、基本面分析
### 供给端
暂无可核验数据。（来源：CTP snapshot API 覆盖范围说明）
### 需求端
暂无可核验数据。（来源：CTP snapshot API 覆盖范围说明）
### 库存与持仓
持仓 100，成交 200。（来源：CTP snapshot API）

## 三、国际市场
COMEX黄金截至 2026-04-10 收盘价 2400，涨跌 12，涨跌幅 0.5%。（来源：Yahoo Finance via yfinance）

## 四、近期重要资讯
- 资讯 1（来源：CTP snapshot API）

## 五、核心驱动因子
1. 因子一
2. 因子二

## 六、风险提示
1. 美元波动
2. 需求不及预期

本报告由AI自动生成，仅供参考，不构成投资建议。
""".strip(),
            "raw_data": {
                "sources": ["CTP snapshot API", "Yahoo Finance via yfinance"],
                "external_market_facts": [
                    {"item_type": "external_market", "name": "COMEX黄金", "stale": "false"}
                ],
            },
            "review_round": 0,
            "review_history": [],
        }
        result = await review_node(state, runtime)
        self.assertTrue(result["review_result"]["passed"])
        self.assertFalse(result["review_result"]["blocking_issues"])

    async def test_akshare_source_is_accepted_when_fundamental_facts_exist(self):
        runtime = build_runtime()
        state = {
            "symbol": "AU2606",
            "variety_code": "AU",
            "variety": "沪金",
            "target_date": date.today(),
            "report_draft": """
# 标题
> **核心观点**：中性。  
> **情绪**：中性 | **置信度**：中

## 一、行情回顾
价格在 750 附近。（来源：CTP snapshot API）

## 二、基本面分析
### 供给端
暂无可核验数据。（来源：CTP snapshot API 覆盖范围说明）
### 需求端
暂无可核验数据。（来源：CTP snapshot API 覆盖范围说明）
### 现货与基差
沪金现货与基差截至 2026-04-10 现货价格 1041.78，主力合约 au2606 对应基差 6.58，基差率 0.6316%。（来源：AkShare structured commodity data）
### 库存与持仓
COMEX黄金库存截至 2026-04-10 库存 1198.25 吨。（来源：AkShare structured commodity data）

## 三、国际市场
暂无可核验数据。（来源：数据覆盖范围说明）

## 四、近期重要资讯
- 资讯 1（来源：CTP snapshot API）

## 五、核心驱动因子
1. 因子一
2. 因子二

## 六、风险提示
1. 美元波动
2. 需求不及预期

本报告由AI自动生成，仅供参考，不构成投资建议。
""".strip(),
            "raw_data": {
                "sources": ["CTP snapshot API", "AkShare: 生意社现货与基差", "AkShare: 东方财富COMEX库存"],
                "fundamental_facts": [
                    {"item_type": "spot_basis", "name": "沪金现货与基差", "stale": "false"},
                    {"item_type": "inventory", "name": "COMEX黄金库存", "stale": "false"},
                ],
            },
            "review_round": 0,
            "review_history": [],
        }
        result = await review_node(state, runtime)
        self.assertTrue(result["review_result"]["passed"])
        self.assertFalse(result["review_result"]["blocking_issues"])


if __name__ == "__main__":
    unittest.main()
