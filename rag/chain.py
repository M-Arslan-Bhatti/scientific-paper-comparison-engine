"""
rag/chain.py

LangChain RAG chain for per-paper question answering.
Uses LCEL (LangChain Expression Language) pipe syntax.

Chain structure per paper:
  retriever | format_docs | prompt | llm | output_parser

This chain is used internally by comparison.py to get
context from each paper before the cross-paper synthesis step.
"""
from typing import List
from loguru import logger
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough


RETRIEVAL_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are a scientific research analyst.
You are given excerpts from a research paper and a question.
Answer the question using ONLY the provided excerpts.
If the paper does not address the question, say 'Not addressed in this paper.'
Always be concise and factual."""),
    ("human", """Paper excerpts:
{context}

Question: {question}

Answer based only on the excerpts above:""")
])


def format_docs(docs) -> str:
    """Format retrieved documents into a single context string."""
    return "\n\n---\n\n".join(
        f"[Section: {doc.metadata.get('section', 'Unknown')} | "
        f"Page: {doc.metadata.get('page_number', '?')}]\n{doc.page_content}"
        for doc in docs
    )


def build_paper_chain(retriever, llm):
    """
    Build a LangChain LCEL chain for one paper.
    Returns a runnable that takes {"question": "..."} and returns a string.
    """
    chain = (
        {"context": retriever | format_docs, "question": RunnablePassthrough()}
        | RETRIEVAL_PROMPT
        | llm
        | StrOutputParser()
    )
    return chain


def query_single_paper(retriever, llm, question: str) -> str:
    """
    Run the RAG chain for one paper and return the answer string.
    """
    try:
        chain = build_paper_chain(retriever, llm)
        result = chain.invoke(question)
        return result
    except Exception as e:
        logger.error(f"Chain error: {e}")
        return f"Error retrieving from paper: {str(e)}"
