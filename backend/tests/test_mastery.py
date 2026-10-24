"""掌握度聚合与定向练习取材的单测。

覆盖：时间衰减、置信度收缩、三维聚合、薄弱判定双条件、定向组卷的优先级与不足报错。
"""

from datetime import datetime, timedelta

import pytest

from app.models import (
    ExamAnswer,
    ExamSession,
    KnowledgeEntry,
    Question,
    User,
    WrongQuestion,
)
from app.services import mastery


# ---------------------------------------------------------------- 造数工具
def make_user(db, name="tester"):
    user = User(username=name, password_hash="x")
    db.add(user)
    db.flush()
    return user


def make_entry(db, user_id, title):
    entry = KnowledgeEntry(
        user_id=user_id, title=title, content="示例内容" * 10, status="ready"
    )
    db.add(entry)
    db.flush()
    return entry


def make_question(db, user_id, q_type="choice", difficulty="medium", entry_id=None, review="approved"):
    question = Question(
        user_id=user_id,
        entry_id=entry_id,
        q_type=q_type,
        difficulty=difficulty,
        content=f"{q_type}-{difficulty} 的示例题干内容",
        answer="A",
        status="active",
        review_status=review,
    )
    db.add(question)
    db.flush()
    return question


def record(db, user_id, question, correct=True, score=None, days_ago=0):
    """记一次已提交作答（每次独立会话，便于控制时间）。"""
    session = ExamSession(
        user_id=user_id,
        paper_id=0,
        status="submitted",
        submitted_at=datetime.utcnow() - timedelta(days=days_ago),
        max_score=10.0,
        total_score=10.0 if correct else 0.0,
    )
    db.add(session)
    db.flush()
    answer = ExamAnswer(
        session_id=session.id,
        question_id=question.id,
        user_answer="A",
        score=10.0 if score is None else score,
        max_score=10.0,
        is_correct=correct,
        created_at=datetime.utcnow() - timedelta(days=days_ago),
    )
    db.add(answer)
    db.flush()
    return answer


def add_wrong(db, user_id, question, repetitions=0):
    row = WrongQuestion(
        user_id=user_id, question_id=question.id, repetitions=repetitions, error_count=1
    )
    db.add(row)
    db.flush()
    return row


# ---------------------------------------------------------------- 衰减与聚合
def test_decay_weight_halflife():
    now = datetime.utcnow()
    assert mastery.decay_weight(now, now) == pytest.approx(1.0, abs=1e-6)
    assert mastery.decay_weight(now - timedelta(days=14), now) == pytest.approx(0.5, abs=1e-3)
    assert mastery.decay_weight(now - timedelta(days=28), now) == pytest.approx(0.25, abs=1e-3)
    # 缺时间戳按「最近」处理
    assert mastery.decay_weight(None, now) == 1.0


def test_aggregate_without_data_is_neutral():
    result = mastery.aggregate([])
    assert result["mastery"] == 0.5
    assert result["confidence"] == 0.0
    assert result["answered"] == 0


def test_all_correct_raises_mastery(db_session):
    user = make_user(db_session)
    question = make_question(db_session, user.id, q_type="choice", difficulty="easy")
    for _ in range(6):
        record(db_session, user.id, question, correct=True)

    item = mastery.dimension_stats(db_session, user.id, "q_type")["items"]
    choice = next(i for i in item if i["key"] == "choice")
    assert choice["accuracy"] == 1.0
    assert choice["mastery"] > 0.9


def test_all_wrong_lowers_mastery(db_session):
    user = make_user(db_session)
    question = make_question(db_session, user.id, q_type="fill", difficulty="hard")
    for _ in range(6):
        record(db_session, user.id, question, correct=False, score=0.0)

    items = mastery.dimension_stats(db_session, user.id, "q_type")["items"]
    fill = next(i for i in items if i["key"] == "fill")
    assert fill["accuracy"] == 0.0
    assert fill["mastery"] < 0.1


def test_small_sample_shrinks_toward_neutral(db_session):
    """只答对 1 题：不能因为 100% 就判定掌握（样本不足向 0.5 收缩）。"""
    user = make_user(db_session)
    question = make_question(db_session, user.id)
    record(db_session, user.id, question, correct=True)

    items = mastery.dimension_stats(db_session, user.id, "q_type")["items"]
    choice = next(i for i in items if i["key"] == "choice")
    assert choice["accuracy"] == 1.0
    assert 0.5 < choice["mastery"] < 0.7
    assert choice["confidence"] < 0.3


def test_recent_performance_outweighs_old(db_session):
    """同样的对错次数，近期表现决定掌握度方向。"""
    improved = make_user(db_session, "improved")
    q1 = make_question(db_session, improved.id)
    record(db_session, improved.id, q1, correct=False, score=0.0, days_ago=100)
    record(db_session, improved.id, q1, correct=True, score=10.0, days_ago=0)

    regressed = make_user(db_session, "regressed")
    q2 = make_question(db_session, regressed.id)
    record(db_session, regressed.id, q2, correct=True, score=10.0, days_ago=100)
    record(db_session, regressed.id, q2, correct=False, score=0.0, days_ago=0)

    up = next(i for i in mastery.dimension_stats(db_session, improved.id, "q_type")["items"] if i["key"] == "choice")
    down = next(i for i in mastery.dimension_stats(db_session, regressed.id, "q_type")["items"] if i["key"] == "choice")
    assert up["mastery"] > 0.5 > down["mastery"]


def test_partial_score_uses_score_rate(db_session):
    """得分率参与计算：全对但只得一半分的掌握度应低于满分。"""
    user = make_user(db_session)
    question = make_question(db_session, user.id)
    for _ in range(6):
        record(db_session, user.id, question, correct=True, score=5.0)
    items = mastery.dimension_stats(db_session, user.id, "q_type")["items"]
    choice = next(i for i in items if i["key"] == "choice")
    assert choice["accuracy"] == 1.0
    assert choice["avg_score_rate"] == 0.5
    assert choice["mastery"] < 1.0


# ---------------------------------------------------------------- 维度聚合
def test_dimension_stats_by_type_covers_all_keys(db_session):
    user = make_user(db_session)
    items = mastery.dimension_stats(db_session, user.id, "q_type")["items"]
    assert {i["key"] for i in items} == {"choice", "fill", "judge"}
    assert all(i["label"] for i in items)


def test_dimension_stats_by_difficulty(db_session):
    user = make_user(db_session)
    easy = make_question(db_session, user.id, difficulty="easy")
    for _ in range(5):
        record(db_session, user.id, easy, correct=True)
    hard = make_question(db_session, user.id, difficulty="hard")
    for _ in range(5):
        record(db_session, user.id, hard, correct=False, score=0.0)

    items = {i["key"]: i for i in mastery.dimension_stats(db_session, user.id, "difficulty")["items"]}
    assert items["easy"]["mastery"] > 0.9
    assert items["hard"]["mastery"] < 0.1
    assert items["medium"]["mastery"] == 0.5  # 未观测


def test_entry_dimension_includes_untested_entries(db_session):
    user = make_user(db_session)
    entry_a = make_entry(db_session, user.id, "Python 并发")
    make_entry(db_session, user.id, "MySQL 索引")  # 从未考过
    question = make_question(db_session, user.id, entry_id=entry_a.id)
    for _ in range(5):
        record(db_session, user.id, question, correct=True)

    items = {i["label"]: i for i in mastery.dimension_stats(db_session, user.id, "entry")["items"]}
    assert set(items) == {"Python 并发", "MySQL 索引"}
    assert items["MySQL 索引"]["mastery"] == 0.5
    assert items["MySQL 索引"]["answered"] == 0
    assert items["Python 并发"]["mastery"] > 0.9


def test_question_count_only_counts_approved(db_session):
    user = make_user(db_session)
    make_question(db_session, user.id, q_type="choice", review="approved")
    make_question(db_session, user.id, q_type="choice", review="pending")
    make_question(db_session, user.id, q_type="choice", review="rejected")

    items = {i["key"]: i for i in mastery.dimension_stats(db_session, user.id, "q_type")["items"]}
    assert items["choice"]["question_count"] == 1


def test_wrong_pending_is_counted(db_session):
    user = make_user(db_session)
    question = make_question(db_session, user.id, q_type="judge")
    add_wrong(db_session, user.id, question, repetitions=0)  # 未掌握
    mastered = make_question(db_session, user.id, q_type="judge")
    add_wrong(db_session, user.id, mastered, repetitions=3)  # SM-2 已掌握

    items = {i["key"]: i for i in mastery.dimension_stats(db_session, user.id, "q_type")["items"]}
    assert items["judge"]["wrong_pending"] == 1


# ---------------------------------------------------------------- 雷达与薄弱项
def test_radar_has_six_axes(db_session):
    user = make_user(db_session)
    radar = mastery.radar(db_session, user.id)
    assert len(radar["indicators"]) == 6
    assert len(radar["values"]) == 6
    assert [g["dim"] for g in radar["groups"]] == ["q_type", "difficulty"]
    assert all(v == 50.0 for v in radar["values"])  # 无数据：全中性


def test_weak_points_requires_enough_sample(db_session):
    """只答错 1 题不算薄弱（累计权重不足）。"""
    user = make_user(db_session)
    question = make_question(db_session, user.id, q_type="fill")
    record(db_session, user.id, question, correct=False, score=0.0)
    assert mastery.weak_points(db_session, user.id)["items"] == []


def test_weak_points_detects_and_sorts(db_session):
    user = make_user(db_session)
    choice = make_question(db_session, user.id, q_type="choice")
    fill = make_question(db_session, user.id, q_type="fill")
    for _ in range(5):
        record(db_session, user.id, choice, correct=False, score=0.0)
        record(db_session, user.id, fill, correct=False, score=0.0)

    items = mastery.weak_points(db_session, user.id)["items"]
    # 两题都是中等难度，所以「难度-中等」也应当被识别为薄弱
    assert {(i["dim"], i["key"]) for i in items} == {
        ("q_type", "choice"),
        ("q_type", "fill"),
        ("difficulty", "medium"),
    }
    assert [i["mastery"] for i in items] == sorted(i["mastery"] for i in items)
    assert all(i["question_count"] > 0 for i in items)


def test_weak_points_skips_dimension_without_questions(db_session):
    """没有题可练的维度不做推荐（避免推荐了却组不出卷）。"""
    user = make_user(db_session)
    question = make_question(db_session, user.id, q_type="choice", review="pending")
    for _ in range(5):
        record(db_session, user.id, question, correct=False, score=0.0)
    assert mastery.weak_points(db_session, user.id)["items"] == []


def test_overview_summary(db_session):
    user = make_user(db_session)
    question = make_question(db_session, user.id, q_type="choice")
    for _ in range(5):
        record(db_session, user.id, question, correct=True)
    add_wrong(db_session, user.id, question)

    overview = mastery.overview(db_session, user.id)
    assert overview["total_answered"] == 5
    assert overview["overall_mastery"] > 0.9
    assert overview["wrong_pending_total"] == 1
    assert overview["tested_dimension_count"] >= 1


# ---------------------------------------------------------------- 定向组卷
def test_targeted_prioritizes_wrong_questions(db_session):
    user = make_user(db_session)
    wrong = make_question(db_session, user.id, q_type="choice")
    fresh = make_question(db_session, user.id, q_type="choice")
    done = make_question(db_session, user.id, q_type="choice")
    add_wrong(db_session, user.id, wrong)
    record(db_session, user.id, done, correct=True)

    picked = mastery.targeted_questions(db_session, user.id, "q_type", "choice", 3)
    assert len(picked) == 3
    assert picked[0].id == wrong.id  # 错题排在最前
    assert {q.id for q in picked} == {wrong.id, fresh.id, done.id}


def test_targeted_respects_wrong_ratio(db_session):
    """count=2 时错题最多占 1 道（上限 60%），另一道给未作答题。"""
    user = make_user(db_session)
    wrong_a = make_question(db_session, user.id, q_type="choice")
    wrong_b = make_question(db_session, user.id, q_type="choice")
    fresh = make_question(db_session, user.id, q_type="choice")
    add_wrong(db_session, user.id, wrong_a)
    add_wrong(db_session, user.id, wrong_b)

    picked = mastery.targeted_questions(db_session, user.id, "q_type", "choice", 2)
    assert len(picked) == 2
    assert sum(1 for q in picked if q.id in {wrong_a.id, wrong_b.id}) == 1
    assert fresh.id in {q.id for q in picked}


def test_targeted_filters_by_difficulty_and_type(db_session):
    user = make_user(db_session)
    hard = make_question(db_session, user.id, q_type="choice", difficulty="hard")
    make_question(db_session, user.id, q_type="choice", difficulty="easy")
    make_question(db_session, user.id, q_type="fill", difficulty="hard")

    picked = mastery.targeted_questions(db_session, user.id, "difficulty", "hard", 1, types=["choice"])
    assert [q.id for q in picked] == [hard.id]


def test_targeted_fills_up_when_all_in_wrong_book(db_session):
    """候选几乎全在错题本时，解除 60% 占比上限补齐（否则组不满卷）。"""
    user = make_user(db_session)
    questions = [make_question(db_session, user.id, q_type="fill") for _ in range(4)]
    for question in questions:
        add_wrong(db_session, user.id, question)
        record(db_session, user.id, question, correct=False, score=0.0)

    picked = mastery.targeted_questions(db_session, user.id, "q_type", "fill", 4)
    assert len(picked) == 4
    assert {q.id for q in picked} == {q.id for q in questions}


def test_targeted_raises_when_not_enough(db_session):
    user = make_user(db_session)
    make_question(db_session, user.id, q_type="choice")
    make_question(db_session, user.id, q_type="choice")
    with pytest.raises(ValueError, match="不足 5 道"):
        mastery.targeted_questions(db_session, user.id, "q_type", "choice", 5)


def test_targeted_rejects_invalid_dim(db_session):
    user = make_user(db_session)
    with pytest.raises(ValueError, match="维度不合法"):
        mastery.targeted_questions(db_session, user.id, "unknown", "x", 1)


def test_dimension_mastery_lookup(db_session):
    user = make_user(db_session)
    entry = make_entry(db_session, user.id, "Redis")
    question = make_question(db_session, user.id, entry_id=entry.id)
    for _ in range(5):
        record(db_session, user.id, question, correct=True)

    item = mastery.dimension_mastery(db_session, user.id, "entry", entry.id)
    assert item is not None
    assert item["label"] == "Redis"
    assert item["mastery"] > 0.9
    assert mastery.dimension_mastery(db_session, user.id, "entry", 9999) is None
