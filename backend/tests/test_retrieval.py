"""混合检索单测：RRF 融合、指标计算、端到端召回、索引缓存。

用假的 Embedding / 向量库（本地 n-gram 向量 + 暴力余弦，见 conftest.py），
这样单测不依赖磁盘与网络，且行为可复现。
"""

import pytest
from conftest import FakeEmbeddings, patch_retrieval

from app.services import retrieval


def _patch_store(monkeypatch, db, user_id):
    """装配假后端（兼容旧调用点）。"""
    patch_retrieval(monkeypatch, db, user_id)


# ---------------------------------------------------------------- RRF 融合
class TestRRF:
    def test_item_in_both_lists_wins(self):
        vector = [(1, 0.9), (2, 0.8), (3, 0.7)]
        bm25 = [(3, 12.0), (4, 8.0)]
        fused = retrieval.rrf_fuse([vector, bm25])
        # 3 号在两路都出现，名次分别是 3 和 1，总分应超过只在单路第一的 1 号
        assert fused[0][0] == 3

    def test_score_formula(self):
        fused = retrieval.rrf_fuse([[(7, 1.0)]], k=60)
        assert fused == [(7, pytest.approx(1 / 61))]

    def test_weights_scale_channel(self):
        fused = retrieval.rrf_fuse([[(1, 1.0)], [(2, 1.0)]], weights=[2.0, 1.0])
        assert fused[0][0] == 1

    def test_empty_input(self):
        assert retrieval.rrf_fuse([]) == []
        assert retrieval.rrf_fuse([[], []]) == []


# ---------------------------------------------------------------- 指标
class TestMetrics:
    def test_recall_at_k(self):
        assert retrieval.recall_at_k([1, 2, 3], [2], k=5) == 1.0
        assert retrieval.recall_at_k([1, 2, 3], [9], k=5) == 0.0
        assert retrieval.recall_at_k([1, 2], [1, 2], k=5) == 1.0
        assert retrieval.recall_at_k([1], [1, 2], k=5) == 0.5

    def test_recall_respects_k(self):
        assert retrieval.recall_at_k([1, 2, 3, 4, 5, 6], [6], k=5) == 0.0
        assert retrieval.recall_at_k([1, 2, 3, 4, 5, 6], [6], k=6) == 1.0

    def test_recall_empty_expected_is_zero(self):
        assert retrieval.recall_at_k([1, 2], [], k=5) == 0.0

    def test_reciprocal_rank(self):
        assert retrieval.reciprocal_rank([5, 6, 7], [5]) == 1.0
        assert retrieval.reciprocal_rank([5, 6, 7], [6]) == 0.5
        assert retrieval.reciprocal_rank([5, 6, 7], [8]) == 0.0
        assert retrieval.reciprocal_rank([], [1]) == 0.0

    def test_hit_at_1(self):
        assert retrieval.hit_at_1([3, 1], [3]) == 1.0
        assert retrieval.hit_at_1([1, 3], [3]) == 0.0
        assert retrieval.hit_at_1([], [1]) == 0.0


# ---------------------------------------------------------------- 查询改写
class TestRewrite:
    def test_rule_rewrite_adds_keyword_variant(self):
        variants = retrieval.rewrite_query("什么是 GIL 全局解释器锁")
        assert variants[0] == "什么是 GIL 全局解释器锁"
        assert len(variants) >= 2
        assert " " in variants[1]  # 关键词串

    def test_blank_query(self):
        assert retrieval.rewrite_query("   ") == []


# ---------------------------------------------------------------- 端到端召回
class TestRetrieve:
    def test_hybrid_hits_expected_chunk(self, db_session, seeded, monkeypatch):
        user, chunk_ids = seeded
        retrieval.invalidate_index()
        monkeypatch.setattr(retrieval, "get_embeddings", lambda: FakeEmbeddings())
        _patch_store(monkeypatch, db_session, user.id)

        hits = retrieval.retrieve(db_session, user.id, "B+ 树 为什么 范围查询 快", top_k=3)
        assert hits, "混合检索应召回结果"
        # 期望命中 MySQL 索引篇的第一块（B+ 树那段）
        assert hits[0].chunk_id == chunk_ids[3]
        assert hits[0].channels, "至少来自一个通道"

    def test_modes_all_work(self, db_session, seeded, monkeypatch):
        user, _ = seeded
        retrieval.invalidate_index()
        monkeypatch.setattr(retrieval, "get_embeddings", lambda: FakeEmbeddings())
        _patch_store(monkeypatch, db_session, user.id)

        for mode in retrieval.MODES:
            hits = retrieval.retrieve(db_session, user.id, "GIL 多进程 并发", top_k=3, mode=mode)
            assert isinstance(hits, list)
            if mode == retrieval.MODE_BM25:
                assert all(h.bm25_rank for h in hits)
            if mode == retrieval.MODE_VECTOR:
                assert all(h.vector_rank for h in hits)

    def test_invalid_mode_falls_back_to_hybrid(self, db_session, seeded, monkeypatch):
        user, _ = seeded
        retrieval.invalidate_index()
        monkeypatch.setattr(retrieval, "get_embeddings", lambda: FakeEmbeddings())
        _patch_store(monkeypatch, db_session, user.id)
        hits = retrieval.retrieve(db_session, user.id, "协程 事件循环", top_k=2, mode="unknown")
        assert hits

    def test_blank_query_returns_empty(self, db_session, seeded):
        user, _ = seeded
        assert retrieval.retrieve(db_session, user.id, "   ") == []

    def test_no_corpus_returns_empty(self, db_session):
        from app.models import User

        user = User(username="u2", password_hash="x")
        db_session.add(user)
        db_session.commit()
        assert retrieval.retrieve(db_session, user.id, "任意查询") == []

    def test_rewrite_mode_still_returns_hits(self, db_session, seeded, monkeypatch):
        user, _ = seeded
        retrieval.invalidate_index()
        monkeypatch.setattr(retrieval, "get_embeddings", lambda: FakeEmbeddings())
        _patch_store(monkeypatch, db_session, user.id)
        hits = retrieval.retrieve(
            db_session, user.id, "什么是 GIL", top_k=3, use_rewrite=True, embedding_cache={}
        )
        assert hits


# ---------------------------------------------------------------- 索引缓存
class TestIndexCache:
    def test_cache_reused_and_invalidated(self, db_session, seeded):
        user, chunk_ids = seeded
        retrieval.invalidate_index()
        index1 = retrieval.get_bm25_index(db_session, user.id)
        index2 = retrieval.get_bm25_index(db_session, user.id)
        assert index1 is index2, "语料未变时应命中缓存"
        assert len(index1) == 6

        # 新增一块 -> 版本变化 -> 重建
        from app.models import KnowledgeChunk

        chunk = KnowledgeChunk(
            entry_id=1, seq=99, content="新增的一块知识内容用于触发索引重建", char_count=20
        )
        db_session.add(chunk)
        db_session.commit()

        index3 = retrieval.get_bm25_index(db_session, user.id)
        assert index3 is not index1
        assert len(index3) == 7
        retrieval.invalidate_index()

    def test_other_user_not_in_corpus(self, db_session, seeded):
        user, _ = seeded
        corpus = retrieval.load_corpus(db_session, user.id)
        assert len(corpus) == 6
        assert retrieval.load_corpus(db_session, user.id + 999) == []
