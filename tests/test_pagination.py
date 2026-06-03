"""Page-level provenance (FR-7): chunks carry a source page, and grounding
returns it so a filled value can cite the page it came from."""
from __future__ import annotations

from app import ingest, filler


def test_chunk_text_carries_page():
    chunks = ingest.chunk_text("Hello world. " * 40, "scan.pdf", page=4)
    assert chunks and all(c.page == 4 for c in chunks)


def test_read_document_pages_txt_is_unpaginated(tmp_path):
    p = tmp_path / "x.txt"
    p.write_text("some case text here")
    assert ingest.read_document_pages(str(p)) == [(None, "some case text here")]


def test_locate_evidence_returns_document_and_page():
    passages = [
        {"document": "intake.pdf", "text": "The client is Jane Roe of Oakland.", "page": 7},
    ]
    snippet, doc, page = filler._locate_evidence("Jane Roe", passages)
    assert doc == "intake.pdf"
    assert page == 7
    assert "Jane Roe" in snippet
