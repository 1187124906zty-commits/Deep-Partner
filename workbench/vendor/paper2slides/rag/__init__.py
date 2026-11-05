from .config import RAGConfig

from .query import (
    RAGQueryResult,
    RAG_PAPER_QUERIES,
    RAG_QUERY_MODES,
    SKIP_LLM_SECTIONS,
    GENERAL_OVERVIEW_QUERIES,
    get_queries,
    generate_general_queries,
)


def __getattr__(name):
    # Parsing an already extracted document does not require LightRAG.
    if name == "RAGClient":
        from .client import RAGClient
        return RAGClient
    raise AttributeError(name)

__all__ = [
    "RAGConfig",
    "RAGClient",
    "RAGQueryResult",
    "RAG_PAPER_QUERIES",
    "RAG_QUERY_MODES",
    "SKIP_LLM_SECTIONS",
    "GENERAL_OVERVIEW_QUERIES",
    "get_queries",
    "generate_general_queries",
]
