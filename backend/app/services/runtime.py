"""服务层单例：整个进程共享同一份 Embedding 服务与 ChromaDB 客户端。"""

from .embeddings import EmbeddingService
from .llm_client import LLMClient
from .vector_store import VectorStore

_embedding_service: EmbeddingService | None = None
_vector_store: VectorStore | None = None
_llm_client: LLMClient | None = None


def get_embeddings() -> EmbeddingService:
    global _embedding_service
    if _embedding_service is None:
        _embedding_service = EmbeddingService()
    return _embedding_service


def get_vector_store() -> VectorStore:
    global _vector_store
    if _vector_store is None:
        _vector_store = VectorStore()
    return _vector_store


def get_llm() -> LLMClient:
    global _llm_client
    if _llm_client is None:
        _llm_client = LLMClient()
    return _llm_client
