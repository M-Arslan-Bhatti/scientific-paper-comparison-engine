"""
rag/comparison.py
Multi-paper comparison logic using LangChain.
"""
import json
from typing import List, Dict, Any
from dataclasses import dataclass, field
from loguru import logger
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from rag.chain import query_single_paper
from rag.bedrock_llm import get_bedrock_llm
from vectorstore.pinecone_store import PaperVectorStore
from config import get_settings

settings = get_settings()


@dataclass
class ComparisonItem:
    description: str
    sources: List[str] = field(default_factory=list)
    confidence: float = 0.8


@dataclass
class ComparisonResult:
    agreements: List[ComparisonItem] = field(default_factory=list)
    contradictions: List[ComparisonItem] = field(default_factory=list)
    methodology_differences: List[ComparisonItem] = field(default_factory=list)
    research_gaps: List[ComparisonItem] = field(default_factory=list)


PER_PAPER_QUESTIONS = [
    "What are the main findings, methodology, key results, limitations, and future work of this paper?",
]

SYNTHESIS_SYSTEM = """You are an expert scientific literature analyst.
You receive summaries from multiple research papers on the same topic.
Your job is to identify:
1. AGREEMENTS: findings or claims multiple papers agree on
2. CONTRADICTIONS: findings where papers directly disagree
3. METHODOLOGY DIFFERENCES: different approaches, datasets, or evaluation methods
4. RESEARCH GAPS: open questions, limitations, or future work identified

Return ONLY a valid JSON object. No text before or after the JSON.
Use this exact schema:
{{
  "agreements": [{{"description": "...", "sources": ["PAPER_NAME: evidence text"], "confidence": 0.9}}],
  "contradictions": [{{"description": "...", "sources": ["PAPER_NAME1: evidence", "PAPER_NAME2: evidence"], "confidence": 0.85}}],
  "methodology_differences": [{{"description": "...", "sources": ["PAPER_NAME: evidence"], "confidence": 0.8}}],
  "research_gaps": [{{"description": "...", "sources": ["PAPER_NAME: evidence"], "confidence": 0.75}}]
}}

IMPORTANT: In the sources list, use the actual paper filename/title as PAPER_NAME.
Do NOT use paper IDs like "38f0a295". Use the real paper name provided to you.

Rules:
- Every item MUST cite which paper it comes from using the paper filename
- Do NOT invent findings not in the summaries
- Empty list [] is fine if nothing found
- Return ONLY the JSON, nothing else"""

SYNTHESIS_HUMAN = """Here are the per-paper summaries:

{paper_summaries}

User comparison focus: {user_query}

Produce the structured JSON comparison now. Use paper filenames in sources, not IDs:"""


class MultiPaperComparator:

    def __init__(self, vector_store: PaperVectorStore):
        self.vector_store = vector_store
        self.llm = get_bedrock_llm()

    def _get_paper_label(self, paper_id: str, meta: dict) -> str:
        """Return a clean readable label for a paper."""
        filename = meta.get("filename", "")
        title    = meta.get("title", "")

        # Clean up filename - remove extension
        if filename:
            name = filename.replace(".pdf", "").strip()
            # Shorten if too long
            if len(name) > 40:
                name = name[:40] + "..."
            return name

        # Fallback to title
        if title and len(title) > 5:
            return title[:50]

        return paper_id

    def _collect_paper_context(
        self,
        paper_ids: List[str],
        paper_metadata: Dict[str, Dict],
        user_query: str,
    ) -> Dict[str, str]:
        paper_contexts = {}

        for paper_id in paper_ids:
            meta  = paper_metadata.get(paper_id, {})
            label = self._get_paper_label(paper_id, meta)
            logger.info(f"Querying paper: {label} ({paper_id})")

            retriever = self.vector_store.get_retriever(paper_id)
            answers   = []

            all_questions = PER_PAPER_QUESTIONS + [user_query]
            for question in all_questions:
                answer = query_single_paper(retriever, self.llm, question)
                answers.append(f"Q: {question}\nA: {answer}")

            paper_contexts[paper_id] = "\n\n".join(answers)

        return paper_contexts

    def _synthesise(
        self,
        paper_contexts: Dict[str, str],
        paper_metadata: Dict[str, Dict],
        user_query: str,
    ) -> ComparisonResult:
        summary_blocks = []
        for paper_id, context in paper_contexts.items():
            meta  = paper_metadata.get(paper_id, {})
            label = self._get_paper_label(paper_id, meta)

            # Give Claude the readable label to use in sources
            summary_blocks.append(
                f"=== PAPER NAME: {label} (ID: {paper_id}) ===\n{context}"
            )

        combined = "\n\n".join(summary_blocks)

        synthesis_prompt = ChatPromptTemplate.from_messages([
            ("system", SYNTHESIS_SYSTEM),
            ("human",  SYNTHESIS_HUMAN),
        ])

        chain = synthesis_prompt | self.llm | StrOutputParser()

        logger.info("Running synthesis chain across all papers...")
        raw = chain.invoke({
            "paper_summaries": combined,
            "user_query":      user_query,
        })

        return self._parse_output(raw, paper_metadata)

    def _parse_output(self, raw: str, paper_metadata: dict) -> ComparisonResult:
        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        raw = raw.strip()

        try:
            data = json.loads(raw)
        except json.JSONDecodeError as e:
            logger.error(f"JSON parse error: {e}. Raw: {raw[:300]}")
            # Try to recover truncated JSON by finding last complete item
            try:
                # Find last complete closing bracket
                for end_char in [']}', ']\n}', ']\r\n}']:
                    last_pos = raw.rfind(end_char)
                    if last_pos > 0:
                        recovered = raw[:last_pos + len(end_char)] + '}'
                        # Count open braces to close properly
                        data = json.loads(recovered)
                        logger.info("Recovered truncated JSON successfully")
                        break
                else:
                    data = {}
            except Exception:
                data = {}

        # Build ID -> label mapping for post-processing
        id_to_label = {}
        for pid, meta in paper_metadata.items():
            id_to_label[pid] = self._get_paper_label(pid, meta)

        def clean_sources(sources: list) -> list:
            """Replace any raw paper IDs with readable names."""
            cleaned = []
            for src in sources:
                src_str = str(src)
                for pid, label in id_to_label.items():
                    src_str = src_str.replace(pid, label)
                cleaned.append(src_str)
            return cleaned

        def parse_items(items_data) -> List[ComparisonItem]:
            result = []
            for item in (items_data or []):
                if isinstance(item, dict):
                    sources = clean_sources(item.get("sources", []))
                    result.append(ComparisonItem(
                        description=item.get("description", ""),
                        sources=sources,
                        confidence=item.get("confidence", 0.8),
                    ))
            return result

        return ComparisonResult(
            agreements=parse_items(data.get("agreements", [])),
            contradictions=parse_items(data.get("contradictions", [])),
            methodology_differences=parse_items(data.get("methodology_differences", [])),
            research_gaps=parse_items(data.get("research_gaps", [])),
        )

    def compare(
        self,
        paper_ids: List[str],
        paper_metadata: Dict[str, Dict],
        user_query: str = "Compare these papers comprehensively",
    ) -> ComparisonResult:
        logger.info(f"Starting comparison of {len(paper_ids)} papers")

        paper_contexts = self._collect_paper_context(
            paper_ids, paper_metadata, user_query
        )
        result = self._synthesise(paper_contexts, paper_metadata, user_query)

        total = (
            len(result.agreements) +
            len(result.contradictions) +
            len(result.methodology_differences) +
            len(result.research_gaps)
        )
        logger.info(f"Comparison complete: {total} total findings")
        return result