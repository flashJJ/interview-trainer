"""错题本路由：列表 / 统计 / 生成复习卷 / 手动掌握 / 移出。

复习卷通过 ExamPaper（config.mode=review）实现，复用现有考试与提交流程；
提交时 grader 会按 SM-2 更新排期（见 services/srs.py）。
"""

import json
import random
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..database import get_db
from ..dependencies import get_current_user
from ..models import ExamPaper, ExamPaperQuestion, Question, User, WrongQuestion
from ..schemas import (
    ExamPaperOut,
    ReviewGenerateIn,
    WrongQuestionItem,
    WrongQuestionListOut,
    WrongQuestionStatsOut,
)

router = APIRouter(prefix="/wrong-questions", tags=["wrong-questions"])


def _item(wrong: WrongQuestion) -> WrongQuestionItem:
    question = wrong.question
    return WrongQuestionItem(
        id=wrong.id,
        question_id=wrong.question_id,
        content=question.content,
        q_type=question.q_type,
        options=question.options,
        answer=question.answer,
        explanation=question.explanation,
        difficulty=question.difficulty,
        entry_title=question.entry.title if question.entry else None,
        error_count=wrong.error_count,
        interval_days=wrong.interval_days,
        repetitions=wrong.repetitions,
        due_date=wrong.due_date,
        days_until_due=(wrong.due_date - date.today()).days,
        last_error_at=wrong.last_error_at,
    )


@router.get("", response_model=WrongQuestionListOut)
def list_wrong_questions(
    page: int = 1,
    size: int = 10,
    q_type: str = "",
    only_due: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(WrongQuestion).filter(WrongQuestion.user_id == current_user.id)
    if only_due:
        query = query.filter(WrongQuestion.due_date <= date.today())
    if q_type:
        query = query.join(Question, Question.id == WrongQuestion.question_id).filter(
            Question.q_type == q_type
        )
    total = query.count()
    items = (
        query.order_by(WrongQuestion.due_date.asc(), WrongQuestion.error_count.desc())
        .offset((page - 1) * size)
        .limit(size)
        .all()
    )
    return WrongQuestionListOut(
        items=[_item(w) for w in items], total=total, page=page, size=size
    )


@router.get("/stats", response_model=WrongQuestionStatsOut)
def wrong_question_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    today = date.today()
    base = db.query(WrongQuestion).filter(WrongQuestion.user_id == current_user.id)
    type_rows = (
        db.query(Question.q_type, func.count(WrongQuestion.id))
        .join(Question, Question.id == WrongQuestion.question_id)
        .filter(WrongQuestion.user_id == current_user.id)
        .group_by(Question.q_type)
        .all()
    )
    return WrongQuestionStatsOut(
        total=base.count(),
        due_today=base.filter(WrongQuestion.due_date == today).count(),
        overdue=base.filter(WrongQuestion.due_date < today).count(),
        due_next_7_days=base.filter(
            WrongQuestion.due_date > today, WrongQuestion.due_date <= today + timedelta(days=7)
        ).count(),
        by_type={t: c for t, c in type_rows},
    )


@router.post("/review/generate", response_model=ExamPaperOut)
def generate_review_paper(
    payload: ReviewGenerateIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """从到期错题随机组一份复习卷（复用考卷/会话/提交链路）。"""
    today = date.today()
    due = (
        db.query(WrongQuestion)
        .filter(WrongQuestion.user_id == current_user.id, WrongQuestion.due_date <= today)
        .all()
    )
    if not due:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "当前没有到期（含逾期）的错题，先去练习或等待复习日期到达",
        )
    chosen = random.sample(due, min(payload.count, len(due)))
    paper = ExamPaper(
        user_id=current_user.id,
        title=f"错题复习 · {len(chosen)} 题（到期 {len(due)} 道）",
        question_count=len(chosen),
        config=json.dumps({"mode": "review", "count": len(chosen)}, ensure_ascii=False),
    )
    db.add(paper)
    db.flush()
    for order, wrong in enumerate(chosen):
        db.add(ExamPaperQuestion(paper_id=paper.id, question_id=wrong.question_id, order=order))
    db.commit()
    db.refresh(paper)
    return ExamPaperOut(
        id=paper.id,
        title=paper.title,
        question_count=paper.question_count,
        config=json.loads(paper.config or "{}"),
        created_at=paper.created_at,
        latest_session=None,
    )


@router.post("/{wrong_id}/master")
def mark_mastered(
    wrong_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """手动标记掌握，移出错题本。"""
    wrong = db.get(WrongQuestion, wrong_id)
    if wrong is None or wrong.user_id != current_user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "错题记录不存在")
    db.delete(wrong)
    db.commit()
    return {"ok": True, "message": "已标记掌握，移出错题本"}


@router.delete("/{wrong_id}")
def remove_wrong_question(
    wrong_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """移出错题本（不再复习该题）。"""
    wrong = db.get(WrongQuestion, wrong_id)
    if wrong is None or wrong.user_id != current_user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "错题记录不存在")
    db.delete(wrong)
    db.commit()
    return {"ok": True, "message": "已移出错题本"}
