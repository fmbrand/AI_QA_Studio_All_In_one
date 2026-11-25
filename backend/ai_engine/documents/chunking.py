"""Split parsed text into overlapping chunks that keep exact character offsets and their page/sheet.

Chunks never cross a segment boundary (a PDF page or a spreadsheet sheet), so every chunk has a single
page or sheet. Inside a segment, a chunk ends at the last paragraph, line or sentence break that fits.
"""

from dataclasses import dataclass

from .parsers import ParsedDocument

_BREAKS = ("\n\n", "\n", ". ", "? ", "! ", "; ", ", ", " ")


@dataclass(frozen=True)
class Chunk:
    index: int
    start: int
    end: int
    text: str
    page: int | None
    sheet: str | None


def _cut_point(text: str, start: int, hard_end: int, min_len: int) -> int:
    """Best place to end a chunk in text[start:hard_end], preferring natural breaks."""
    if hard_end >= len(text):
        return len(text)
    window = text[start:hard_end]
    for separator in _BREAKS:
        pos = window.rfind(separator)
        if pos >= min_len:
            return start + pos + len(separator)
    return hard_end


def chunk_document(doc: ParsedDocument, size: int = 1200, overlap: int = 200) -> list[Chunk]:
    if size <= 0 or overlap < 0 or overlap >= size:
        raise ValueError("chunk size must be positive and larger than the overlap")
    chunks: list[Chunk] = []
    for seg in doc.segments:
        pos = seg.start
        while pos < seg.end:
            hard_end = min(seg.end, pos + size)
            end = seg.end if hard_end == seg.end else _cut_point(doc.text[: seg.end], pos, hard_end, size // 2)
            # Trim whitespace at both ends without breaking the offset contract.
            s, e = pos, end
            while s < e and doc.text[s].isspace():
                s += 1
            while e > s and doc.text[e - 1].isspace():
                e -= 1
            if e > s:
                chunks.append(Chunk(len(chunks), s, e, doc.text[s:e], seg.page, seg.sheet))
            if end >= seg.end:
                break
            next_pos = max(end - overlap, pos + 1)
            # Start the overlap at a word boundary so chunks do not begin mid-word.
            space = doc.text.find(" ", next_pos, end)
            pos = space + 1 if space != -1 and space + 1 < end else next_pos
    return chunks
