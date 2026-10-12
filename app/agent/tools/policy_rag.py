"""Answer policy questions (insurance, cancellation, damage, roadside
assistance, fuel, age requirements) using the RAG knowledge base.
"""

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from app.models.prompt_template import PromptTemplates
from app.service.rag.retrieval_service import get_retriever


class PolicyRagArgs(BaseModel):
    query: str = Field(description="The customer's policy question, verbatim or paraphrased")


@tool("policy_rag", args_schema=PolicyRagArgs)
def policy_rag(query: str) -> str:
    """Answer questions about insurance, cancellation policy, damage policy,
    roadside assistance, fuel policy, or age requirements, by retrieving the
    official policy text. Always use this tool for policy questions instead of
    answering from general knowledge — if it finds nothing relevant, say so
    rather than guessing."""
    results = get_retriever().retrieve(query)
    if not results:
        return PromptTemplates.POLICY_NOT_FOUND_MESSAGE

    chunks = [f"(source: {doc.metadata['source']})\n{doc.page_content}" for doc, _ in results]
    return "\n\n".join(chunks)
