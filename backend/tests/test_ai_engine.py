"""Unit tests for the ai_engine package: parsers, chunking, schema conversion, grounding, embeddings."""

import tempfile
from pathlib import Path

import pytest

from ai_engine.documents.chunking import chunk_document
from ai_engine.documents.ocr import OCR, find_tesseract
from ai_engine.documents.parsers import ParsedDocument, Segment, parse_csv, parse_file, parse_json, parse_text
from ai_engine.embeddings import HashEmbedder, cosine
from ai_engine.grounding import SourceChunk, ground
from ai_engine.llm.schema import strict_schema
from ai_engine.prompts import requirement_extraction as prompt
from tests.files import make_docx, make_pdf, make_png, make_xlsx

NO_OCR = OCR(tesseract_cmd="definitely-not-installed-tesseract")
HAS_TESSERACT = find_tesseract(None) is not None


def _write(data: bytes, suffix: str) -> Path:
    fh = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)  # noqa: SIM115
    fh.write(data)
    fh.close()
    return Path(fh.name)


# ---- parsers ------------------------------------------------------------------------------------


def test_pdf_pages_are_kept_as_segments() -> None:
    path = _write(
        make_pdf([["Booking rules", "A customer can book a slot."], ["Coupons expire after 30 days."]]), ".pdf"
    )
    doc = parse_file(path, ".pdf", NO_OCR)
    assert "A customer can book a slot." in doc.text
    assert [s.page for s in doc.segments] == [1, 2]
    second = doc.segments[1]
    assert doc.text[second.start : second.end].strip() == "Coupons expire after 30 days."
    assert doc.meta["pages"] == 2 and doc.warnings == []


def test_scanned_pdf_page_without_ocr_is_reported() -> None:
    path = _write(make_pdf([["Readable page with enough text to count."], []]), ".pdf")
    doc = parse_file(path, ".pdf", NO_OCR)
    assert len(doc.warnings) == 1 and "OCR is not installed" in doc.warnings[0]
    assert "2" in doc.warnings[0]


def test_docx_keeps_headings_and_tables_in_order() -> None:
    data = make_docx(
        ["Checkout", "Payment is taken before confirmation."], table=[["Field", "Rule"], ["Email", "Required"]]
    )
    doc = parse_file(_write(data, ".docx"), ".docx", NO_OCR)
    assert doc.text.startswith("# Checkout")
    assert doc.text.index("Payment is taken") < doc.text.index("Field: Email | Rule: Required")
    assert doc.meta["tables"] == 1


def test_xlsx_sheets_become_segments() -> None:
    data = make_xlsx({"Rules": [["Rule", "Limit"], ["One coupon per order", 1]], "Empty": []})
    doc = parse_file(_write(data, ".xlsx"), ".xlsx", NO_OCR)
    assert [s.sheet for s in doc.segments] == ["Rules"]
    assert "Rule: One coupon per order | Limit: 1" in doc.text
    assert doc.meta["sheets"] == {"Rules": 1, "Empty": 0}


def test_text_csv_json_parsers() -> None:
    assert parse_text(b"\xef\xbb\xbfline one\r\nline two").text == "line one\nline two"
    csv_doc = parse_csv(b"name,role\nAda,admin\n,\n")
    assert csv_doc.text == "name: Ada | role: admin" and csv_doc.meta["rows"] == 1
    assert parse_json(b'{"a": 1}').text == '{\n  "a": 1\n}'


def test_image_without_ocr_warns() -> None:
    doc = parse_file(_write(make_png("Book now"), ".png"), ".png", NO_OCR)
    assert doc.text == "" and doc.warnings and doc.meta["width"] == 900


@pytest.mark.skipif(not HAS_TESSERACT, reason="Tesseract is not installed")
def test_image_ocr_reads_text() -> None:
    doc = parse_file(_write(make_png("Confirm booking"), ".png"), ".png", OCR(None))
    assert "confirm" in doc.text.lower() and doc.segments[0].ocr


# ---- chunking -----------------------------------------------------------------------------------


def _doc(text: str, pages: list[tuple[int, int, int]]) -> ParsedDocument:
    return ParsedDocument(text=text, segments=[Segment(s, e, page=p) for s, e, p in pages])


def test_chunks_keep_exact_offsets_and_overlap() -> None:
    paragraph = "The customer selects a date. " * 20
    text = (paragraph.strip() + "\n\n") * 6
    doc = _doc(text.strip(), [(0, len(text.strip()), 1)])
    chunks = chunk_document(doc, size=300, overlap=60)
    assert len(chunks) > 3
    for c in chunks:
        assert doc.text[c.start : c.end] == c.text
        assert len(c.text) <= 300
        assert not c.text[0].isspace() and not c.text[-1].isspace()
    for a, b in zip(chunks, chunks[1:], strict=False):
        assert b.start < a.end, "consecutive chunks overlap"
        assert doc.text[b.start - 1] == " " or b.start == a.end, "overlap starts at a word boundary"
    assert chunks[-1].end == len(doc.text)


def test_chunks_never_cross_pages() -> None:
    text = "Page one text. " * 10 + "\n\n" + "Page two text. " * 10
    split = text.index("\n\n")
    doc = _doc(text, [(0, split, 1), (split + 2, len(text), 2)])
    chunks = chunk_document(doc, size=100, overlap=20)
    for c in chunks:
        assert (c.page == 1 and c.end <= split) or (c.page == 2 and c.start >= split + 2)
    with pytest.raises(ValueError):
        chunk_document(doc, size=50, overlap=50)


# ---- schema, embeddings -------------------------------------------------------------------------


def test_strict_schema_is_closed_and_fully_required() -> None:
    schema = strict_schema(prompt.ExtractionOutput)
    item = schema["properties"]["requirements"]["items"]
    assert schema["additionalProperties"] is False and item["additionalProperties"] is False
    assert set(item["required"]) == set(item["properties"])
    assert "$defs" not in schema and "$ref" not in str(schema)
    # A field called "title" survives; the JSON-Schema "title" keyword does not.
    assert item["properties"]["title"] == {"type": "string", "description": item["properties"]["title"]["description"]}
    assert "title" in item["required"]
    assert item["properties"]["module"]["anyOf"] == [{"type": "string"}, {"type": "null"}]


def test_hash_embedder_is_deterministic_and_normalised() -> None:
    e = HashEmbedder()
    a, b, c = e.embed(["coupon expired", "coupon expired", "provider accepts booking"])
    assert a == b and len(a) == 384
    assert abs(cosine(a, a) - 1.0) < 1e-9 and cosine(a, c) < 0.5


# ---- grounding ----------------------------------------------------------------------------------


def _chunk(sid: str, text: str, start: int = 100) -> SourceChunk:
    return SourceChunk(sid, f"chunk-{sid}", "doc-1", "ver-1", "Booking spec", 3, None, start, text)


def _req(citations: list[tuple[str, str]], title: str = "Customer can book a slot") -> prompt.ExtractedRequirement:
    return prompt.ExtractedRequirement(
        type="functional", title=title, description=title, module=None, feature=None, user_role=None,
        priority="high", acceptance_criteria=[], confidence="high",
        citations=[prompt.Citation(source_id=s, quote=q) for s, q in citations],
    )  # fmt: skip


def test_grounding_keeps_real_quotes_with_offsets() -> None:
    chunks = {"S1": _chunk("S1", "Intro.  A customer   can book\nan available slot. End.")}
    report = ground([_req([("S1", "a customer can book an available slot")])], chunks)
    assert len(report.kept) == 1 and report.discarded_uncited == 0
    ref = report.kept[0].source_refs[0]
    assert ref["quote"] == "A customer   can book\nan available slot"
    assert ref["char_start"] == 100 + chunks["S1"].text.index("A customer")
    assert ref["char_end"] - ref["char_start"] == len(ref["quote"])
    assert ref["page"] == 3 and ref["document_title"] == "Booking spec"


def test_grounding_drops_fabricated_quotes_and_unknown_sources() -> None:
    chunks = {"S1": _chunk("S1", "Coupons expire after 30 days.")}
    report = ground(
        [
            _req([("S1", "Coupons never expire")]),  # quote not in source
            _req([("S9", "Coupons expire after 30 days")]),  # unknown source
            _req([("S1", "expire")]),  # too short to be evidence
            _req([("S1", "Coupons expire after 30 days"), ("S2", "made up")], title="kept"),
        ],
        chunks,
    )
    assert report.discarded_uncited == 3
    assert [g.item.title for g in report.kept] == ["kept"]
    assert report.dropped_citations == 4
