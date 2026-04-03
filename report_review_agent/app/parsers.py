from __future__ import annotations

from io import BytesIO
from pathlib import Path

from pypdf import PdfReader

from report_review_agent.app import config
from report_review_agent.app.models import ParsedDocument


class ParseError(ValueError):
    pass


def parse_document(filename: str, payload: bytes) -> ParsedDocument:
    suffix = Path(filename).suffix.lower()
    if suffix == ".md":
        text = _decode_text(payload)
        return ParsedDocument(
            filename=filename,
            format="markdown",
            content=text,
            char_count=len(text),
        )
    if suffix == ".txt":
        text = _decode_text(payload)
        return ParsedDocument(
            filename=filename,
            format="text",
            content=text,
            char_count=len(text),
        )
    if suffix == ".pdf":
        return _parse_pdf(filename, payload)
    raise ParseError("Unsupported file type. Please upload a .md, .txt, or .pdf report.")


def _decode_text(payload: bytes) -> str:
    for encoding in ("utf-8", "utf-8-sig", "gb18030", "gbk"):
        try:
            text = payload.decode(encoding).strip()
            if text:
                return text
        except UnicodeDecodeError:
            continue
    raise ParseError("Unable to decode the uploaded text file.")


def _parse_pdf(filename: str, payload: bytes) -> ParsedDocument:
    try:
        reader = PdfReader(BytesIO(payload))
    except Exception as exc:  # pragma: no cover - parser library exceptions vary
        raise ParseError("Unable to open the uploaded PDF.") from exc

    pages: list[str] = []
    for page in reader.pages:
        extracted = page.extract_text() or ""
        cleaned = extracted.strip()
        if cleaned:
            pages.append(cleaned)

    text = "\n\n".join(pages).strip()
    if len(text) < config.MIN_PDF_TEXT_CHARS:
        raise ParseError(
            "The PDF contains too little extractable text. It may be an image-only scan; OCR is not included in this MVP."
        )

    return ParsedDocument(
        filename=filename,
        format="pdf",
        content=text,
        char_count=len(text),
        page_count=len(reader.pages),
        metadata={"extracted_pages": len(pages)},
    )
