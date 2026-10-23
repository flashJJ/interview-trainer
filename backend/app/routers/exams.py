"""考试路由：随机组卷 / 考卷管理 / 开始考试 / 提交评分 / 成绩查询。

注意路由声明顺序：/sessions 相关路径必须先于 /{paper_id} 声明，避免被动态路径捕获。
"""

import json
import random
from collections import Counter

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..database import get_db
from ..dependencies import get_current_user
from ..models import ExamPaper, ExamPaperQuestion, ExamSession, Question, User
from ..schemas import (
    AnswerResultOut,
    ExamDetailOut,
    ExamListOut,
    ExamPaperOut,
    ExamQuestionOut,
    GenerateExamIn,
    SessionDetailOut,
    SessionListItem,
    SessionListOut,
    StartExamOut,
    SubmitExamIn,
    SubmitExamOut,
)
from ..services.grader import Grader, grade_and_submit_session
from ..services.runtime import get_embeddings, get_llm

router = APIRouter(prefix="/exams", tags=["exams"])

_TYPE_NAME = {"choice": "单选", "fill": "填空", "judge": "判断"}


def _auto_title(questions: list[Question]) -> str:
    dist = Counter(q.q_type for q in questions)
    parts = [f"{_TYPE_NAME.get(t, t)}×{c}" for t, c in dist.items() if c]
    return f"随机考卷 · {len(questions)} 题（{' '.join(parts)}）"


def _exam_question(question: Question) -> ExamQuestionOut:
    return ExamQuestionOut(
        id=question.id,
        q_type=question.q_type,
        content=question.content,
        options=question.options,
        difficulty=question.difficulty,
    )


def _paper_out(db: Session, paper: ExamPaper, user_id: int) -> ExamPaperOut:
    session = (
        db.query(ExamSession)
        .filter(ExamSession.paper_id == paper.id, ExamSession.user_id == user_id)
        .order_by(ExamSession.id.desc())
        .first()
    )
    latest = None
    if session is not None:
        latest = {
            "id": session.id,
            "status": session.status,
            "total_score": session.total_score,
            "max_score": session.max_score,
            "submitted_at": session.submitted_at,
        }
    return ExamPaperOut(
        id=paper.id,
        title=paper.title,
        question_count=paper.question_count,
        config=json.loads(paper.config or "{}"),
        created_at=paper.created_at,
        latest_session=latest,
    )


# ---------------------------------------------------------------- 组卷
@router.post("/generate", response_model=ExamPaperOut)
def generate_exam(
    payload: GenerateExamIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(Question).filter(
        Question.user_id == current_user.id,
        Question.status == "active",
        Question.q_type.in_(payload.types),
    )
    if payload.difficulty:
        query = query.filter(Question.difficulty == payload.difficulty)
    if payload.entry_ids:
        query = query.filter(Question.entry_id.in_(payload.entry_ids))

    available = query.count()
    if available < payload.count:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"符合条件的题目仅 {available} 道，请减少数量或放宽筛选条件",
        )

    all_ids = [row[0] for row in query.with_entities(Question.id).all()]
    chosen_ids = random.sample(all_ids, payload.count)
    questions = db.query(Question).filter(Question.id.in_(chosen_ids)).all()
    random.shuffle(questions)

    paper = ExamPaper(
        user_id=current_user.id,
        title=payload.title.strip() or _auto_title(questions),
        question_count=len(questions),
        config=json.dumps(
            {
                "count": payload.count,
                "types": payload.types,
                "difficulty": payload.difficulty,
                "entry_ids": payload.entry_ids,
            },
            ensure_ascii=False,
        ),
    )
    db.add(paper)
    db.flush()
    for order, question in enumerate(questions):
        db.add(ExamPaperQuestion(paper_id=paper.id, question_id=question.id, order=order))
    db.commit()
    db.refresh(paper)
    return _paper_out(db, paper, current_user.id)


# ---------------------------------------------------------------- 考卷列表/详情
@router.get("", response_model=ExamListOut)
def list_exams(
    page: int = 1,
    size: int = 10,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(ExamPaper).filter(ExamPaper.user_id == current_user.id)
    total = query.count()
    papers = query.order_by(ExamPaper.id.desc()).offset((page - 1) * size).limit(size).all()
    return ExamListOut(
        items=[_paper_out(db, p, current_user.id) for p in papers],
        total=total,
        page=page,
        size=size,
    )


@router.get("/sessions", response_model=SessionListOut)
def list_sessions(
    page: int = 1,
    size: int = 10,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(ExamSession).filter(
        ExamSession.user_id == current_user.id, ExamSession.status == "submitted"
    )
    total = query.count()
    sessions = query.order_by(ExamSession.id.desc()).offset((page - 1) * size).limit(size).all()
    items = []
    for session in sessions:
        answers = session.answers
        items.append(
            SessionListItem(
                id=session.id,
                paper_title=session.paper.title if session.paper else "",
                total_score=session.total_score,
                max_score=session.max_score,
                score_rate=round(session.total_score / session.max_score, 3) if session.max_score else 0.0,
                correct_count=sum(1 for a in answers if a.is_correct),
                question_count=len(answers),
                duration_sec=session.duration_sec,
                submitted_at=session.submitted_at,
            )
        )
    return SessionListOut(items=items, total=total, page=page, size=size)


@router.get("/sessions/{session_id}", response_model=SessionDetailOut)
def session_detail(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    session = db.get(ExamSession, session_id)
    if session is None or session.user_id != current_user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "考试记录不存在")
    answers = {a.question_id: a for a in session.answers}
    items = sorted(session.paper.items, key=lambda i: i.order)
    results = []
    for item in items:
        question = item.question
        answer = answers.get(question.id)
        results.append(
            AnswerResultOut(
                question_id=question.id,
                q_type=question.q_type,
                content=question.content,
                options=question.options,
                answer=question.answer,
                user_answer=answer.user_answer if answer else "",
                score=answer.score if answer else 0.0,
                max_score=answer.max_score if answer else 10.0,
                is_correct=answer.is_correct if answer else False,
                feedback=answer.feedback if answer else "未作答",
                explanation=question.explanation,
                ai_source=answer.ai_source if answer else "rule",
            )
        )
    return SessionDetailOut(
        session_id=session.id,
        total_score=session.total_score,
        max_score=session.max_score,
        score_rate=round(session.total_score / session.max_score, 3) if session.max_score else 0.0,
        correct_count=sum(1 for r in results if r.is_correct),
        question_count=len(results),
        duration_sec=session.duration_sec,
        results=results,
        paper_title=session.paper.title if session.paper else "",
    )


@router.get("/{paper_id}", response_model=ExamDetailOut)
def exam_detail(
    paper_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    paper = db.get(ExamPaper, paper_id)
    if paper is None or paper.user_id != current_user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "考卷不存在")
    items = sorted(paper.items, key=lambda i: i.order)
    return ExamDetailOut(
        paper=_paper_out(db, paper, current_user.id),
        questions=[_exam_question(item.question) for item in items],
    )


# ---------------------------------------------------------------- 考试会话
@router.post("/{paper_id}/start", response_model=StartExamOut)
def start_exam(
    paper_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    paper = db.get(ExamPaper, paper_id)
    if paper is None or paper.user_id != current_user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "考卷不存在")
    # 同一考卷的未提交会话可续考
    session = (
        db.query(ExamSession)
        .filter(
            ExamSession.paper_id == paper.id,
            ExamSession.user_id == current_user.id,
            ExamSession.status == "in_progress",
        )
        .order_by(ExamSession.id.desc())
        .first()
    )
    if session is None:
        session = ExamSession(
            user_id=current_user.id,
            paper_id=paper.id,
            status="in_progress",
            mode=json.loads(paper.config or "{}").get("mode", "exam"),
        )
        db.add(session)
        db.commit()
        db.refresh(session)
    items = sorted(paper.items, key=lambda i: i.order)
    saved_answers = [
        {"question_id": a.question_id, "user_answer": a.user_answer}
        for a in session.answers
        if a.user_answer and a.user_answer.strip()
    ]
    return StartExamOut(
        session=session,
        questions=[_exam_question(item.question) for item in items],
        answers=saved_answers,
    )


@router.post("/sessions/{session_id}/submit", response_model=SubmitExamOut)
def submit_exam(
    session_id: int,
    payload: SubmitExamIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    session = db.get(ExamSession, session_id)
    if session is None or session.user_id != current_user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "考试记录不存在")
    if session.status == "submitted":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "该考试已提交，不能重复评分")

    answers_map = {a.question_id: a.answer for a in payload.answers}
    grader = Grader(llm=get_llm(), embeddings=get_embeddings())
    try:
        result = grade_and_submit_session(db, session, answers_map, grader)
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    return SubmitExamOut(**result)


@router.post("/sessions/{session_id}/save")
def save_exam_answers(
    session_id: int,
    payload: SubmitExamIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """保存未提交考试的作答草稿（断点续考）。仅进行中的会话可保存。"""
    from ..models import ExamAnswer

    session = db.get(ExamSession, session_id)
    if session is None or session.user_id != current_user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "考试记录不存在")
    if session.status == "submitted":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "考试已提交，无法保存草稿")

    valid_qids = {item.question_id for item in session.paper.items}
    existing = {a.question_id: a for a in session.answers}
    for item in payload.answers:
        if item.question_id not in valid_qids:
            continue
        answer = (item.answer or "").strip()
        row = existing.get(item.question_id)
        if row is None:
            if answer:
                db.add(
                    ExamAnswer(
                        session_id=session.id,
                        question_id=item.question_id,
                        user_answer=answer,
                        score=0.0,
                        max_score=10.0,
                        is_correct=False,
                        feedback="",
                        ai_source="draft",
                    )
                )
        else:
            row.user_answer = answer
    # 清理被清空的草稿行
    for row in existing.values():
        if not row.user_answer.strip():
            db.delete(row)
    db.commit()
    saved = sum(1 for a in session.answers if a.user_answer.strip())
    return {"ok": True, "saved": saved}
