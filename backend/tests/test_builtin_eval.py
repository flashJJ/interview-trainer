"""内置检索评测用例的单测。

覆盖：
1. **用例质量**：数量足够、每条都能对上某篇内置条目、查询刻意改述（防数据泄漏）。
2. **载入链路**：按 (user_id, query) 幂等、来源标记 builtin、expected_ids 全部属于映射条目。
"""

import json

import pytest

from app.models import KnowledgeChunk, KnowledgeEntry, RetrievalEvalCase, User
from app.services import builtin as builtin_service

from data.builtin import eval_cases as eval_data
from data.builtin import knowledge as knowledge_data

# 防泄漏窗口：查询不应包含条目正文里连续的 ≥15 字（改写后的自然提问不会这么长地照搬）
LEAK_WINDOW = 15


def test_case_count_is_usable():
    assert len(eval_data.BUILTIN_EVAL_CASES) >= 18


def test_every_case_maps_to_a_builtin_entry():
    titles = {e["title"] for e in knowledge_data.BUILTIN_ENTRIES}
    for case in eval_data.BUILTIN_EVAL_CASES:
        assert case["entry"] in titles, f"用例引用了不存在的条目：{case['entry']}"


def test_entries_are_not_duplicated_across_cases():
    # 允许同一篇被问多次，但 (entry, query) 不应重复
    seen = {(c["entry"], c["query"]) for c in eval_data.BUILTIN_EVAL_CASES}
    assert len(seen) == len(eval_data.BUILTIN_EVAL_CASES)


def test_queries_avoid_leakage():
    """每条查询都不应包含其映射条目正文里连续的 15 字（避免词面泄漏）。"""
    content_by_title = {e["title"]: e["content"] for e in knowledge_data.BUILTIN_ENTRIES}
    for case in eval_data.BUILTIN_EVAL_CASES:
        content = content_by_title[case["entry"]]
        query = case["query"]
        for i in range(len(content) - LEAK_WINDOW + 1):
            window = content[i : i + LEAK_WINDOW]
            assert window not in query, (
                f"用例「{query}」与条目「{case['entry']}」存在 15 字连续重合：{window}"
            )


# ---------------------------------------------------------------- 载入链路
def _make_user(db, name="builtin-eval-tester"):
    user = User(username=name, password_hash="x")
    db.add(user)
    db.flush()
    return user


def _seed_entries_with_chunks(db, user_id):
    """插入 19 篇内置条目 + 每篇 2 个知识块（最小结构，足以驱动 eval 用例解析）。"""
    for entry in knowledge_data.BUILTIN_ENTRIES:
        e = KnowledgeEntry(
            user_id=user_id,
            title=entry["title"],
            source_type="builtin",
            content=entry["content"],
            status="ready",
            chunk_count=2,
        )
        db.add(e)
        db.flush()
        for seq in range(2):
            db.add(
                KnowledgeChunk(
                    entry_id=e.id,
                    seq=seq,
                    content=entry["content"][seq * 50 : seq * 50 + 80],
                    char_count=80,
                )
            )
    db.commit()


class TestLoadBuiltinEvalCases:
    def test_loads_and_tags_builtin(self, db_session):
        user = _make_user(db_session)
        _seed_entries_with_chunks(db_session, user.id)

        stat = builtin_service.load_builtin_eval_cases(db_session, user.id, log=lambda _m: None)
        assert stat["created"] == len(eval_data.BUILTIN_EVAL_CASES)
        assert stat["orphan"] == 0

        cases = (
            db_session.query(RetrievalEvalCase)
            .filter(RetrievalEvalCase.user_id == user.id)
            .all()
        )
        assert {c.source for c in cases} == {"builtin"}
        # 每条用例的 expected_ids 必须全部属于其映射条目
        entry_id_by_title = {
            e.title: e.id
            for e in db_session.query(KnowledgeEntry)
            .filter(KnowledgeEntry.user_id == user.id)
            .all()
        }
        for case in cases:
            title = next(c["entry"] for c in eval_data.BUILTIN_EVAL_CASES if c["query"] == case.query)
            expected_entry_ids = {
                ch.entry_id
                for ch in db_session.query(KnowledgeChunk)
                .filter(KnowledgeChunk.id.in_(json.loads(case.expected_ids_json)))
                .all()
            }
            assert expected_entry_ids == {entry_id_by_title[title]}

    def test_idempotent(self, db_session):
        user = _make_user(db_session)
        _seed_entries_with_chunks(db_session, user.id)

        first = builtin_service.load_builtin_eval_cases(db_session, user.id, log=lambda _m: None)
        second = builtin_service.load_builtin_eval_cases(db_session, user.id, log=lambda _m: None)
        assert first["created"] == len(eval_data.BUILTIN_EVAL_CASES)
        assert second["created"] == 0
        assert second["skipped"] == len(eval_data.BUILTIN_EVAL_CASES)
        assert (
            db_session.query(RetrievalEvalCase)
            .filter(RetrievalEvalCase.user_id == user.id)
            .count()
            == len(eval_data.BUILTIN_EVAL_CASES)
        )

    def test_orphan_when_entry_missing(self, db_session):
        """条目不存在时该用例跳过（orphan 计数），不报错。"""
        user = _make_user(db_session)
        # 只建一篇条目，其余用例对不上
        e = KnowledgeEntry(
            user_id=user.id,
            title=knowledge_data.BUILTIN_ENTRIES[0]["title"],
            source_type="builtin",
            content=knowledge_data.BUILTIN_ENTRIES[0]["content"],
            status="ready",
            chunk_count=2,
        )
        db_session.add(e)
        db_session.flush()
        for seq in range(2):
            db_session.add(
                KnowledgeChunk(
                    entry_id=e.id, seq=seq,
                    content=knowledge_data.BUILTIN_ENTRIES[0]["content"][:80], char_count=80,
                )
            )
        db_session.commit()

        stat = builtin_service.load_builtin_eval_cases(db_session, user.id, log=lambda _m: None)
        assert stat["created"] == 1  # 只有第一条对得上
        assert stat["orphan"] == len(eval_data.BUILTIN_EVAL_CASES) - 1
