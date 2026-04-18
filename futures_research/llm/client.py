from __future__ import annotations

import asyncio
import json
from typing import Any, Dict, List

from futures_research import config

try:
    from anthropic import Anthropic
except ImportError:  # pragma: no cover
    Anthropic = None


class LLMClient:
    def __init__(self):
        self.api_key = config.ANTHROPIC_API_KEY
        self.base_url = config.ANTHROPIC_BASE_URL or None
        self.model = config.LLM_MODEL
        self.max_tokens = config.LLM_MAX_TOKENS
        self.temperature = config.LLM_TEMPERATURE
        self._client = (
            Anthropic(api_key=self.api_key, base_url=self.base_url) if self.api_key and Anthropic else None
        )

    @property
    def is_live(self) -> bool:
        return self._client is not None

    async def generate_analysis(self, prompt: str, context: Dict[str, Any]) -> str:
        if self.is_live:
            return await asyncio.to_thread(self._call_anthropic, prompt, context, "analysis")
        raise RuntimeError("LLM analysis requested but no live Anthropic-compatible client is configured.")

    async def generate_report(self, prompt: str, context: Dict[str, Any]) -> str:
        if self.is_live:
            return await asyncio.to_thread(self._call_anthropic, prompt, context, "report")
        raise RuntimeError("LLM report generation requested but no live Anthropic-compatible client is configured.")

    def _call_anthropic(self, prompt: str, context: Dict[str, Any], kind: str) -> str:
        tools: List[Dict[str, Any]] = []
        if config.ENABLE_ANTHROPIC_WEB_SEARCH:
            tools.append({"type": "web_search_20250305", "name": "web_search"})
        message = self._client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            temperature=self.temperature,
            tools=tools or None,
            messages=[
                {
                    "role": "user",
                    "content": "%s\n\n上下文：\n%s" % (
                        prompt,
                        json.dumps(context, ensure_ascii=False, indent=2),
                    ),
                }
            ],
        )
        parts = []
        for block in message.content:
            text = getattr(block, "text", "")
            if text:
                parts.append(text)
        if not parts:
            raise ValueError("Anthropic returned no text blocks for %s" % kind)
        return "\n".join(parts).strip()

    def _mock_analysis(self, context: Dict[str, Any]) -> str:
        raw_data = context["raw_data"]
        variety = context["variety_name"]
        contract = context["contract"]
        key_factors = context["key_factors"]
        highlights = raw_data.get("highlights", [])
        sources = "、".join(raw_data.get("sources", []))
        review_feedback = context.get("review_feedback", "")
        requested_review_round = context.get("requested_review_round", 1)
        revision_prefix = ""
        if review_feedback:
            revision_prefix = "[第%d轮修改]\n已根据审核反馈补充合规与数据表达，并修正上一轮问题。\n\n" % requested_review_round
        return """
{revision_prefix}
## 核心观点
{variety}{contract} 维持中性偏多判断，原因是供需预期平稳、库存压力可控、国际联动没有出现明显利空冲击。

## 基本面分析
### 供给端
当前供给端围绕{factor_1}展开，模拟数据反映市场对供给节奏保持审慎乐观。
### 需求端
需求端与{factor_2}相关，当前下游采购节奏偏稳，未出现明显塌陷。
### 库存
库存指标显示阶段性库存仍在可承受区间，未形成压制性累库。

## 国际联动
国际市场方面，外盘与宏观环境对国内盘面的传导偏温和，说明跨市场冲击有限。

## 近期重要事件
1. 模拟行业快讯围绕{factor_1}展开。
2. 模拟交易所公告聚焦持仓与库存。
3. 模拟产业信息反映下游采购偏稳。

## 核心驱动因子
1. {factor_1}
2. {factor_2}
3. {factor_3}

## 风险提示
1. 需求恢复不及预期。
2. 政策节奏变化超预期。
3. 国际价格波动向国内传导加快。

## 情绪判断
中性偏多，置信度：中。

补充来源：{sources}
补充摘要：{highlights}
""".strip().format(
            revision_prefix=revision_prefix,
            variety=variety,
            contract=contract,
            factor_1=key_factors[0] if key_factors else "供给端节奏",
            factor_2=key_factors[1] if len(key_factors) > 1 else "需求端韧性",
            factor_3=key_factors[2] if len(key_factors) > 2 else "国际价格联动",
            sources=sources or "Mock 数据源",
            highlights="；".join(highlights[:3]),
        )

    def _mock_report(self, context: Dict[str, Any]) -> str:
        raw_data = context["raw_data"]
        analysis = context["analysis_result"]
        variety = context["variety_name"]
        contract = context["contract"]
        target_date = context["target_date"]
        sources = raw_data.get("sources", [])
        metrics = raw_data.get("metrics", {})
        key_factors = context["key_factors"]
        summary = (
            "%s%s 当前供需两端均未出现失衡信号，库存与持仓指标偏稳，"
            "整体判断维持中性偏多。"
        ) % (variety, contract)
        recent_news = raw_data.get("highlights", [])
        return """
# {variety}期货日报 — {contract} [{target_date}]

> **核心观点**：{summary}  
> **情绪**：中性偏多 | **置信度**：中

---

## 一、行情回顾
{contract} 当前参考价位于 {price} 一线，近月远月价差约为 {spread}，盘面整体呈现震荡偏强格局。（来源：MockMarketWire）

## 二、基本面分析

### 供给端
供给端主要围绕 {factor_1} 展开，当前模拟行业跟踪显示供给节奏较平稳，未出现剧烈扰动。（来源：MockIndustryPanel）

### 需求端
需求端与 {factor_2} 关联度较高，目前下游开工率约为 {operating_rate}，采购延续刚需补库特征。（来源：MockIndustryPanel）

### 库存与持仓
社会库存约为 {inventory}，主力持仓变化约为 {position_change}，说明市场分歧仍存但未见极端拥挤。（来源：MockExchangeBulletin）

## 三、国际市场
国际联动指数约为 {global_index}，说明外盘与宏观环境对国内盘面的传导仍需观察。若海外价格波动放大，可能通过成本和情绪路径影响国内行情。（来源：MockMarketWire）

## 四、近期重要资讯
- {news_1}（来源：MockMarketWire）
- {news_2}（来源：MockExchangeBulletin）
- {news_3}（来源：MockIndustryPanel）

## 五、核心驱动因子
1. **{factor_1}**：当前仍是盘面定价的关键抓手。
2. **{factor_2}**：决定下游订单与补库节奏。
3. **{factor_3}**：影响内外盘联动和市场情绪。

## 六、风险提示
1. 供给端节奏若出现超预期变化，价格中枢可能重新定价。
2. 需求恢复若低于预期，下游开工和采购意愿可能回落。
3. 外盘波动、宏观政策变化或汇率扰动可能放大短期风险。

---
*数据来源：{sources_text}*  
*生成时间：{target_date}*  
*本报告由AI自动生成，仅供参考，不构成投资建议。*

<!-- analysis_trace
{analysis}
-->
""".strip().format(
            variety=variety,
            contract=contract,
            target_date=target_date,
            summary=summary,
            price=metrics.get("主力合约参考价", "待补充"),
            spread=metrics.get("近月-远月价差", "待补充"),
            operating_rate=metrics.get("下游开工率", "待补充"),
            inventory=metrics.get("社会库存", "待补充"),
            position_change=metrics.get("主力持仓变化", "待补充"),
            global_index=metrics.get("国际联动指数", "待补充"),
            news_1=recent_news[0] if len(recent_news) > 0 else "暂无资讯",
            news_2=recent_news[1] if len(recent_news) > 1 else "暂无资讯",
            news_3=recent_news[2] if len(recent_news) > 2 else "暂无资讯",
            factor_1=key_factors[0] if key_factors else "供给端节奏",
            factor_2=key_factors[1] if len(key_factors) > 1 else "需求端韧性",
            factor_3=key_factors[2] if len(key_factors) > 2 else "国际联动",
            sources_text="、".join(sources) or "MockMarketWire",
            analysis=analysis,
        )
