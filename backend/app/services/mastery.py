"""知识点掌握度聚合与定向练习取材。

核心思想：把每次已提交作答视为一次「观测」，按维度聚合出掌握度。

三个关键设计（详见 docs/06-v1.6-掌握度与定向训练.md）：
1. **时间衰减**：近期作答权重更高，半衰期 14 天（≈ 两轮 SM-2 复习间隔）。
2. **置信度收缩**：样本不足时把掌握度向 0.5（中性）收缩，避免把「没练过」
   误读成「完全不会」；同时把 confidence 暴露给前端，让"样本不足"可见。
3. **薄弱判定双条件**：既要 mastery 低于阈值，也要累计权重够（约 2 次近期作答），
   否则「只做过 1 题且答错」会被误判为薄弱。
"""

from __future__ import annotations

import random
from datetime import datetime

from sqlalchemy import func

from ..models import ExamAnswer, ExamSession, KnowledgeEntry, Question, WrongQuestion

# ---------------------------------------------------------------- 可调参数
HALF_LIFE_DAYS = 14.0          # 时间衰减半衰期（天）
FULL_CONFIDENCE_WEIGHT = 5.0   # 累计权重达到该值即视为满置信（≈5 次近期作答）
NEUTRAL = 0.5                  # 无观测时的中性掌握度
ACC_WEIGHT = 0.7               # 二值正确率在 raw 中的占比（其余给得分率）
DEFAULT_THRESHOLD = 0.6        # 薄弱阈值
MIN_WEIGHT_FOR_WEAK = 1.5      # 参与薄弱判定的最低累计权重
WRONG_RATIO = 0.6              # 定向练习中错题本题目占比上限
MASTERY_REPETITIONS = 3        # SM-2 连续答对次数达到该值视为已掌握

Q_TYPE_TEXT = {"choice": "单选", "fill": "填空", "judge": "判断"}
DIFFICULTY_TEXT = {"easy": "简单", "medium": "中等", "hard": "困难"}

DIMS = ("q_type", "difficulty", "entry")
DIM_TEXT = {"q_type": "题型", "difficulty": "难度", "entry": "资料"}
DIM_FIELD = {"q_type": Question.q_type, "difficulty": Question.difficulty, "entry": Question.entry_id}

_FIXED_KEYS = {
    "q_type": ["choice", "fill", "judge"],
    "difficulty": ["easy", "medium", "hard"],
}


# ---------------------------------------------------------------- 观测
def decay_weight(created_at: datetime | None, now: datetime | None = None) -> float:
    """按半衰期折算观测权重；缺时间戳按「最近」处理（权重 1.0）。"""
    if created_at is None:
        return 1.0
    now = now or datetime.utcnow()
    days = max((now - created_at).total_seconds() / 86400.0, 0.0)
    return 0.5 ** (days / HALF_LIFE_DAYS)


def load_observations(db, user_id: int, now: datetime | None = None) -> list[dict]:
    """拉取该用户所有已提交作答，折算成带权观测。"""
    rows = (
        db.query(
            ExamAnswer.question_id,
            ExamAnswer.is_correct,
            ExamAnswer.score,
            ExamAnswer.max_score,
            ExamAnswer.created_at,
            Question.q_type,
            Question.difficulty,
            Question.entry_id,
        )
        .join(ExamSession, ExamSession.id == ExamAnswer.session_id)
        .join(Question, Question.id == ExamAnswer.question_id)
        .filter(ExamSession.user_id == user_id, ExamSession.status == "submitted")
        .all()
    )
    out: list[dict] = []
    for qid, correct, score, max_score, created_at, q_type, difficulty, entry_id in rows:
        denominator = float(max_score or 0.0) or 10.0
        rate = float(score or 0.0) / denominator
        out.append(
            {
                "question_id": qid,
                "correct": 1.0 if correct else 0.0,
                "rate": min(max(rate, 0.0), 1.0),
                "weight": decay_weight(created_at, now),
                "q_type": q_type,
                "difficulty": difficulty,
                "entry_id": entry_id,
            }
        )
    return out


def aggregate(observations: list[dict]) -> dict:
    """把一组观测折算成掌握度指标。"""
    if not observations:
        return {
            "answered": 0,
            "correct": 0,
            "accuracy": 0.0,
            "avg_score_rate": 0.0,
            "weight": 0.0,
            "confidence": 0.0,
            "mastery": NEUTRAL,
        }
    total_w = sum(o["weight"] for o in observations) or 1e-9
    accuracy = sum(o["weight"] * o["correct"] for o in observations) / total_w
    score_rate = sum(o["weight"] * o["rate"] for o in observations) / total_w
    raw = ACC_WEIGHT * accuracy + (1 - ACC_WEIGHT) * score_rate
    confidence = min(1.0, total_w / FULL_CONFIDENCE_WEIGHT)
    return {
        "answered": len(observations),
        "correct": int(sum(o["correct"] for o in observations)),
        "accuracy": round(accuracy, 3),
        "avg_score_rate": round(score_rate, 3),
        "weight": round(total_w, 3),
        "confidence": round(confidence, 3),
        "mastery": round(NEUTRAL + (raw - NEUTRAL) * confidence, 3),
    }


# ---------------------------------------------------------------- 维度聚合
def _dim_key(observation: dict, dim: str):
    return observation["entry_id"] if dim == "entry" else observation[dim]


def normalize_key(dim: str, key):
    """维度键归一化：资料维度统一成 int（未关联资料的题目归到 0）。"""
    if dim == "entry":
        try:
            return int(key)
        except (TypeError, ValueError):
            return 0
    return key if key is not None else ""


def _entry_titles(db, user_id: int) -> dict[int, str]:
    rows = (
        db.query(KnowledgeEntry.id, KnowledgeEntry.title)
        .filter(KnowledgeEntry.user_id == user_id)
        .all()
    )
    return {int(eid): title for eid, title in rows}


def _label(dim: str, key, entry_titles: dict[int, str]) -> str:
    if dim == "q_type":
        return Q_TYPE_TEXT.get(key, str(key))
    if dim == "difficulty":
        return DIFFICULTY_TEXT.get(key, str(key))
    if not key:
        return "未关联资料"
    return entry_titles.get(int(key), f"资料#{key}")  # type: ignore[arg-type]


def _question_counts(db, user_id: int, dim: str) -> dict:
    """该维度下「已进入组卷池」的题目数（approved + active）。"""
    field = DIM_FIELD[dim]
    rows = (
        db.query(field, func.count(Question.id))
        .filter(
            Question.user_id == user_id,
            Question.status == "active",
            Question.review_status == "approved",
        )
        .group_by(field)
        .all()
    )
    return {key: int(count) for key, count in rows}


def _wrong_pending(db, user_id: int, dim: str) -> dict:
    """该维度下仍在错题本中的题目数（SM-2 未掌握）。"""
    field = DIM_FIELD[dim]
    rows = (
        db.query(field, func.count(WrongQuestion.id))
        .join(Question, Question.id == WrongQuestion.question_id)
        .filter(WrongQuestion.user_id == user_id, WrongQuestion.repetitions < MASTERY_REPETITIONS)
        .group_by(field)
        .all()
    )
    return {key: int(count) for key, count in rows}


def dimension_stats(
    db, user_id: int, dim: str = "q_type", now: datetime | None = None
) -> dict:
    """单维度聚合。返回 {dim, items:[{key,label,answered,correct,accuracy,mastery,...}]}。"""
    if dim not in DIMS:
        dim = "q_type"
    observations = load_observations(db, user_id, now)
    buckets: dict = {}
    for obs in observations:
        buckets.setdefault(normalize_key(dim, _dim_key(obs, dim)), []).append(obs)

    entry_titles = _entry_titles(db, user_id) if dim == "entry" else {}
    # 维度候选键：题型/难度固定三种；资料维度取全部条目（未测的也要可见）
    keys = list(_FIXED_KEYS.get(dim, [])) or sorted(
        {normalize_key(dim, k) for k in set(buckets) | set(entry_titles)}
    )
    for key in buckets:
        if key not in keys:
            keys.append(key)

    counts = {normalize_key(dim, k): v for k, v in _question_counts(db, user_id, dim).items()}
    wrongs = {normalize_key(dim, k): v for k, v in _wrong_pending(db, user_id, dim).items()}

    items = []
    for key in keys:
        metrics = aggregate(buckets.get(key, []))
        items.append(
            {
                **metrics,
                "key": str(key),
                "label": _label(dim, key, entry_titles),
                "question_count": int(counts.get(key, 0)),
                "wrong_pending": int(wrongs.get(key, 0)),
            }
        )
    # 掌握度升序：薄弱维度排在最前，方便直接看「要先补什么」
    items.sort(key=lambda x: (x["mastery"], -x["weight"]))
    return {"dim": dim, "dim_label": DIM_TEXT[dim], "items": items}


def radar(db, user_id: int, now: datetime | None = None) -> dict:
    """雷达数据：题型 3 轴 + 难度 3 轴。"""
    axes: list[dict] = []
    values: list[float] = []
    groups: list[dict] = []
    for dim in ("q_type", "difficulty"):
        stats = dimension_stats(db, user_id, dim, now)
        by_key = {item["key"]: item for item in stats["items"]}
        for key in _FIXED_KEYS[dim]:
            item = by_key.get(key, {})
            axes.append({"name": _label(dim, key, {}), "max": 100})
            values.append(round(float(item.get("mastery", NEUTRAL)) * 100, 1))
        groups.append({"dim": dim, "label": DIM_TEXT[dim], "count": len(_FIXED_KEYS[dim])})
    return {"indicators": axes, "values": values, "groups": groups}


def weak_points(
    db,
    user_id: int,
    threshold: float = DEFAULT_THRESHOLD,
    limit: int = 5,
    now: datetime | None = None,
) -> dict:
    """薄弱维度：掌握度低于阈值、样本够、且有题可练。"""
    items: list[dict] = []
    for dim in DIMS:
        for item in dimension_stats(db, user_id, dim, now)["items"]:
            if item["mastery"] >= threshold:
                continue
            if item["weight"] < MIN_WEIGHT_FOR_WEAK:
                continue
            if item["question_count"] <= 0:
                continue  # 没有题可练的维度不做推荐
            if dim == "entry" and item["key"] == "0":
                continue  # 「未关联资料」不是知识点，不做定向推荐
            items.append({**item, "dim": dim, "dim_label": DIM_TEXT[dim]})
    items.sort(key=lambda x: (x["mastery"], -x["weight"]))
    return {"threshold": threshold, "items": items[:limit]}


def overview(db, user_id: int, threshold: float = DEFAULT_THRESHOLD, now: datetime | None = None) -> dict:
    observations = load_observations(db, user_id, now)
    overall = aggregate(observations)
    weak = weak_points(db, user_id, threshold=threshold, limit=5, now=now)
    wrong_total = (
        db.query(func.count(WrongQuestion.id))
        .filter(WrongQuestion.user_id == user_id, WrongQuestion.repetitions < MASTERY_REPETITIONS)
        .scalar()
        or 0
    )
    tested_dims = sum(
        1
        for dim in DIMS
        for item in dimension_stats(db, user_id, dim, now)["items"]
        if item["answered"] > 0
    )
    return {
        "total_answered": overall["answered"],
        "total_correct": overall["correct"],
        "overall_accuracy": overall["accuracy"],
        "overall_mastery": overall["mastery"],
        "confidence": overall["confidence"],
        "weak_count": len(weak["items"]),
        "tested_dimension_count": tested_dims,
        "wrong_pending_total": int(wrong_total),
        "threshold": threshold,
        "top_weak": weak["items"][0] if weak["items"] else None,
    }


# ---------------------------------------------------------------- 定向练习取材
def _filter_dim(query, dim: str, key):
    if dim == "q_type":
        return query.filter(Question.q_type == key)
    if dim == "difficulty":
        return query.filter(Question.difficulty == key)
    entry_id = normalize_key("entry", key)
    if entry_id:
        return query.filter(Question.entry_id == entry_id)
    return query.filter(Question.entry_id.is_(None))  # 0 表示「未关联资料」


def targeted_questions(
    db,
    user_id: int,
    dim: str,
    key,
    count: int,
    types: list[str] | None = None,
    now: datetime | None = None,
) -> list[Question]:
    """按薄弱维度挑题：错题本未掌握 → 从未作答 → 其余，保证「薄弱优先但不重复刷旧题」。"""
    if dim not in DIMS:
        raise ValueError("维度不合法：仅支持 q_type / difficulty / entry")

    base = db.query(Question).filter(
        Question.user_id == user_id,
        Question.status == "active",
        Question.review_status == "approved",
    )
    if types:
        base = base.filter(Question.q_type.in_(types))
    base = _filter_dim(base, dim, key)
    candidates = base.all()
    if not candidates:
        raise ValueError("该维度下没有可练习的已审核题目")

    wrong_ids = {
        row[0]
        for row in db.query(WrongQuestion.question_id)
        .filter(WrongQuestion.user_id == user_id, WrongQuestion.repetitions < MASTERY_REPETITIONS)
        .all()
    }
    answered_ids = {
        row[0]
        for row in db.query(ExamAnswer.question_id)
        .join(ExamSession, ExamSession.id == ExamAnswer.session_id)
        .filter(ExamSession.user_id == user_id, ExamSession.status == "submitted")
        .all()
    }

    pool_wrong = [q for q in candidates if q.id in wrong_ids]
    # 未作答题池要排除错题池，否则会把错题的占比顶上去
    pool_fresh = [q for q in candidates if q.id not in answered_ids and q.id not in wrong_ids]
    picked_ids = {q.id for q in pool_wrong} | {q.id for q in pool_fresh}
    pool_rest = [q for q in candidates if q.id not in picked_ids]

    random.shuffle(pool_wrong)
    random.shuffle(pool_fresh)
    random.shuffle(pool_rest)

    chosen: list[Question] = []
    chosen_ids: set[int] = set()

    def take(pool: list[Question], limit: int) -> None:
        for question in pool:
            if len(chosen) >= limit or question.id in chosen_ids:
                continue
            chosen.append(question)
            chosen_ids.add(question.id)

    # 错题本占比设上限：定向练习要补弱，但也不能只刷旧题
    take(pool_wrong, min(count, max(1, int(count * WRONG_RATIO))))
    take(pool_fresh, count)
    take(pool_rest, count)
    # 仍未取满说明候选池高度重叠（例如该维度的题几乎全在错题本里）。
    # 此时解除占比上限补齐：题目不够时宁可多练错题，也不能组不出卷。
    if len(chosen) < count:
        take(pool_wrong, count)
        take(pool_fresh, count)
        take(pool_rest, count)

    if len(chosen) < count:
        raise ValueError(
            f"该维度下可组题目仅 {len(chosen)} 道（可用候选 {len(candidates)} 道），"
            f"不足 {count} 道，请减少数量或放宽筛选条件"
        )
    return chosen


def dimension_mastery(
    db, user_id: int, dim: str, key, now: datetime | None = None
) -> dict | None:
    """取单个维度键的掌握度（定向组卷标题用）。"""
    for item in dimension_stats(db, user_id, dim, now)["items"]:
        if str(item["key"]) == str(key):
            return item
    return None
