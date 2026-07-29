"""
vectorstore/pinecone_store.py
Pinecone vector store - one namespace per paper.
"""
import os
from typing import List, Dict, Any
from loguru import logger
from pinecone import Pinecone, ServerlessSpec
from config import get_settings

settings = get_settings()


class PaperVectorStore:
    """One Pinecone index, one namespace per paper."""

    def __init__(self, embeddings):
        self.embeddings = embeddings
        self.api_key    = settings.pinecone_api_key or os.getenv("PINECONE_API_KEY", "")

        # Set env var so langchain_pinecone can find it
        os.environ["PINECONE_API_KEY"] = self.api_key

        self.pc         = Pinecone(api_key=self.api_key)
        self.index_name = settings.pinecone_index_name
        self._stores: Dict[str, Any] = {}
        self._ensure_index()

    def _ensure_index(self):
        existing = [idx.name for idx in self.pc.list_indexes()]
        if self.index_name not in existing:
            logger.info(f"Creating Pinecone index: {self.index_name}")
            self.pc.create_index(
                name=self.index_name,
                dimension=1024,
                metric="cosine",
                spec=ServerlessSpec(
                    cloud="aws",
                    region=settings.pinecone_environment
                ),
            )
        else:
            logger.info(f"Connected to Pinecone index: {self.index_name}")

    def index_paper(self, chunks: List, paper_id: str) -> int:
        """Embed and store all chunks for one paper."""
        from langchain_pinecone import PineconeVectorStore

        logger.info(f"Indexing paper {paper_id}: {len(chunks)} chunks")

        texts     = [c.text for c in chunks]
        metadatas = [{
            "paper_id":    c.paper_id,
            "chunk_id":    c.chunk_id,
            "chunk_index": c.chunk_index,
            "section":     c.section,
            "page_number": c.page_number,
            "filename":    c.filename,
            "title":       c.title,
            "text_preview": c.text[:900],
        } for c in chunks]

        store = PineconeVectorStore.from_texts(
            texts=texts,
            embedding=self.embeddings,
            metadatas=metadatas,
            index_name=self.index_name,
            namespace=paper_id,
        )
        self._stores[paper_id] = store
        logger.info(f"Indexed {len(chunks)} chunks in namespace '{paper_id}'")
        return len(chunks)

    def get_retriever(self, paper_id: str, top_k: int = None):
        from langchain_pinecone import PineconeVectorStore

        k = top_k or settings.retrieval_top_k
        if paper_id not in self._stores:
            self._stores[paper_id] = PineconeVectorStore(
                index=self.pc.Index(self.index_name),
                embedding=self.embeddings,
                namespace=paper_id,
            )
        return self._stores[paper_id].as_retriever(
            search_type="similarity",
            search_kwargs={"k": k},
        )

    def similarity_search(
        self, query: str, paper_id: str, top_k: int = None
    ) -> List[Dict[str, Any]]:
        k        = top_k or settings.retrieval_top_k
        retriever = self.get_retriever(paper_id, k)
        docs     = retriever.invoke(query)
        results  = []
        for doc in docs:
            results.append({
                "text":        doc.page_content,
                "paper_id":    doc.metadata.get("paper_id", paper_id),
                "filename":    doc.metadata.get("filename", ""),
                "title":       doc.metadata.get("title", ""),
                "section":     doc.metadata.get("section", ""),
                "page_number": doc.metadata.get("page_number", 0),
                "chunk_index": doc.metadata.get("chunk_index", 0),
            })
        return results

    def delete_paper(self, paper_id: str):
        try:
            index = self.pc.Index(self.index_name)
            index.delete(delete_all=True, namespace=paper_id)
            self._stores.pop(paper_id, None)
            logger.info(f"Deleted namespace: {paper_id}")
        except Exception as e:
            logger.warning(f"Could not delete namespace {paper_id}: {e}")

    def test_connection(self) -> bool:
        try:
            self.pc.Index(self.index_name).describe_index_stats()
            return True
        except Exception:
            return False