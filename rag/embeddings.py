"""
rag/embeddings.py
Amazon Titan Embeddings via AWS Bedrock.
Wrapped as LangChain-compatible Embeddings class.
"""
import json
import boto3
from typing import List
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential
from langchain_core.embeddings import Embeddings
from config import get_settings

settings = get_settings()


class TitanEmbeddings(Embeddings):
    """
    LangChain Embeddings using Amazon Titan via Bedrock.
    Works with both titan-embed-text-v2 and titan-embed-image-v1.
    """

    def __init__(self):
        client_kwargs = {
            "service_name": "bedrock-runtime",
            "region_name": settings.aws_default_region,
        }
        # Only pass explicit keys when set — otherwise fall back to boto3's
        # default credential chain (IAM role, e.g. App Runner instance role).
        if settings.aws_access_key_id and settings.aws_secret_access_key:
            client_kwargs["aws_access_key_id"] = settings.aws_access_key_id
            client_kwargs["aws_secret_access_key"] = settings.aws_secret_access_key
        self._client = boto3.client(**client_kwargs)
        self.model_id = settings.bedrock_embed_model
        logger.info(f"TitanEmbeddings ready. Model: {self.model_id}")

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=10))
    def _embed_single(self, text: str) -> List[float]:
        """Call Bedrock Titan for one text — simple format only."""
        body = json.dumps({
            "inputText": text[:8000],
        })
        response = self._client.invoke_model(
            modelId=self.model_id,
            body=body,
            contentType="application/json",
            accept="application/json",
        )
        result = json.loads(response["body"].read())
        return result["embedding"]

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Embed list of documents — called by LangChain during indexing."""
        embeddings = []
        for i, text in enumerate(texts):
            emb = self._embed_single(text)
            embeddings.append(emb)
            if (i + 1) % 5 == 0:
                logger.info(f"  Embedded {i+1}/{len(texts)} chunks")
        return embeddings

    def embed_query(self, text: str) -> List[float]:
        """Embed single query — called by LangChain at retrieval time."""
        return self._embed_single(text)
