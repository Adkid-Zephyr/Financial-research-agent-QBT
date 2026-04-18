from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Dict, List

from futures_research import config
from futures_research.models.report import ResearchReport
from futures_research.models.review import ReviewResult
from futures_research.prompts.reviewer_prompt import REVIEW_RUBRIC
from futures_research.runtime import RuntimeContext

ABSOLUTE_PATTERNS = [
    re.compile(r"必涨"),
    re.compile(r"必跌"),
    re.compile(r"一定会"),
    re.compile(r"一定将"),
    re.compile(r"肯定会"),
    re.compile(r"必然"),
]
ADVICE_PATTERNS = [
    re.compile(r"建议买入"),
    re.compile(r"建议卖出"),
    re.compile(r"应当做多"),
    re.compile(r"应当做空"),
    re.compile(r"建议做多"),
    re.compile(r"建议做空"),
]
DISCLAIMER_PATTERNS = [
    re.compile(r"本报告由(?:AI|人工智能).{0,24}生成"),
    re.compile(r"仅供(?:参考|信息参考)"),
    re.compile(r"不构成(?:任何)?投资建议"),
]
DEFAULT_ALLOWED_SOURCE_PREFIXES = [
    "CTP snapshot API",
    "Yahoo Finance via yfinance",
    "AkShare structured commodity data",
    "AkShare:",
    "数据覆盖范围说明",
]


def _has_sources(text: str) -> bool:
    return "来源：" in text or "来源:" in text


def _extract_source_labels(text: str) -> List[str]:
    labels = []
    for match in re.finditer(r"来源[:：]([^\n）)]+)", text):
        label = match.group(1).strip()
        if label:
            labels.append(label)
    return labels


def _unknown_source_labels(text: str, raw_sources: List[str]) -> List[str]:
    allowed_prefixes = [*DEFAULT_ALLOWED_SOURCE_PREFIXES, *[str(item) for item in raw_sources]]
    unknown = []
    for label in _extract_source_labels(text):
        if not any(label.startswith(prefix) for prefix in allowed_prefixes):
            unknown.append(label)
    return unknown


def _contains_any(text: str, keywords: List[str]) -> bool:
    return any(keyword in text for keyword in keywords)


def _matches_any(text: str, patterns: List[re.Pattern[str]]) -> bool:
    return any(pattern.search(text) for pattern in patterns)


def _section_exists(text: str, section: str) -> bool:
    return section in text


def _count_numeric_mentions(text: str) -> int:
    return len(re.findall(r"\d+(?:\.\d+)?", text))


def _has_ai_disclaimer(text: str) -> bool:
    return all(pattern.search(text) for pattern in DISCLAIMER_PATTERNS)


async def review_node(state: Dict[str, Any], runtime: RuntimeContext) -> Dict[str, Any]:
    del runtime
    draft = state["report_draft"]
    blocking_issues = []
    if _matches_any(draft, ABSOLUTE_PATTERNS):
        blocking_issues.append("存在绝对化预测表述")
    if _matches_any(draft, ADVICE_PATTERNS):
        blocking_issues.append("存在投资建议性表述")
    if not _has_ai_disclaimer(draft):
        blocking_issues.append("缺少 AI 免责声明")
    if "Mock" in draft or any("Mock" in str(item) for item in state.get("raw_data", {}).get("sources", [])):
        blocking_issues.append("包含 mock 数据来源")
    if "未通过合规审查，卡在第四步" in draft:
        blocking_issues.append("grounded LLM 第四步合规审查未通过")
    if "web_search_20250305" in draft or any(
        "web_search_20250305" in str(item) for item in state.get("raw_data", {}).get("sources", [])
    ):
        blocking_issues.append("包含保留中的 web_search 数据来源")
    unknown_sources = _unknown_source_labels(draft, state.get("raw_data", {}).get("sources", []))
    if unknown_sources:
        blocking_issues.append("包含未登记数据来源：%s" % "；".join(sorted(set(unknown_sources))))
    external_market_facts = state.get("raw_data", {}).get("external_market_facts", [])
    if external_market_facts and "Yahoo Finance via yfinance" not in draft:
        blocking_issues.append("外盘/宏观数字缺少 Yahoo Finance via yfinance 来源标注")
    fundamental_facts = state.get("raw_data", {}).get("fundamental_facts", [])
    if fundamental_facts and "AkShare" not in draft:
        blocking_issues.append("基本面数字缺少 AkShare 来源标注")

    logic_chain = 10.0
    if _section_exists(draft, "## 二、基本面分析"):
        logic_chain += 5
    if _section_exists(draft, "## 三、国际市场"):
        logic_chain += 5
    if _section_exists(draft, "## 五、核心驱动因子"):
        logic_chain += 5

    data_quality = 4.0
    numeric_mentions = _count_numeric_mentions(draft)
    if numeric_mentions >= 8:
        data_quality += 8
    elif numeric_mentions >= 4:
        data_quality += 4
    if _has_sources(draft):
        data_quality += 8

    conclusion_clarity = 8.0
    if _contains_any(draft, ["偏多", "偏空", "中性"]):
        conclusion_clarity += 6
    if "核心观点" in draft:
        conclusion_clarity += 6

    risk_disclosure = 6.0
    if _section_exists(draft, "## 六、风险提示"):
        risk_disclosure += 4
    if _contains_any(draft, ["政策", "需求", "供给", "国际"]):
        risk_disclosure += 5

    compliance = 20.0
    if blocking_issues:
        compliance -= min(20.0, 6.0 * len(blocking_issues))
    elif not _has_sources(draft):
        compliance -= 4

    dimension_scores = {
        "logic_chain": round(min(REVIEW_RUBRIC["logic_chain"]["weight"], logic_chain), 1),
        "data_quality": round(min(REVIEW_RUBRIC["data_quality"]["weight"], data_quality), 1),
        "conclusion_clarity": round(min(REVIEW_RUBRIC["conclusion_clarity"]["weight"], conclusion_clarity), 1),
        "risk_disclosure": round(min(REVIEW_RUBRIC["risk_disclosure"]["weight"], risk_disclosure), 1),
        "compliance": round(max(0.0, min(REVIEW_RUBRIC["compliance"]["weight"], compliance)), 1),
    }
    total_score = round(sum(dimension_scores.values()), 1)
    passed = total_score >= config.MIN_PASS_SCORE and not blocking_issues
    feedback_parts = []
    if dimension_scores["data_quality"] < 12:
        feedback_parts.append("补充具体数字和来源标注，尤其是在行情回顾和库存持仓部分。")
    if dimension_scores["logic_chain"] < 18:
        feedback_parts.append("强化供给、需求、库存与国际联动之间的因果衔接。")
    if dimension_scores["risk_disclosure"] < 10:
        feedback_parts.append("将风险提示细化为供给、需求和政策三类。")
    if blocking_issues:
        feedback_parts.append("优先修复合规问题：%s。" % "；".join(blocking_issues))
    feedback = "".join(feedback_parts) or "结构完整，可进入后续发布或存储环节。"

    review_result = ReviewResult(
        round=state.get("review_round", 0) + 1,
        total_score=total_score,
        passed=passed,
        dimension_scores=dimension_scores,
        feedback=feedback[:200],
        blocking_issues=blocking_issues,
    )
    review_history = list(state.get("review_history", []))
    review_history.append(review_result.model_dump())

    report_content = _normalize_user_report_text(draft)
    report = ResearchReport(
        symbol=state["symbol"],
        variety_code=state["variety_code"],
        variety=state["variety"],
        target_date=state["target_date"],
        generated_at=datetime.now(),
        review_rounds=review_result.round,
        final_score=review_result.total_score,
        content=report_content,
        summary=_extract_summary(report_content),
        sentiment=_extract_sentiment(report_content),
        confidence=_extract_confidence(report_content),
        key_factors=_extract_numbered_items(report_content, "## 五、核心驱动因子"),
        risk_points=_extract_numbered_items(report_content, "## 六、风险提示"),
        data_sources=state["raw_data"].get("sources", []),
    )
    return {
        "current_step": "review",
        "review_round": review_result.round,
        "review_result": review_result.model_dump(),
        "review_history": review_history,
        "final_report": report.model_dump(),
    }


def _extract_summary(text: str) -> str:
    cleaned = _normalize_user_report_text(text)
    for line in cleaned.splitlines():
        stripped = line.strip()
        if stripped.startswith("> **核心观点**："):
            return _compact_summary(stripped.replace("> **核心观点**：", ""))
        if stripped.startswith("> 核心观点"):
            return _compact_summary(stripped.replace("> 核心观点", "").lstrip("：:"))
    for heading in ["## 核心观点", "## 一、结论先行", "## 一、行情回顾"]:
        section = _extract_section_after_heading(cleaned, heading)
        if section:
            return _compact_summary(section)
    for line in cleaned.splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and not stripped.startswith("---"):
            return _compact_summary(stripped)
    return ""


def _compact_summary(text: str) -> str:
    compact = re.sub(r"\s+", " ", _strip_markdown_inline(text)).strip(" ：:")
    return compact[:120]


def _extract_section_after_heading(text: str, heading: str) -> str:
    if heading not in text:
        return ""
    section = text.split(heading, 1)[1]
    lines = []
    for line in section.splitlines():
        stripped = line.strip()
        if not stripped:
            if lines:
                break
            continue
        if stripped.startswith("## "):
            break
        lines.append(stripped.lstrip("> ").strip())
    return " ".join(lines)


def _normalize_user_report_text(text: str) -> str:
    normalized = _strip_internal_blocks(text)
    normalized = re.sub(r"\[(?:F|G)\d+\]", "", normalized)
    normalized = re.sub(r"(?<![A-Za-z0-9])(?:F|G)\d+(?![A-Za-z0-9])", "", normalized)
    normalized = re.sub(r"[ \t]+([，。；：、,.])", r"\1", normalized)
    normalized = re.sub(r"([（(])\s+([）)])", "", normalized)
    normalized = re.sub(r"[ \t]{2,}", " ", normalized)
    return "\n".join(line.rstrip() for line in normalized.splitlines()).strip()


def _strip_internal_blocks(text: str) -> str:
    without_comments = re.sub(r"<!--.*?-->", "", text or "", flags=re.DOTALL)
    lines = without_comments.splitlines()
    visible = []
    skip_mode = ""
    for line in lines:
        stripped = line.strip()
        if re.match(r"^##\s+七、数据说明与待补充项", stripped):
            skip_mode = "section"
            continue
        if stripped == "写作约束：":
            skip_mode = "constraint"
            continue
        if skip_mode:
            can_resume = (
                re.match(r"^#{1,6}\s+", stripped)
                or stripped == "---"
                or (skip_mode == "constraint" and not stripped)
            )
            if can_resume:
                skip_mode = ""
            else:
                continue
        if re.match(r"^\d+\.\s+\*\*研究边界\*\*", stripped):
            continue
        visible.append(line)
    return "\n".join(visible)


def _strip_markdown_inline(text: str) -> str:
    stripped = _normalize_user_report_text(text)
    stripped = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", stripped)
    stripped = re.sub(r"`([^`]+)`", r"\1", stripped)
    stripped = stripped.replace("**", "").replace("*", "")
    stripped = stripped.lstrip("> ").strip()
    return stripped

def _extract_sentiment(text: str) -> str:
    if "偏多" in text:
        return "偏多"
    if "偏空" in text:
        return "偏空"
    return "中性"


def _extract_confidence(text: str) -> str:
    if "置信度：高" in text:
        return "高"
    if "置信度：低" in text:
        return "低"
    return "中"


def _extract_numbered_items(text: str, heading: str) -> List[str]:
    if heading not in text:
        return []
    section = text.split(heading, 1)[1]
    items = []
    for line in section.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("## "):
            break
        if re.match(r"^\d+\.", stripped):
            item = stripped.split(" ", 1)[1] if " " in stripped else stripped
            items.append(item.strip())
    return items
