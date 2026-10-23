"""知识库处理流水线：分块 → 关键词 → 向量化 → 入向量库。"""

import json

from ..config import get_settings
from ..models import KnowledgeChunk
from . import text_utils
from .chunker import chunk_text
from .runtime import get_embeddings, get_vector_store


def _clear_entry_data(db, entry) -> None:
    """清理条目的旧块与向量（重新处理前调用）。"""
    get_vector_store().delete_entry_vectors(entry.id)
    for chunk in list(entry.chunks):
        db.delete(chunk)
    db.commit()


def process_entry(db, entry) -> None:
    """处理单个知识条目。失败时置 status=failed 并记录错误信息。"""
    try:
        entry.status = "processing"
        entry.error = ""
        db.commit()

        _clear_entry_data(db, entry)

        settings = get_settings()
        embeddings = get_embeddings()
        store = get_vector_store()

        texts = chunk_text(entry.content, settings.chunk_target_size, settings.chunk_max_size)
        for seq, text in enumerate(texts):
            keywords = text_utils.top_terms([text], top_k=5)
            chunk = KnowledgeChunk(
                entry_id=entry.id,
                seq=seq,
                content=text,
                char_count=len(text),
                keywords_json=json.dumps(keywords, ensure_ascii=False),
            )
            db.add(chunk)
            db.flush()
            vector_id = f"chunk_{chunk.id}"
            store.upsert_chunk(
                vector_id=vector_id,
                entry_id=entry.id,
                seq=seq,
                content=text,
                embedding=embeddings.embed(text),
            )
            chunk.vector_id = vector_id

        entry.chunk_count = len(texts)
        entry.char_count = len(entry.content)
        entry.status = "ready"
        db.commit()
    except Exception as exc:  # noqa: BLE001 - 处理失败不阻塞录入，记录错误状态
        db.rollback()
        entry.status = "failed"
        entry.error = str(exc)[:500]
        db.commit()
