"""Turn an uploaded file into plain text plus a map of where each part came from.

Every parser returns one ParsedDocument: the full text and a list of segments, each covering a
[start, end) character range of that text and naming its page (PDF) or sheet (XLSX). Chunks and
requirement citations later point back into this text by character offsets.
"""

import csv
import io
import json
from dataclasses import dataclass, field
from pathlib import Path

from .ocr import OCR

# A PDF page with less text than this is treated as scanned and sent to OCR.
SCANNED_PAGE_MIN_CHARS = 25
OCR_RENDER_SCALE = 2.0  # ~144 dpi; a good balance of accuracy and speed for documents


@dataclass
class Segment:
    start: int
    end: int
    page: int | None = None
    sheet: str | None = None
    ocr: bool = False


@dataclass
class ParsedDocument:
    text: str
    segments: list[Segment]
    meta: dict[str, object] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


class _Builder:
    """Appends text blocks, separated by blank lines, and records their segments."""

    def __init__(self) -> None:
        self.parts: list[str] = []
        self.segments: list[Segment] = []
        self.length = 0

    def add(self, text: str, *, page: int | None = None, sheet: str | None = None, ocr: bool = False) -> None:
        text = text.strip()
        if not text:
            return
        if self.parts:
            self.parts.append("\n\n")
            self.length += 2
        start = self.length
        self.parts.append(text)
        self.length += len(text)
        self.segments.append(Segment(start, self.length, page=page, sheet=sheet, ocr=ocr))

    def build(self, **kwargs: object) -> ParsedDocument:
        return ParsedDocument(text="".join(self.parts), segments=self.segments, **kwargs)  # type: ignore[arg-type]


def _normalise_newlines(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n").replace("\x00", "")


def parse_text(data: bytes) -> ParsedDocument:
    b = _Builder()
    b.add(_normalise_newlines(data.decode("utf-8-sig")))
    return b.build()


def parse_json(data: bytes) -> ParsedDocument:
    raw = data.decode("utf-8-sig")
    value = json.loads(raw)
    b = _Builder()
    # Pretty-printed JSON chunks and reads better than a single minified line.
    b.add(json.dumps(value, indent=2, ensure_ascii=False))
    return b.build(meta={"top_level_type": type(value).__name__})


def _rows_to_lines(header: list[str], rows: list[list[str]]) -> list[str]:
    """Render table rows as 'column: value' lines so each row is self-describing in a chunk."""
    lines = []
    for row in rows:
        cells = [f"{h or f'column {i + 1}'}: {v}" for i, (h, v) in enumerate(zip(header, row, strict=False)) if v]
        if cells:
            lines.append(" | ".join(cells))
    return lines


def parse_csv(data: bytes) -> ParsedDocument:
    text = _normalise_newlines(data.decode("utf-8-sig"))
    rows = [r for r in csv.reader(io.StringIO(text)) if any(c.strip() for c in r)]
    b = _Builder()
    if rows:
        header = [h.strip() for h in rows[0]]
        b.add("\n".join(_rows_to_lines(header, [[c.strip() for c in r] for r in rows[1:]])) or " | ".join(header))
    return b.build(meta={"rows": max(0, len(rows) - 1), "columns": rows[0] if rows else []})


def parse_xlsx(path: Path) -> ParsedDocument:
    from openpyxl import load_workbook

    wb = load_workbook(path, read_only=True, data_only=True)
    b = _Builder()
    sheets: dict[str, int] = {}
    try:
        for ws in wb.worksheets:
            rows = [["" if v is None else str(v).strip() for v in row] for row in ws.iter_rows(values_only=True)]
            rows = [r for r in rows if any(r)]
            sheets[ws.title] = max(0, len(rows) - 1)
            if rows:
                lines = _rows_to_lines(rows[0], rows[1:]) or [" | ".join(rows[0])]
                b.add(f"Sheet: {ws.title}\n" + "\n".join(lines), sheet=ws.title)
    finally:
        wb.close()
    return b.build(meta={"sheets": sheets})


def parse_docx(path: Path) -> ParsedDocument:
    import docx
    from docx.table import Table
    from docx.text.paragraph import Paragraph

    document = docx.Document(str(path))
    b = _Builder()
    tables = 0
    # Walk the body in order so tables stay next to the text that introduces them.
    for child in document.element.body.iterchildren():
        tag = child.tag.rsplit("}", 1)[-1]
        if tag == "p":
            paragraph = Paragraph(child, document)
            text = paragraph.text
            style = (paragraph.style.name if paragraph.style is not None else "") or ""
            if text.strip() and style.lower().startswith("heading"):
                text = "#" * min(6, int(style[-1]) if style[-1].isdigit() else 1) + " " + text
            elif text.strip() and "list" in style.lower():
                text = "- " + text
            b.add(text)
        elif tag == "tbl":
            tables += 1
            table = Table(child, document)
            rows = [[cell.text.strip() for cell in row.cells] for row in table.rows]
            if rows:
                b.add("\n".join(_rows_to_lines(rows[0], rows[1:]) or [" | ".join(rows[0])]))
    return b.build(meta={"tables": tables})


def parse_pdf(path: Path, ocr: OCR) -> ParsedDocument:
    import pypdfium2 as pdfium

    pdf = pdfium.PdfDocument(str(path))
    b = _Builder()
    ocr_pages: list[int] = []
    skipped: list[int] = []
    try:
        for index in range(len(pdf)):
            page_no = index + 1
            page = pdf[index]
            textpage = page.get_textpage()
            text = _normalise_newlines(textpage.get_text_range())
            textpage.close()
            if len(text.strip()) >= SCANNED_PAGE_MIN_CHARS:
                b.add(text, page=page_no)
            else:
                image = page.render(scale=OCR_RENDER_SCALE).to_pil()
                recognised = ocr.read(image)
                if recognised is None:
                    skipped.append(page_no)
                    b.add(text, page=page_no)  # keep whatever little text there was
                elif recognised.strip():
                    ocr_pages.append(page_no)
                    b.add(_normalise_newlines(recognised), page=page_no, ocr=True)
            page.close()
        page_count = len(pdf)
    finally:
        pdf.close()
    warnings = []
    if skipped:
        warnings.append(
            f"{len(skipped)} page(s) look scanned but OCR is not installed, so their text was skipped: "
            f"{', '.join(map(str, skipped[:20]))}"
        )
    return b.build(meta={"pages": page_count, "ocr_pages": ocr_pages}, warnings=warnings)


def parse_image(path: Path, ocr: OCR) -> ParsedDocument:
    from PIL import Image

    with Image.open(path) as image:
        size = image.size
        text = ocr.read(image)
    b = _Builder()
    warnings = []
    if text is None:
        warnings.append("OCR is not installed, so no text was read from this image.")
    else:
        b.add(_normalise_newlines(text), ocr=True)
    return b.build(meta={"width": size[0], "height": size[1]}, warnings=warnings)


def parse_file(path: Path, extension: str, ocr: OCR) -> ParsedDocument:
    """Dispatch on the (server-verified) file extension."""
    ext = extension.lower()
    if ext in (".txt", ".md"):
        return parse_text(path.read_bytes())
    if ext == ".csv":
        return parse_csv(path.read_bytes())
    if ext == ".json":
        return parse_json(path.read_bytes())
    if ext == ".pdf":
        return parse_pdf(path, ocr)
    if ext == ".docx":
        return parse_docx(path)
    if ext == ".xlsx":
        return parse_xlsx(path)
    if ext in (".png", ".jpg", ".jpeg", ".webp"):
        return parse_image(path, ocr)
    raise ValueError(f"No parser for {extension}")
