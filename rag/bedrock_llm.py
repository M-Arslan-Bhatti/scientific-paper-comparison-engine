"""
rag/bedrock_llm.py

AWS Bedrock Claude via direct boto3 call.
ChatBedrock does not support global.* model prefixes,
so we use a custom LangChain BaseChatModel wrapper.
"""
import json
import boto3
from typing import List, Optional, Any
from loguru import logger
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from langchain_core.outputs import ChatResult, ChatGeneration
from config import get_settings

settings = get_settings()


def _get_boto_client():
    from botocore.config import Config
    config = Config(
        read_timeout=600,        # 10 minutes - enough for 5 paper synthesis
        connect_timeout=30,
        retries={"max_attempts": 2}
    )
    return boto3.client(
        service_name="bedrock-runtime",
        region_name=settings.aws_default_region,
        aws_access_key_id=settings.aws_access_key_id,
        aws_secret_access_key=settings.aws_secret_access_key,
        config=config,
    )


class BedrockClaude(BaseChatModel):
    """
    Custom LangChain-compatible chat model using direct boto3.
    Works with global.* model prefixes that ChatBedrock does not support.
    """

    model_id: str = ""
    temperature: float = 0.1
    max_tokens: int = 8192

    def _generate(self, messages: List[BaseMessage], stop=None, **kwargs) -> ChatResult:
        client = _get_boto_client()

        system_prompt = ""
        chat_messages = []

        for msg in messages:
            if isinstance(msg, SystemMessage):
                system_prompt = msg.content
            elif isinstance(msg, HumanMessage):
                chat_messages.append({"role": "user", "content": msg.content})
            elif isinstance(msg, AIMessage):
                chat_messages.append({"role": "assistant", "content": msg.content})

        if not chat_messages:
            chat_messages.append({"role": "user", "content": ""})

        body_dict = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "messages": chat_messages,
        }
        if system_prompt:
            body_dict["system"] = system_prompt

        response = client.invoke_model(
            modelId=self.model_id,
            body=json.dumps(body_dict),
            contentType="application/json",
            accept="application/json",
        )

        result  = json.loads(response["body"].read())
        text    = result["content"][0]["text"]
        message = AIMessage(content=text)
        return ChatResult(generations=[ChatGeneration(message=message)])

    @property
    def _llm_type(self) -> str:
        return "bedrock-claude-direct"


def get_bedrock_llm() -> BedrockClaude:
    """
    Returns a LangChain-compatible Claude model via direct boto3.
    Compatible with global.* model prefixes.
    """
    model_id = settings.bedrock_llm_model
    llm = BedrockClaude(
        model_id=model_id,
        temperature=0.1,
        max_tokens=8192,
    )
    logger.info(f"BedrockClaude ready. Model: {model_id}")
    return llm


def test_bedrock_connection() -> bool:
    """Quick connectivity check."""
    try:
        client   = _get_boto_client()
        model_id = settings.bedrock_llm_model

        body = json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 20,
            "temperature": 0.1,
            "messages": [{"role": "user", "content": "Say OK"}],
        })

        response = client.invoke_model(
            modelId=model_id,
            body=body,
            contentType="application/json",
            accept="application/json",
        )
        result = json.loads(response["body"].read())
        reply  = result["content"][0]["text"]
        logger.info(f"Bedrock test passed. Reply: {reply}")
        return True

    except Exception as e:
        logger.error(f"Bedrock test failed: {e}")
        return False