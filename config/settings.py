"""
config/settings.py
All environment variables loaded from .env file.
"""
from dotenv import load_dotenv
load_dotenv()
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # AWS Bedrock
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    aws_default_region: str = "us-east-1"

    # Bedrock Model IDs
    bedrock_llm_model: str = "global.anthropic.claude-sonnet-4-6"
    bedrock_embed_model: str = "amazon.titan-embed-image-v1"

    # Pinecone
    pinecone_api_key: str = ""
    pinecone_index_name: str = "paper-comparison-engine"
    pinecone_environment: str = "us-east-1"

    # RAG
    chunk_size: int = 1024
    chunk_overlap: int = 200
    retrieval_top_k: int = 6
    max_papers: int = 8
    min_papers: int = 3

    # Properties for backward compatibility
    @property
    def aws_region(self) -> str:
        return self.aws_default_region

    @property
    def bedrock_llm_model_id(self) -> str:
        return self.bedrock_llm_model

    @property
    def bedrock_embedding_model_id(self) -> str:
        return self.bedrock_embed_model

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
