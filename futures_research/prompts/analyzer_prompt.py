from __future__ import annotations

from typing import Optional

from futures_research.models.review import ReviewResult
from futures_research.models.variety import VarietyDefinition
from futures_research.prompts.loader import PromptRepository

ANALYZER_SYSTEM_PROMPT = """
你是一位专注于国内期货品种日报的资深分析师。

你的分析需要遵守以下原则：
1. 基于事实组织逻辑，不夸大，不绝对化。
2. 覆盖供给、需求、库存、持仓、国际联动、风险提示。
3. 给出明确但克制的偏多/中性/偏空判断。
4. 不得写出“必涨”“必跌”“建议买入”“应当做多”等表述。
5. 如果存在上轮审核反馈，必须显式说明修正点。
""".strip()


def build_analyzer_user_prompt(
    variety_definition: VarietyDefinition,
    prompt_repository: PromptRepository,
    raw_data: dict,
    review_result: Optional[ReviewResult],
    next_round: int,
    request_context: dict | None = None,
) -> str:
    market_context = prompt_repository.load_market_template(variety_definition)
    request_section = _build_request_section(request_context)
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

{request_section}

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
        request_section=request_section,
        raw_data=raw_data,
        feedback_section=feedback_section or "本轮为首轮分析，无需引用审核反馈。",
    )


def _build_request_section(request_context: dict | None) -> str:
    if not request_context:
        return "本次使用默认机构日报口径。"
    key_points = request_context.get("key_points", [])
    directives = request_context.get("writing_directives", [])
    return """
本次研究任务偏好：
- 研究周期：{horizon}
- 身份视角：{persona}
- 用户自定义关注：{focus}
- 已提炼关键点：{key_points}
- 写作/分析要求：{directives}
""".strip().format(
        horizon=request_context.get("horizon_label", "中线"),
        persona=request_context.get("persona_label", "金融公司期货部门"),
        focus=request_context.get("user_focus", "未额外指定"),
        key_points="；".join(key_points) if key_points else "按品种默认关键因子展开",
        directives="；".join(directives) if directives else "保持标准机构研究表达",
    )
