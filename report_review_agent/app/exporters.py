from __future__ import annotations

import json
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfbase.pdfmetrics import registerFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

from report_review_agent.app.models import ReviewResult


def build_markdown(result: ReviewResult) -> str:
    dimension_lines = "\n".join(
        f"- **{item.label}**: {item.score:.1f}/{item.max_score:.1f} - {item.rationale}"
        for item in result.dimension_scores
    )
    findings_lines = "\n".join(
        "\n".join(
            [
                f"### [{item.severity.upper()}] {item.title}",
                item.detail,
                f"- 建议：{item.recommendation}",
                f"- 目标章节：{', '.join(item.target_sections) if item.target_sections else 'N/A'}",
                f"- 证据：{' | '.join(item.evidence) if item.evidence else 'N/A'}",
            ]
        )
        for item in result.findings
    )
    actions_lines = "\n".join(
        f"{item.priority}. **{item.title}**: {item.action} "
        f"(目标章节: {', '.join(item.target_sections) if item.target_sections else 'N/A'})"
        for item in result.improvement_actions
    )
    strengths_lines = "\n".join(f"- {item}" for item in result.strengths)
    outline_lines = "\n".join(f"{index}. {item}" for index, item in enumerate(result.suggested_outline, start=1))
    return f"""# 研报评审包

## 基本信息
- Review ID: `{result.review_id}`
- 文件名: `{result.filename}`
- 格式: `{result.document_format}`
- 生成时间: `{result.created_at.isoformat()}`
- 得分: `{result.overall_score:.1f}/100`
- 状态: `{result.status}`
- 是否通过: `{result.passed}`

## 执行摘要
{result.executive_summary}

## 主要优点
{strengths_lines or "- 暂无记录"}

## 维度得分
{dimension_lines or "- 暂无维度得分"}

## 主要问题
{findings_lines or "未发现明显问题。"}

## 改进动作
{actions_lines or "1. 暂无额外动作。"}

## 建议重写提纲
{outline_lines or "1. 暂无建议提纲。"}
""".strip() + "\n"


def write_json(result: ReviewResult, path: Path) -> None:
    path.write_text(json.dumps(result.model_dump(mode="json"), ensure_ascii=False, indent=2), encoding="utf-8")


def write_pdf(markdown_content: str, path: Path) -> None:
    registerFont(UnicodeCIDFont("STSong-Light"))
    styles = getSampleStyleSheet()
    body = ParagraphStyle(
        "ReviewBody",
        parent=styles["BodyText"],
        fontName="STSong-Light",
        fontSize=10.5,
        leading=15,
        spaceAfter=6,
    )
    heading = ParagraphStyle(
        "ReviewHeading",
        parent=styles["Heading2"],
        fontName="STSong-Light",
        fontSize=15,
        leading=20,
        spaceBefore=8,
        spaceAfter=8,
    )
    title = ParagraphStyle(
        "ReviewTitle",
        parent=styles["Title"],
        fontName="STSong-Light",
        fontSize=20,
        leading=26,
        spaceAfter=12,
    )

    story = []
    for raw_line in markdown_content.splitlines():
        line = raw_line.strip()
        if not line:
            story.append(Spacer(1, 4))
            continue
        if line.startswith("# "):
            story.append(Paragraph(_escape(line[2:]), title))
            continue
        if line.startswith("## "):
            story.append(Paragraph(_escape(line[3:]), heading))
            continue
        if line.startswith("### "):
            story.append(Paragraph(_escape(line[4:]), body))
            continue
        if line.startswith("- "):
            story.append(Paragraph(f"&#8226; {_escape(line[2:])}", body))
            continue
        story.append(Paragraph(_escape(line), body))

    doc = SimpleDocTemplate(
        str(path),
        pagesize=A4,
        rightMargin=16 * mm,
        leftMargin=16 * mm,
        topMargin=14 * mm,
        bottomMargin=14 * mm,
    )
    doc.build(story)


def _escape(value: str) -> str:
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )
