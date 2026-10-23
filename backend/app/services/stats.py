"""统计分析查询：题目分析平台与做题分析平台的数据源。"""

from datetime import datetime, timedelta

from sqlalchemy import case, func

from ..models import ExamAnswer, ExamSession, KnowledgeEntry, Question


def _questions_base(db, user_id: int):
    return db.query(Question).filter(Question.user_id == user_id, Question.status == "active")


def questions_overview(db, user_id: int) -> dict:
    base = _questions_base(db, user_id)
    total = base.count()
    llm_count = base.filter(Question.source == "llm").count()

    type_rows = (
        base.with_entities(Question.q_type, func.count(Question.id))
        .group_by(Question.q_type)
        .all()
    )
    type_map = {"choice": 0, "fill": 0, "judge": 0}
    for q_type, count in type_rows:
        type_map[q_type] = count

    difficulty_rows = (
        base.with_entities(Question.difficulty, func.count(Question.id))
        .group_by(Question.difficulty)
        .all()
    )
    difficulty_map = {"easy": 0, "medium": 0, "hard": 0}
    for level, count in difficulty_rows:
        difficulty_map[level] = count

    entry_rows = (
        db.query(KnowledgeEntry.id, KnowledgeEntry.title, func.count(Question.id))
        .join(Question, Question.entry_id == KnowledgeEntry.id)
        .filter(Question.user_id == user_id, Question.status == "active")
        .group_by(KnowledgeEntry.id, KnowledgeEntry.title)
        .order_by(func.count(Question.id).desc())
        .all()
    )

    answered_count = (
        db.query(func.count(func.distinct(ExamAnswer.question_id)))
        .join(Question, Question.id == ExamAnswer.question_id)
        .filter(Question.user_id == user_id)
        .scalar()
        or 0
    )

    return {
        "total": total,
        "llm_count": llm_count,
        "rule_count": total - llm_count,
        "answered_count": answered_count,
        "by_type": [{"key": k, "count": v} for k, v in type_map.items()],
        "by_difficulty": [{"key": k, "count": v} for k, v in difficulty_map.items()],
        "by_entry": [
            {"entry_id": eid, "title": title, "count": count} for eid, title, count in entry_rows
        ],
    }


def questions_accuracy(db, user_id: int, limit: int = 10) -> dict:
    rows = (
        db.query(
            Question.id,
            Question.content,
            Question.q_type,
            KnowledgeEntry.title,
            func.count(ExamAnswer.id).label("answered"),
            func.sum(case((ExamAnswer.is_correct.is_(True), 1), else_=0)).label("correct"),
        )
        .join(ExamAnswer, ExamAnswer.question_id == Question.id)
        .join(ExamSession, ExamSession.id == ExamAnswer.session_id)
        .outerjoin(KnowledgeEntry, KnowledgeEntry.id == Question.entry_id)
        .filter(Question.user_id == user_id, ExamSession.status == "submitted")
        .group_by(Question.id)
        .all()
    )
    items = []
    for qid, content, q_type, entry_title, answered, correct in rows:
        answered = answered or 0
        correct = int(correct or 0)
        items.append(
            {
                "question_id": qid,
                "content": (content or "")[:80],
                "q_type": q_type,
                "entry_title": entry_title,
                "answered_count": answered,
                "correct_count": correct,
                "accuracy": round(correct / answered, 3) if answered else 0.0,
            }
        )
    items.sort(key=lambda x: (x["accuracy"], -x["answered_count"]))
    return {"items": items[:limit]}


def practice_overview(db, user_id: int) -> dict:
    sessions = (
        db.query(ExamSession)
        .filter(ExamSession.user_id == user_id)
        .order_by(ExamSession.id.desc())
        .all()
    )
    submitted = [s for s in sessions if s.status == "submitted"]
    rates = [s.total_score / s.max_score for s in submitted if s.max_score]
    answer_stats = (
        db.query(
            func.count(ExamAnswer.id),
            func.sum(case((ExamAnswer.is_correct.is_(True), 1), else_=0)),
        )
        .join(ExamSession, ExamSession.id == ExamAnswer.session_id)
        .filter(ExamSession.user_id == user_id, ExamSession.status == "submitted")
        .one()
    )
    total_answered = int(answer_stats[0] or 0)
    total_correct = int(answer_stats[1] or 0)
    return {
        "session_count": len(sessions),
        "submitted_count": len(submitted),
        "avg_score_rate": round(sum(rates) / len(rates), 3) if rates else 0.0,
        "total_answered": total_answered,
        "total_correct": total_correct,
        "overall_accuracy": round(total_correct / total_answered, 3) if total_answered else 0.0,
        "best_score_rate": round(max(rates), 3) if rates else 0.0,
    }


def practice_trend(db, user_id: int, days: int = 30) -> dict:
    since = datetime.utcnow() - timedelta(days=days)
    sessions = (
        db.query(ExamSession)
        .filter(
            ExamSession.user_id == user_id,
            ExamSession.status == "submitted",
            ExamSession.submitted_at.isnot(None),
            ExamSession.submitted_at >= since,
        )
        .all()
    )
    by_date: dict[str, dict] = {}
    for session in sessions:
        date_key = session.submitted_at.strftime("%Y-%m-%d")
        bucket = by_date.setdefault(
            date_key, {"date": date_key, "session_count": 0, "score_sum": 0.0, "answered": 0, "correct": 0}
        )
        bucket["session_count"] += 1
        if session.max_score:
            bucket["score_sum"] += session.total_score / session.max_score
    # 每日答题数需要按答案聚合
    answer_rows = (
        db.query(func.date(ExamAnswer.created_at), func.count(ExamAnswer.id), func.sum(case((ExamAnswer.is_correct.is_(True), 1), else_=0)))
        .join(ExamSession, ExamSession.id == ExamAnswer.session_id)
        .filter(
            ExamSession.user_id == user_id,
            ExamSession.status == "submitted",
            ExamAnswer.created_at >= since,
        )
        .group_by(func.date(ExamAnswer.created_at))
        .all()
    )
    for date_value, answered, correct in answer_rows:
        date_key = str(date_value)
        bucket = by_date.setdefault(
            date_key, {"date": date_key, "session_count": 0, "score_sum": 0.0, "answered": 0, "correct": 0}
        )
        bucket["answered"] = int(answered or 0)
        bucket["correct"] = int(correct or 0)

    items = []
    for date_key in sorted(by_date):
        bucket = by_date[date_key]
        items.append(
            {
                "date": date_key,
                "session_count": bucket["session_count"],
                "avg_score_rate": round(bucket["score_sum"] / bucket["session_count"], 3)
                if bucket["session_count"]
                else 0.0,
                "answered": bucket["answered"],
                "correct": bucket["correct"],
            }
        )
    return {"items": items}


def practice_by_type(db, user_id: int) -> dict:
    rows = (
        db.query(
            Question.q_type,
            func.count(ExamAnswer.id),
            func.sum(case((ExamAnswer.is_correct.is_(True), 1), else_=0)),
            func.avg(ExamAnswer.score),
        )
        .join(ExamAnswer, ExamAnswer.question_id == Question.id)
        .join(ExamSession, ExamSession.id == ExamAnswer.session_id)
        .filter(ExamSession.user_id == user_id, ExamSession.status == "submitted")
        .group_by(Question.q_type)
        .all()
    )
    order = {"choice": 0, "fill": 1, "judge": 2}
    items = []
    for q_type, answered, correct, avg_score in sorted(rows, key=lambda r: order.get(r[0], 9)):
        answered = int(answered or 0)
        correct = int(correct or 0)
        items.append(
            {
                "q_type": q_type,
                "answered": answered,
                "correct": correct,
                "accuracy": round(correct / answered, 3) if answered else 0.0,
                "avg_score": round(float(avg_score or 0.0), 1),
            }
        )
    return {"items": items}


def recent_sessions(db, user_id: int, limit: int = 10) -> dict:
    sessions = (
        db.query(ExamSession)
        .filter(ExamSession.user_id == user_id, ExamSession.status == "submitted")
        .order_by(ExamSession.id.desc())
        .limit(limit)
        .all()
    )
    items = []
    for session in sessions:
        answers = session.answers
        items.append(
            {
                "id": session.id,
                "paper_title": session.paper.title if session.paper else "",
                "total_score": session.total_score,
                "max_score": session.max_score,
                "score_rate": round(session.total_score / session.max_score, 3) if session.max_score else 0.0,
                "correct_count": sum(1 for a in answers if a.is_correct),
                "question_count": len(answers),
                "duration_sec": session.duration_sec,
                "submitted_at": session.submitted_at,
            }
        )
    return {"items": items}
