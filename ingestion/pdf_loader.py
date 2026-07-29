"""
ingestion/pdf_loader.py

Multimodal ingestion pipeline.
Strategy: pdfplumber for fast reliable extraction.
Tables are extracted as structured text.
This avoids heavy ML models (Table Transformer, ONNX)
while still capturing table content from research papers.
"""
import os
import re
import uuid
from pathlib import Path
from typing import List, Tuple
from dataclasses import dataclass, field
from loguru import logger

try:
    import pdfplumber
    PDFPLUMBER_AVAILABLE = True
except ImportError:
    PDFPLUMBER_AVAILABLE = False

try:
    from unstructured.partition.pdf import partition_pdf
    UNSTRUCTURED_AVAILABLE = True
except ImportError:
    UNSTRUCTURED_AVAILABLE = False


@dataclass
class DocumentElement:
    """A single extracted element from a research paper."""
    element_id: str
    paper_id: str
    element_type: str
    text: str
    page_number: int = 0
    section: str = ""


@dataclass
class ParsedPaper:
    """Result of parsing one PDF file."""
    paper_id: str
    filename: str
    title: str
    elements: List[DocumentElement] = field(default_factory=list)
    total_pages: int = 0


class MultimodalPDFLoader:
    """
    PDF loader using pdfplumber as primary engine.
    - Extracts text paragraphs
    - Extracts tables as formatted text
    - Detects section headings
    - Fast and reliable — no heavy ML models
    """

    def load(self, file_path: str, filename: str) -> ParsedPaper:
        """Main entry point. Returns ParsedPaper with all elements."""
        paper_id = str(uuid.uuid4())[:8]
        logger.info(f"Loading: {filename} (ID: {paper_id})")

        if PDFPLUMBER_AVAILABLE:
            return self._load_with_pdfplumber(file_path, filename, paper_id)
        elif UNSTRUCTURED_AVAILABLE:
            return self._load_with_unstructured_fast(file_path, filename, paper_id)
        else:
            raise RuntimeError("Neither pdfplumber nor unstructured is installed.")

    def _load_with_pdfplumber(
        self, file_path: str, filename: str, paper_id: str
    ) -> ParsedPaper:
        """
        Primary method: pdfplumber for text + table extraction.
        Fast, reliable, no ML models needed.
        """
        elements = []
        detected_title = filename.replace(".pdf", "")
        title_found = False
        current_section = "General"
        total_pages = 0

        with pdfplumber.open(file_path) as pdf:
            total_pages = len(pdf.pages)

            for page_num, page in enumerate(pdf.pages, start=1):

                # ── Extract tables first ──────────────────────────────────
                tables = page.extract_tables() or []
                table_bboxes = []

                for table in tables:
                    if not table:
                        continue

                    # Convert table rows to readable text
                    table_lines = []
                    for row in table:
                        if row:
                            cleaned = [str(cell).strip() if cell else "" for cell in row]
                            table_lines.append(" | ".join(cleaned))

                    table_text = "\n".join(table_lines)
                    if len(table_text.strip()) < 10:
                        continue

                    elements.append(DocumentElement(
                        element_id=f"{paper_id}_el_{len(elements)}",
                        paper_id=paper_id,
                        element_type="Table",
                        text=f"[TABLE]\n{table_text}",
                        page_number=page_num,
                        section=current_section,
                    ))

                # ── Extract text ──────────────────────────────────────────
                raw_text = page.extract_text() or ""
                lines = raw_text.split("\n")

                for line in lines:
                    line = line.strip()

                    # Skip very short lines and page numbers
                    if len(line) < 4:
                        continue
                    if re.fullmatch(r"\d+", line):
                        continue

                    # Detect title from first page
                    if not title_found and page_num == 1 and len(line) > 20:
                        detected_title = line[:200]
                        title_found = True

                    # Detect section headings
                    if self._is_heading(line):
                        current_section = line[:100]
                        elements.append(DocumentElement(
                            element_id=f"{paper_id}_el_{len(elements)}",
                            paper_id=paper_id,
                            element_type="Title",
                            text=line,
                            page_number=page_num,
                            section=current_section,
                        ))
                    else:
                        elements.append(DocumentElement(
                            element_id=f"{paper_id}_el_{len(elements)}",
                            paper_id=paper_id,
                            element_type="NarrativeText",
                            text=line,
                            page_number=page_num,
                            section=current_section,
                        ))

        logger.info(
            f"Parsed '{filename}': {len(elements)} elements, "
            f"{total_pages} pages, title='{detected_title[:60]}'"
        )

        return ParsedPaper(
            paper_id=paper_id,
            filename=filename,
            title=detected_title,
            elements=elements,
            total_pages=total_pages,
        )

    def _is_heading(self, line: str) -> bool:
        """Detect if a line is a section heading."""
        # Common IEEE paper section patterns
        patterns = [
            r"^\d+\.\s+[A-Z]",           # 1. Introduction
            r"^[IVX]+\.\s+[A-Z]",        # I. Introduction
            r"^(Abstract|Introduction|Conclusion|References|Methodology|Results|Discussion|Related Work|Background|Evaluation|Experiments)",
        ]
        for pat in patterns:
            if re.match(pat, line.strip()):
                return True
        # All caps short line = heading
        if line.isupper() and 3 < len(line) < 60:
            return True
        return False

    def _load_with_unstructured_fast(
        self, file_path: str, filename: str, paper_id: str
    ) -> ParsedPaper:
        """Fallback: unstructured with fast strategy (no ML models)."""
        elements_raw = partition_pdf(
            filename=file_path,
            strategy="fast",
            infer_table_structure=False,
            include_page_breaks=False,
            extract_images_in_pdf=False,
        )

        elements = []
        detected_title = filename.replace(".pdf", "")
        title_found = False
        current_section = "General"

        for el in elements_raw:
            raw_text = str(el).strip()
            if not raw_text or len(raw_text) < 4:
                continue

            el_type = type(el).__name__
            page_num = 0
            if hasattr(el, "metadata") and el.metadata:
                page_num = getattr(el.metadata, "page_number", 0) or 0

            if el_type == "Title":
                if not title_found and len(raw_text) > 15:
                    detected_title = raw_text[:200]
                    title_found = True
                current_section = raw_text[:100]

            elements.append(DocumentElement(
                element_id=f"{paper_id}_el_{len(elements)}",
                paper_id=paper_id,
                element_type=el_type,
                text=raw_text,
                page_number=page_num,
                section=current_section,
            ))

        return ParsedPaper(
            paper_id=paper_id,
            filename=filename,
            title=detected_title,
            elements=elements,
        )