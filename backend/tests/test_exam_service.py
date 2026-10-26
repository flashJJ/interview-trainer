"""难度自适应组卷的单测。

覆盖：
1. `allocate` 纯函数：比例整数化、合计严格等于 count、已知蓝图的可复现分布。
2. `adaptive_questions`：正常抽样、某档库存不足的回补（不静默少题）、库存整体不足抛错。
"""

import pytest

from app.models import Question, User
from app.services import exam_service


# ---------------------------------------------------------------- allocate 纯函数
class TestAllocate:
    def test_sum_invariant(self):
        for bp in exam_service.BLUEPRINTS:
            for count in range(1, 51):
                alloc = exam_service.allocate(count, bp)
                assert sum(alloc.values()) == count
                assert all(v >= 0 for v in alloc.values())

    def test_known_blueprints(self):
        assert exam_service.allocate(10, "intro") == {"easy": 6, "medium": 3, "hard": 1}
        assert exam_service.allocate(20, "consolidate") == {"easy": 4, "medium": 11, "hard": 5}
        assert exam_service.allocate(10, "sprint") == {"easy": 1, "medium": 3, "hard": 6}

    def test_balanced_close_to_even(self):
        alloc = exam_service.allocate(20, "balanced")
        # 比例约 1:1:1，取整后最大偏差不超过 1
        assert sum(alloc.values()) == 20
        assert max(alloc.values()) - min(alloc.values()) <= 1

    def test_unknown_blueprint_raises(self):
        with pytest.raises(KeyError):
            exam_service.allocate(10, "nope")


# ---------------------------------------------------------------- adaptive_questions（需用 DB）
def _make_user(db, name="exam-svc-tester"):
    user = User(username=name, password_hash="x")
    db.add(user)
    db.flush()
    return user


def _add_question(db, user_id, q_type, difficulty, content):
    db.add(
        Question(
            user_id=user_id,
            q_type=q_type,
            content=content,
            answer="A" if q_type == "choice" else "正确",
            options_json='["A. x", "B. y", "C. z", "D. w"]' if q_type == "choice" else "[]",
            explanation="解析",
            difficulty=difficulty,
            keywords_json="[]",
            source="rule",
            review_status="approved",
            status="active",
        )
    )


def _seed_difficulties(db, user_id, counts: dict[str, int], q_type="choice"):
    for difficulty, n in counts.items():
        for i in range(n):
            _add_question(db, user_id, q_type, difficulty, f"{difficulty}-{q_type}-{i}-{id(db)}")


class TestAdaptiveQuestions:
    def test_adaptive_sampling_respects_blueprint(self, db_session):
        user = _make_user(db_session)
        _seed_difficulties(db_session, user.id, {"easy": 10, "medium": 10, "hard": 10})
        db_session.commit()

        questions, actual = exam_service.adaptive_questions(
            db_session, user.id, 6, ["choice"], "sprint"
        )
        assert len(questions) == 6
        assert actual == {"easy": 0, "medium": 2, "hard": 4}
        assert sum(actual.values()) == 6

    def test_shortfall_redistributes_to_other_levels(self, db_session):
        """hard 只有 2 道却要冲刺蓝图（hard 占大头）→ 缺口回补到 easy/medium，不静默少题。"""
        user = _make_user(db_session)
        _seed_difficulties(db_session, user.id, {"easy": 10, "medium": 10, "hard": 2})
        db_session.commit()

        questions, actual = exam_service.adaptive_questions(
            db_session, user.id, 10, ["choice"], "sprint"
        )
        assert len(questions) == 10, "库存不足时应回补，而不是少题"
        assert actual["hard"] == 2, "hard 最多只能取到可用量"
        assert sum(actual.values()) == 10

    def test_pool_too_small_raises(self, db_session):
        user = _make_user(db_session)
        _seed_difficulties(db_session, user.id, {"easy": 1, "medium": 1, "hard": 1})
        db_session.commit()

        with pytest.raises(ValueError):
            exam_service.adaptive_questions(db_session, user.id, 10, ["choice"], "balanced")

    def test_respects_type_filter(self, db_session):
        user = _make_user(db_session)
        _seed_difficulties(db_session, user.id, {"easy": 5, "medium": 5, "hard": 5})
        db_session.commit()

        # 只有 choice 题，请求 judge → 基础池为空，应抛错而不是返回空卷
        with pytest.raises(ValueError):
            exam_service.adaptive_questions(db_session, user.id, 6, ["judge"], "balanced")
