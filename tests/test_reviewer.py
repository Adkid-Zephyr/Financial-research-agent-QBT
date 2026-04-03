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
            "raw_data": {"sources": ["Mock"]},
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
            "raw_data": {"sources": ["Mock"]},
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
价格在 13500 元/吨附近，价差 120 元/吨。（来源：A）

## 二、基本面分析
### 供给端
供给平稳。（来源：A）
### 需求端
需求平稳。（来源：B）
### 库存与持仓
库存 50 万吨，持仓变化 4%。（来源：C）

## 三、国际市场
ICE 与美元波动温和。（来源：D）

## 四、近期重要资讯
- 资讯 1（来源：A）

## 五、核心驱动因子
1. 因子一
2. 因子二

## 六、风险提示
1. 政策变化
2. 需求不及预期

本报告由AI自动生成，仅供参考，不构成投资建议。
""".strip(),
            "raw_data": {"sources": ["Mock"]},
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
价格在 750 元/克附近，价差 3 元/克。（来源：A）

## 二、基本面分析
### 供给端
供给平稳。（来源：A）
### 需求端
避险需求存在。（来源：B）
### 库存与持仓
库存 12 吨，持仓变化 2%。（来源：C）

## 三、国际市场
COMEX 黄金与美元波动温和。（来源：D）

## 四、近期重要资讯
- 资讯 1（来源：A）

## 五、核心驱动因子
1. 因子一
2. 因子二

## 六、风险提示
1. 美元反弹
2. 避险情绪回落

本报告由AI生成，内容仅供参考，不构成任何投资建议。
""".strip(),
            "raw_data": {"sources": ["Mock"]},
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
价格在 7000 元/吨附近，存在一定支撑。（来源：A）

## 二、基本面分析
### 供给端
供给平稳。（来源：A）
### 需求端
需求平稳。（来源：B）
### 库存与持仓
库存 50 万吨，持仓变化 4%。（来源：C）

## 三、国际市场
外盘波动温和。（来源：D）

## 四、近期重要资讯
- 资讯 1（来源：A）

## 五、核心驱动因子
1. 因子一
2. 因子二

## 六、风险提示
1. 政策变化
2. 需求不及预期

本报告由AI辅助生成，内容仅供参考，不构成任何投资建议。
""".strip(),
            "raw_data": {"sources": ["Mock"]},
            "review_round": 0,
            "review_history": [],
        }
        result = await review_node(state, runtime)
        self.assertTrue(result["review_result"]["passed"])
        self.assertNotIn("存在绝对化预测表述", result["review_result"]["blocking_issues"])


if __name__ == "__main__":
    unittest.main()
