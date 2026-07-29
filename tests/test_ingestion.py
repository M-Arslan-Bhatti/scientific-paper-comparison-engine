"""tests/test_ingestion.py"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from ingestion.chunker import SmartChunker
from ingestion.pdf_loader import ParsedPaper, DocumentElement


def make_paper(num_elements=50):
    elements = [
        DocumentElement(
            element_id=f"p1_el_{i}",
            paper_id="paper1",
            element_type="NarrativeText",
            text=f"This is sentence number {i} discussing RAG systems and embeddings. " * 3,
            page_number=i // 10 + 1,
            section="Introduction" if i < 25 else "Methodology",
        )
        for i in range(num_elements)
    ]
    return ParsedPaper(
        paper_id="paper1",
        filename="test_paper.pdf",
        title="A Test Research Paper on RAG",
        elements=elements,
    )


class TestSmartChunker:

    def setup_method(self):
        self.chunker = SmartChunker()

    def test_produces_chunks(self):
        paper = make_paper(50)
        chunks = self.chunker.chunk_paper(paper)
        assert len(chunks) > 0

    def test_chunks_respect_sections(self):
        paper = make_paper(50)
        chunks = self.chunker.chunk_paper(paper)
        sections = set(c.section for c in chunks)
        assert "Introduction" in sections or "Methodology" in sections

    def test_chunk_ids_unique(self):
        paper = make_paper(50)
        chunks = self.chunker.chunk_paper(paper)
        ids = [c.chunk_id for c in chunks]
        assert len(ids) == len(set(ids))

    def test_chunks_have_text(self):
        paper = make_paper(30)
        chunks = self.chunker.chunk_paper(paper)
        for c in chunks:
            assert len(c.text.strip()) > 10
