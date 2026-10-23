"""向量数据库封装（ChromaDB 嵌入式持久化）。

两个集合：
- kb_chunks   知识块向量（语义检索）
- questions   题目向量（出题去重）
"""

import os

import chromadb
from chromadb.config import Settings as ChromaSettings

from ..config import get_settings

KB_COLLECTION = "kb_chunks"
QUESTION_COLLECTION = "questions"


class VectorStore:
    def __init__(self, persist_dir: str | None = None):
        settings = get_settings()
        path = persist_dir or settings.chroma_dir
        os.makedirs(path, exist_ok=True)
        self._client = chromadb.PersistentClient(
            path=path,
            settings=ChromaSettings(anonymized_telemetry=False, allow_reset=True),
        )
        self._kb = self._client.get_or_create_collection(KB_COLLECTION, embedding_function=None)
        self._questions = self._client.get_or_create_collection(
            QUESTION_COLLECTION, embedding_function=None
        )

    # ---------- 知识块 ----------
    def upsert_chunk(self, vector_id: str, entry_id: int, seq: int, content: str, embedding: list[float]) -> None:
        self._kb.upsert(
            ids=[vector_id],
            embeddings=[embedding],
            documents=[content],
            metadatas=[{"entry_id": int(entry_id), "seq": int(seq)}],
        )

    def delete_entry_vectors(self, entry_id: int) -> None:
        self._kb.delete(where={"entry_id": int(entry_id)})

    def search_chunks(self, embedding: list[float], top_k: int = 5, entry_ids: list[int] | None = None) -> list[dict]:
        where = {"entry_id": {"$in": [int(i) for i in entry_ids]}} if entry_ids else None
        res = self._kb.query(query_embeddings=[embedding], n_results=top_k, where=where)
        hits: list[dict] = []
        ids = (res.get("ids") or [[]])[0]
        docs = (res.get("documents") or [[]])[0]
        metas = (res.get("metadatas") or [[]])[0]
        dists = (res.get("distances") or [[]])[0]
        for vid, doc, meta, dist in zip(ids, docs, metas, dists):
            hits.append(
                {
                    "vector_id": vid,
                    "content": doc or "",
                    "entry_id": (meta or {}).get("entry_id"),
                    "seq": (meta or {}).get("seq", 0),
                    "score": round(max(0.0, 1.0 - float(dist)), 4),
                }
            )
        return hits

    # ---------- 题目 ----------
    def upsert_question(
        self,
        vector_id: str,
        question_id: int,
        user_id: int,
        entry_id: int | None,
        q_type: str,
        content: str,
        embedding: list[float],
    ) -> None:
        self._questions.upsert(
            ids=[vector_id],
            embeddings=[embedding],
            documents=[content],
            metadatas=[
                {
                    "question_id": int(question_id),
                    "user_id": int(user_id),
                    "entry_id": int(entry_id or 0),
                    "q_type": q_type,
                }
            ],
        )

    def delete_question_vector(self, question_id: int) -> None:
        self._questions.delete(ids=[f"question_{int(question_id)}"])

    def delete_entry_question_vectors(self, entry_id: int) -> None:
        self._questions.delete(where={"entry_id": int(entry_id)})

    def max_question_similarity(self, embedding: list[float], user_id: int) -> float:
        """与当前用户已有题目的最高相似度（用于去重）。"""
        res = self._questions.query(
            query_embeddings=[embedding], n_results=1, where={"user_id": int(user_id)}
        )
        dists = res.get("distances") or [[]]
        if not dists or not dists[0]:
            return 0.0
        return max(0.0, 1.0 - float(dists[0][0]))

    # ---------- 统计 ----------
    def counts(self) -> dict:
        return {KB_COLLECTION: self._kb.count(), QUESTION_COLLECTION: self._questions.count()}
