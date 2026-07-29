"""
ingestion/chunker.py

Smart chunker that works with DocumentElement objects from the ingestion pipeline.
Respects section boundaries — chunks do not cross section headings.
Uses LangChain's RecursiveCharacterTextSplitter internally.
"""
from typing import List
from dataclasses import dataclass
from loguru import logger
from langchain.text_splitter import RecursiveCharacterTextSplitter
from ingestion.pdf_loader import ParsedPaper
from config import get_settings

settings = get_settings()


@dataclass
class Chunk:
    """A single text chunk ready for embedding and storage."""
    chunk_id: str
    paper_id: str
    text: str
    chunk_index: int
    section: str
    page_number: int
    element_type: str
    filename: str
    title: str


class SmartChunker:
    """
    Converts ParsedPaper elements into Chunk objects.

    Strategy:
    1. Group elements by section.
    2. Concatenate elements within each section into a block.
    3. Split each block using LangChain RecursiveCharacterTextSplitter
       at 512 tokens (approx 2048 chars) with 50-token (200-char) overlap.
    4. Tag every chunk with its source metadata.

    This ensures chunks do not span section boundaries, which improves
    retrieval precision (a retrieved chunk about 'methodology' will not
    accidentally contain text from 'results').
    """

    def __init__(self):
        # 1 token ~= 4 chars for English academic text
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=settings.chunk_size * 4,      # characters
            chunk_overlap=settings.chunk_overlap * 4,
            separators=["\n\n", "\n", ". ", " ", ""],
            length_function=len,
        )

    def chunk_paper(self, paper: ParsedPaper) -> List[Chunk]:
        """Convert a ParsedPaper into a list of Chunks."""
        chunks: List[Chunk] = []
        chunk_index = 0

        # Group elements by section
        sections: dict = {}
        for el in paper.elements:
            key = el.section or "General"
            if key not in sections:
                sections[key] = []
            sections[key].append(el)

        for section_name, elements in sections.items():
            # Build section text block
            section_block = "\n\n".join(
                el.text for el in elements
                if el.element_type not in ("PageBreak",) and len(el.text) > 10
            )

            if not section_block.strip():
                continue

            # Split the section block
            split_texts = self.splitter.split_text(section_block)

            # Use the page number of the first element in this section
            page_num = elements[0].page_number if elements else 0

            for text in split_texts:
                if len(text.strip()) < 20:
                    continue

                chunks.append(Chunk(
                    chunk_id=f"{paper.paper_id}_chunk_{chunk_index}",
                    paper_id=paper.paper_id,
                    text=text.strip(),
                    chunk_index=chunk_index,
                    section=section_name,
                    page_number=page_num,
                    element_type="mixed",
                    filename=paper.filename,
                    title=paper.title,
                ))
                chunk_index += 1

        logger.info(
            f"Chunked '{paper.filename}': {len(chunks)} chunks "
            f"across {len(sections)} sections"
        )
        return chunks
