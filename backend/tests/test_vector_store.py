"""向量存储的维度探测与集合重建（切换 Embedding 模型时的迁移基础）。

回归背景：ChromaDB 的维度由首次写入决定，从 384 维哈希向量换到 1024 维真实模型时，
若不清空集合直接写入会报「Dimensionality ... does not match」。
"""

import pytest

from app.services.vector_store import KB_COLLECTION, QUESTION_COLLECTION, VectorStore


@pytest.fixture()
def store(tmp_path):
    return VectorStore(persist_dir=str(tmp_path / "chroma"))


def test_empty_store_has_no_dimension(store):
    assert store.stored_dims() == {KB_COLLECTION: None, QUESTION_COLLECTION: None}


def test_dimension_detected_after_upsert(store):
    store.upsert_chunk("chunk_1", 1, 0, "缓存穿透", [0.1, 0.2, 0.3])
    assert store.stored_dims()[KB_COLLECTION] == 3

    store.upsert_question("question_1", 1, 1, 1, "choice", "题干", [0.0] * 8)
    assert store.stored_dims()[QUESTION_COLLECTION] == 8


def test_reset_clears_collections_and_dimension(store):
    store.upsert_chunk("chunk_1", 1, 0, "缓存穿透", [0.1, 0.2])
    store.upsert_question("question_1", 1, 1, 1, "choice", "题干", [0.0] * 4)
    assert store.counts() == {KB_COLLECTION: 1, QUESTION_COLLECTION: 1}

    store.reset_collections()

    assert store.counts() == {KB_COLLECTION: 0, QUESTION_COLLECTION: 0}
    assert store.stored_dims() == {KB_COLLECTION: None, QUESTION_COLLECTION: None}
