from __future__ import annotations

from typing import Optional

from futures_research.models.review import ReviewResult
from futures_research.models.variety import VarietyDefinition
from futures_research.prompts.loader import PromptRepository

WRITER_SYSTEM_PROMPT = """
你是一位头部期货公司研究院的日报撰写专家。请将分析框架转化为规范 Markdown 研报。

写作规范：
1. 严格使用六章节：行情回顾、基本面分析、国际市场、近期重要资讯、核心驱动因子、风险提示。
2. 首段必须像期货公司正式日报一样，给出一句话核心观点、情绪、置信度，并点明主要矛盾。
3. 版式要适合后续导出为 A4 中文 PDF：标题克制、段落短、层级清晰、避免超长句和口语化表达。
4. 具体数字、时间、来源只能使用输入里已经核验的结构化数据；若输入未提供单位，不得自行补单位。
5. 对于现货、库存、开工率、国际联动等缺失字段，必须明确写“暂无可核验数据”，不得套模板填充。
6. 专业、客观、简练，不使用投资建议或绝对预测。
7. 结尾必须包含 AI 免责声明。
8. 输出必须是完整 Markdown，不要额外解释写作过程。
""".strip()


def build_writer_user_prompt(
    variety_definition: VarietyDefinition,
    prompt_repository: PromptRepository,
    analysis_result: str,
    raw_data: dict,
    review_result: Optional[ReviewResult],
    next_round: int,
) -> str:
    market_context = prompt_repository.load_market_template(variety_definition)
    revision_section = ""
    if review_result and not review_result.passed:
        revision_section = """
当前为第{next_round}轮写作，请优先落实以下审核意见，避免重复上一轮问题：
- 审核反馈：{feedback}
- 必须修复：{issues}
""".strip().format(
            next_round=next_round,
            feedback=review_result.feedback,
            issues="；".join(review_result.blocking_issues) or "无",
        )
    return """
{market_context}

请把下面的分析框架写成完整日报 Markdown：
{analysis_result}

可引用原始数据：
{raw_data}

{revision_section}
""".strip().format(
        market_context=market_context,
        analysis_result=analysis_result,
        raw_data=raw_data,
        revision_section=revision_section or "本轮为首轮写作，按标准模板输出即可。",
    )
