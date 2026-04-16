from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable, List
from uuid import UUID

from futures_research import config
from futures_research.models.report import ResearchReport


def persist_report_artifacts(report: ResearchReport, *, run_id: UUID) -> ResearchReport:
    output_dir = config.OUTPUT_DIR / report.target_date.isoformat()
    output_dir.mkdir(parents=True, exist_ok=True)
    slug = _artifact_slug(report.variety_code, report.symbol, run_id)
    markdown_path = output_dir / f"{slug}.md"
    pdf_path = output_dir / f"{slug}.pdf"

    markdown_path.write_text(report.content, encoding="utf-8")
    _render_pdf(report, pdf_path)

    report.markdown_path = str(markdown_path.resolve())
    report.pdf_path = str(pdf_path.resolve())
    report.markdown_url = _to_output_url(markdown_path)
    report.pdf_url = _to_output_url(pdf_path)
    return report


def remove_report_artifacts(report: ResearchReport | None) -> None:
    if report is None:
        return
    for raw_path in [report.markdown_path, report.pdf_path]:
        if not raw_path:
            continue
        path = Path(raw_path)
        try:
            if path.exists():
                path.unlink()
        except FileNotFoundError:
            continue


def _artifact_slug(variety_code: str, symbol: str, run_id: UUID) -> str:
    base = f"{variety_code}_{symbol}_{str(run_id)[:8]}"
    return re.sub(r"[^A-Za-z0-9._-]+", "_", base)


def _to_output_url(path: Path) -> str:
    relative = path.resolve().relative_to(config.OUTPUT_DIR.resolve())
    return "/outputs/" + "/".join(relative.parts)


def _render_pdf(report: ResearchReport, destination: Path) -> None:
    from reportlab.lib.enums import TA_CENTER
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.cidfonts import UnicodeCIDFont
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

    pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
    styles = _build_styles(ParagraphStyle, getSampleStyleSheet, TA_CENTER)
    story = []

    for block in _to_story_blocks(report.content, styles):
        story.append(block)

    document = SimpleDocTemplate(
        str(destination),
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=16 * mm,
        title=f"{report.variety}期货日报",
        author="Futures Research Agent",
    )
    document.build(story)


def _build_styles(ParagraphStyle, getSampleStyleSheet, TA_CENTER):
    sample = getSampleStyleSheet()
    title = ParagraphStyle(
        "TitleCN",
        parent=sample["Title"],
        fontName="STSong-Light",
        fontSize=19,
        leading=25,
        alignment=TA_CENTER,
        spaceAfter=12,
        textColor="#1b2b34",
    )
    heading = ParagraphStyle(
        "HeadingCN",
        parent=sample["Heading2"],
        fontName="STSong-Light",
        fontSize=14,
        leading=20,
        spaceBefore=8,
        spaceAfter=6,
        textColor="#0e6b5c",
    )
    subheading = ParagraphStyle(
        "SubHeadingCN",
        parent=sample["Heading3"],
        fontName="STSong-Light",
        fontSize=11.5,
        leading=17,
        spaceBefore=4,
        spaceAfter=4,
        textColor="#7a340f",
    )
    body = ParagraphStyle(
        "BodyCN",
        parent=sample["BodyText"],
        fontName="STSong-Light",
        fontSize=10.5,
        leading=17,
        firstLineIndent=0,
        spaceAfter=5,
        wordWrap="CJK",
    )
    callout = ParagraphStyle(
        "CalloutCN",
        parent=body,
        backColor="#eef6f4",
        borderPadding=7,
        borderColor="#c8ddd8",
        borderWidth=0.6,
        borderRadius=6,
        spaceAfter=8,
    )
    bullet = ParagraphStyle(
        "BulletCN",
        parent=body,
        leftIndent=12,
        bulletIndent=0,
    )
    footer = ParagraphStyle(
        "FooterCN",
        parent=body,
        fontSize=9.5,
        leading=15,
        textColor="#5f6b73",
    )
    return {
        "title": title,
        "heading": heading,
        "subheading": subheading,
        "body": body,
        "callout": callout,
        "bullet": bullet,
        "footer": footer,
    }


def _to_story_blocks(markdown: str, styles: dict) -> Iterable:
    from reportlab.lib import colors
    from reportlab.platypus import Paragraph, Spacer, Table, TableStyle

    lines = _strip_internal_markdown_blocks(markdown).splitlines()
    index = 0
    while index < len(lines):
        raw_line = lines[index]
        line = raw_line.strip()
        if line and "|" in line and index + 1 < len(lines) and _is_table_divider(lines[index + 1]):
            header = _split_table_row(line)
            rows: List[List[str]] = []
            index += 2
            while index < len(lines) and lines[index].strip() and "|" in lines[index]:
                if not _is_table_divider(lines[index]):
                    rows.append(_split_table_row(lines[index]))
                index += 1
            yield _render_table(header, rows, styles, Paragraph, Table, TableStyle, colors)
            continue
        if not line or line.startswith("<!--"):
            index += 1
            continue
        if line == "---":
            yield Spacer(1, 6)
            index += 1
            continue
        if line.startswith("# "):
            yield Paragraph(_escape(_strip_markdown(line[2:])), styles["title"])
            index += 1
            continue
        if line.startswith("## "):
            yield Spacer(1, 4)
            yield Paragraph(_escape(_strip_markdown(line[3:])), styles["heading"])
            index += 1
            continue
        if line.startswith("### "):
            yield Paragraph(_escape(_strip_markdown(line[4:])), styles["subheading"])
            index += 1
            continue
        if line.startswith("> "):
            yield Paragraph(_escape(_strip_markdown(line[2:])), styles["callout"])
            index += 1
            continue
        if re.match(r"^\d+\.\s+", line):
            yield Paragraph(_escape(_strip_markdown(line)), styles["bullet"])
            index += 1
            continue
        if line.startswith("- "):
            yield Paragraph(_escape(_strip_markdown("• " + line[2:])), styles["bullet"])
            index += 1
            continue
        style = styles["footer"] if line.startswith("*") and line.endswith("*") else styles["body"]
        yield Paragraph(_escape(_strip_markdown(line)), style)
        index += 1


def _split_table_row(line: str) -> List[str]:
    text = line.strip().strip("|")
    cells = []
    current = ""
    for index, char in enumerate(text):
        previous = text[index - 1] if index else ""
        if char == "|" and previous != "\\":
            cells.append(current.replace("\\|", "|").strip())
            current = ""
        else:
            current += char
    cells.append(current.replace("\\|", "|").strip())
    return cells


def _is_table_divider(line: str) -> bool:
    cells = _split_table_row(line)
    return len(cells) > 1 and all(re.match(r"^:?-{3,}:?$", cell.strip()) for cell in cells)


def _render_table(header, rows, styles, Paragraph, Table, TableStyle, colors):
    width = max([len(header)] + [len(row) for row in rows] or [1])

    def cell(text: str):
        return Paragraph(_escape(_strip_markdown(text)), styles["body"])

    table_data = [
        [cell(header[index] if index < len(header) else "") for index in range(width)]
    ]
    for row in rows:
        table_data.append([cell(row[index] if index < len(row) else "") for index in range(width)])
    table = Table(table_data, repeatRows=1, hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, -1), "STSong-Light"),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f0f3f4")),
                ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor("#16181b")),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#d9dee3")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    return table


def _strip_markdown(text: str) -> str:
    stripped = _strip_internal_markdown_blocks(text)
    stripped = re.sub(r"\[(?:F|G)\d+\]", "", stripped)
    stripped = re.sub(r"(?<![A-Za-z0-9])(?:F|G)\d+(?![A-Za-z0-9])", "", stripped)
    stripped = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", stripped)
    stripped = stripped.replace("**", "").replace("*", "")
    stripped = re.sub(r"`([^`]+)`", r"\1", stripped)
    stripped = re.sub(r"[ \t]+([，。；：、,.])", r"\1", stripped)
    stripped = re.sub(r"[ \t]{2,}", " ", stripped)
    return stripped


def _strip_internal_markdown_blocks(markdown: str) -> str:
    without_comments = re.sub(r"<!--.*?-->", "", markdown or "", flags=re.DOTALL)
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


def _escape(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace("\n", "<br/>")
    )
