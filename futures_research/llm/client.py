from __future__ import annotations

import asyncio
import json
import re
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
        return self._mock_analysis(context)

    async def generate_report(self, prompt: str, context: Dict[str, Any]) -> str:
        if self.is_live:
            return await asyncio.to_thread(self._call_anthropic, prompt, context, "report")
        return self._mock_report(context)

    async def generate_research_preview(self, context: Dict[str, Any]) -> Dict[str, Any]:
        fallback = {
            "summary": str(context.get("fallback_summary", "")),
            "key_points": self._normalize_string_list(context.get("fallback_key_points", [])),
            "writing_directives": self._normalize_string_list(context.get("fallback_writing_directives", [])),
            "recommended_template": str(context.get("fallback_template", "")),
        }
        if self.is_live:
            try:
                prompt = """
你是一位期货研究平台主管，需要把用户的一句话研究需求梳理成研报生成前的简报。

请严格输出 JSON：
{
  "summary": "<120字以内的任务概述>",
  "key_points": ["<3到5条关键关注点>"],
  "writing_directives": ["<2到4条写作导向>"],
  "recommended_template": "<简短模板标识>"
}

要求：
1. 不要给投资建议。
2. 不要输出 JSON 之外的任何解释。
3. key_points 要和用户关注点、研究周期、身份视角直接相关。
4. writing_directives 要能直接指导后续研报写作。
""".strip()
                payload = await asyncio.to_thread(
                    self._call_anthropic_json,
                    prompt,
                    context,
                    "research_preview",
                )
                return {
                    "summary": str(payload.get("summary") or fallback["summary"])[:120],
                    "key_points": self._normalize_string_list(payload.get("key_points")) or fallback["key_points"],
                    "writing_directives": self._normalize_string_list(payload.get("writing_directives"))
                    or fallback["writing_directives"],
                    "recommended_template": str(payload.get("recommended_template") or fallback["recommended_template"]),
                }
            except Exception:
                return fallback
        return fallback

    def _call_anthropic(self, prompt: str, context: Dict[str, Any], kind: str, enable_web_search: bool = True) -> str:
        tools: List[Dict[str, Any]] = []
        if enable_web_search and config.ENABLE_ANTHROPIC_WEB_SEARCH:
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

    def _call_anthropic_json(self, prompt: str, context: Dict[str, Any], kind: str) -> Dict[str, Any]:
        payload = self._call_anthropic(prompt, context, kind, enable_web_search=False)
        return self._extract_json_object(payload)

    def _mock_analysis(self, context: Dict[str, Any]) -> str:
        raw_data = context["raw_data"]
        variety = context["variety_name"]
        contract = context["contract"]
        key_factors = context["key_factors"]
        request_context = context.get("research_request") or {}
        highlights = raw_data.get("highlights", [])
        sources = "、".join(raw_data.get("sources", []))
        review_feedback = context.get("review_feedback", "")
        requested_review_round = context.get("requested_review_round", 1)
        revision_prefix = ""
        if review_feedback:
            revision_prefix = "[第%d轮修改]\n已根据审核反馈补充合规与数据表达，并修正上一轮问题。\n\n" % requested_review_round
        focus_points = request_context.get("key_points") or key_factors
        persona_label = request_context.get("persona_label", "金融公司期货部门")
        horizon_label = request_context.get("horizon_label", "中线")
        return """
{revision_prefix}
## 核心观点
从{persona_label}视角看，{variety}{contract} 在{horizon_label}框架下维持中性偏多判断，原因是供需预期平稳、库存压力可控、国际联动没有出现明显利空冲击。

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

定制关注点：{focus_points}
补充来源：{sources}
补充摘要：{highlights}
""".strip().format(
            revision_prefix=revision_prefix,
            persona_label=persona_label,
            variety=variety,
            contract=contract,
            horizon_label=horizon_label,
            factor_1=focus_points[0] if focus_points else "供给端节奏",
            factor_2=focus_points[1] if len(focus_points) > 1 else "需求端韧性",
            factor_3=focus_points[2] if len(focus_points) > 2 else "国际价格联动",
            focus_points="；".join(focus_points[:4]),
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
        request_context = context.get("research_request") or {}
        key_factors = request_context.get("key_points") or context["key_factors"]
        persona_label = request_context.get("persona_label", "金融公司期货部门")
        horizon_label = request_context.get("horizon_label", "中线")
        user_focus = request_context.get("user_focus", "")
        summary = (
            "%s视角下，%s%s 当前供需两端均未出现失衡信号，库存与持仓指标偏稳，"
            "在%s框架内整体判断维持中性偏多。"
        ) % (persona_label, variety, contract, horizon_label)
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
社会库存约为 {inventory}，主力持仓变化约为 {position_change}，说明市场分歧仍存但未见极端拥挤。若以{persona_label}的视角理解，更需要关注节奏切换是否与{focus_label}形成共振。（来源：MockExchangeBulletin）

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
4. {custom_risk}

---
*定制任务摘要：{briefing_summary}*
*用户额外关注：{user_focus_text}*
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
            persona_label=persona_label,
            focus_label=key_factors[0] if key_factors else "核心驱动",
            custom_risk="若%s判断与实际交易节奏背离，短期波动可能放大。"
            % (user_focus or "自定义关注点"),
            briefing_summary=request_context.get("briefing_summary", "按标准机构任务生成"),
            user_focus_text=user_focus or "无",
            sources_text="、".join(sources) or "MockMarketWire",
            analysis=analysis,
        )

    def _extract_json_object(self, payload: str) -> Dict[str, Any]:
        text = payload.strip()
        if text.startswith("```"):
            blocks = re.findall(r"```(?:json)?\s*(.*?)```", text, flags=re.S)
            if blocks:
                text = blocks[0].strip()
        match = re.search(r"\{.*\}", text, flags=re.S)
        if not match:
            raise ValueError("No JSON object found in response payload.")
        return json.loads(match.group(0))

    def _normalize_string_list(self, values: Any) -> List[str]:
        if not isinstance(values, list):
            return []
        normalized = []
        for value in values:
            text = str(value).strip()
            if text:
                normalized.append(text)
        return normalized[:5]
