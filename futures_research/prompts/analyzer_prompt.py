from __future__ import annotations

from typing import Optional

from futures_research.models.review import ReviewResult
from futures_research.models.variety import VarietyDefinition
from futures_research.prompts.loader import PromptRepository

ANALYZER_SYSTEM_PROMPT = """
你是一位专注于国内期货品种日报的资深分析师。

你的分析需要遵守以下原则：
1. 具体数字只能来自输入中的真实结构化数据，禁止补写、脑补、估算或套模板伪造。
2. 若结构化数据缺失，必须明确写“暂无可核验数据”。
3. 覆盖供给、需求、库存、持仓、国际联动、风险提示，但缺失部分只能写缺口说明。
4. 给出明确但克制的偏多/中性/偏空判断，不夸大，不绝对化。
5. 不得写出“必涨”“必跌”“建议买入”“应当做多”等表述。
6. 如果存在上轮审核反馈，必须显式说明修正点。
""".strip()


def build_analyzer_user_prompt(
    variety_definition: VarietyDefinition,
    prompt_repository: PromptRepository,
    raw_data: dict,
    review_result: Optional[ReviewResult],
    next_round: int,
) -> str:
    market_context = prompt_repository.load_market_template(variety_definition)
    feedback_section = ""
    if review_result and not review_result.passed:
        feedback_section = """
当前为第{next_round}轮分析，请在开头注明[第{next_round}轮修改]，并先说明本轮修正了哪些问题。

上轮审核反馈：
{feedback}

必须修复：
{issues}
""".strip().format(
            next_round=next_round,
            feedback=review_result.feedback,
            issues="\n".join(review_result.blocking_issues) or "无",
        )
    return """
{market_context}

请基于以下原始数据，输出结构化分析框架，格式必须包含：
## 核心观点
## 基本面分析
### 供给端
### 需求端
### 库存
## 国际联动
## 近期重要事件
## 核心驱动因子
## 风险提示
## 情绪判断

原始数据：
{raw_data}

{feedback_section}
""".strip().format(
        market_context=market_context,
        raw_data=raw_data,
        feedback_section=feedback_section or "本轮为首轮分析，无需引用审核反馈。",
    )
