"""检索评测单测：评测集自动生成、指标聚合、跳过逻辑。"""

from conftest import patch_retrieval

from app.services import retrieval, retrieval_eval


def _patch(monkeypatch, db, user_id):
    patch_retrieval(monkeypatch, db, user_id)


class TestBuildQuery:
    def test_uses_keywords_not_full_sentence(self):
        content = "B+ 树是 MySQL InnoDB 的默认索引结构，非叶子节点只存键，叶子节点存数据。"
        query = retrieval_eval.build_query_from_chunk(content)
        assert query
        assert len(query) <= 60
        assert query != content

    def test_short_content_still_gives_query(self):
        assert retrieval_eval.build_query_from_chunk("短文本内容测试") != ""


class TestAutoBuild:
    def test_creates_cases(self, db_session, seeded):
        user, chunk_ids = seeded
        created, skipped, total = retrieval_eval.auto_build_cases(db_session, user.id, count=4)
        assert created == 4
        assert total == 4
        assert skipped == 0

        from app.models import RetrievalEvalCase

        cases = (
            db_session.query(RetrievalEvalCase)
            .filter(RetrievalEvalCase.user_id == user.id)
            .all()
        )
        for case in cases:
            assert case.expected_ids, "每个用例必须有期望块"
            assert set(case.expected_ids).issubset(set(chunk_ids))
            assert case.source == "auto"

    def test_dedup_skips_used_chunks(self, db_session, seeded):
        """再次生成不应重复使用同一块；长度不足门槛的块会被跳过。"""
        user, _ = seeded
        created1, _, total1 = retrieval_eval.auto_build_cases(db_session, user.id, count=6)
        assert created1 >= 4, "语料里应有足够长的块可用"
        created2, _, total2 = retrieval_eval.auto_build_cases(db_session, user.id, count=6)
        assert created2 == 0, "块都用过了，不应再生成"
        assert total2 == total1

    def test_short_chunks_are_skipped(self, db_session):
        """过短的块不参与评测集生成（信息量不足，反推查询没区分度）。"""
        from app.models import KnowledgeChunk, KnowledgeEntry, User

        user = User(username="shorty", password_hash="x")
        db_session.add(user)
        db_session.flush()
        entry = KnowledgeEntry(user_id=user.id, title="短资料", content="很短", status="ready")
        db_session.add(entry)
        db_session.flush()
        chunk = KnowledgeChunk(
            entry_id=entry.id, seq=0, content="太短的一块内容", char_count=8
        )
        db_session.add(chunk)
        db_session.commit()

        created, skipped, total = retrieval_eval.auto_build_cases(db_session, user.id, count=3)
        assert (created, skipped, total) == (0, 0, 0)

    def test_empty_corpus(self, db_session):
        from app.models import User

        user = User(username="empty", password_hash="x")
        db_session.add(user)
        db_session.commit()
        assert retrieval_eval.auto_build_cases(db_session, user.id, count=5) == (0, 0, 0)


class TestRunEvaluation:
    def test_summary_has_three_baselines(self, db_session, seeded, monkeypatch):
        user, _ = seeded
        _patch(monkeypatch, db_session, user.id)
        retrieval_eval.auto_build_cases(db_session, user.id, count=6)

        from app.models import RetrievalEvalCase

        cases = db_session.query(RetrievalEvalCase).all()
        summary, detail, elapsed = retrieval_eval.run_evaluation(db_session, user.id, cases, top_k=5)

        assert set(summary) == {"vector", "bm25", "hybrid"}
        for metrics in summary.values():
            assert 0.0 <= metrics["recall"] <= 1.0
            assert 0.0 <= metrics["mrr"] <= 1.0
            assert 0.0 <= metrics["hit_at_1"] <= 1.0
        assert len(detail) == len(cases)
        assert detail[0]["modes"]["hybrid"]["ranked"] is not None
        assert elapsed >= 0
        retrieval.invalidate_index()

    def test_rewrite_adds_fourth_mode(self, db_session, seeded, monkeypatch):
        user, _ = seeded
        _patch(monkeypatch, db_session, user.id)
        retrieval_eval.auto_build_cases(db_session, user.id, count=3)

        from app.models import RetrievalEvalCase

        cases = db_session.query(RetrievalEvalCase).all()
        summary, _, _ = retrieval_eval.run_evaluation(
            db_session, user.id, cases, top_k=5, use_rewrite=True
        )
        assert "hybrid+rewrite" in summary
        assert len(summary) == 4
        retrieval.invalidate_index()

    def test_metrics_empty_when_expected_missing(self, db_session, seeded, monkeypatch):
        """期望块全是不存在的 id 时，各模式 recall 应为 0 而不是报错。"""
        user, _ = seeded
        _patch(monkeypatch, db_session, user.id)

        from app.models import RetrievalEvalCase

        case = RetrievalEvalCase(
            user_id=user.id, query="B+ 树 范围查询", expected_ids_json="[999999]", source="manual"
        )
        db_session.add(case)
        db_session.commit()

        summary, _, _ = retrieval_eval.run_evaluation(db_session, user.id, [case], top_k=5)
        assert all(metrics["recall"] == 0.0 for metrics in summary.values())
        retrieval.invalidate_index()
