"""题库路由：AI 出题 / 列表 / 详情 / 删除 / 统计。"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..database import get_db
from ..dependencies import get_current_user
from ..models import KnowledgeChunk, KnowledgeEntry, Question, User
from ..schemas import (
    GenerateQuestionsIn,
    GenerateQuestionsOut,
    QuestionListOut,
    QuestionOut,
    QuestionStatsOut,
)
from ..services.generator import (
    ChunkLike,
    QuestionGenerator,
    persist_drafts,
    refresh_entry_question_counts,
)
from ..services.runtime import get_embeddings, get_llm, get_vector_store

router = APIRouter(prefix="/questions", tags=["questions"])


def _question_out(question: Question) -> QuestionOut:
    return QuestionOut(
        id=question.id,
        q_type=question.q_type,
        content=question.content,
        options=question.options,
        answer=question.answer,
        explanation=question.explanation,
        difficulty=question.difficulty,
        keywords=question.keywords,
        entry_id=question.entry_id,
        entry_title=question.entry.title if question.entry else None,
        source=question.source,
        created_at=question.created_at,
    )


@router.post("/generate", response_model=GenerateQuestionsOut)
def generate_questions(
    payload: GenerateQuestionsIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if payload.entry_id is not None:
        entry = db.get(KnowledgeEntry, payload.entry_id)
        if entry is None or entry.user_id != current_user.id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "知识条目不存在")
        if entry.status != "ready":
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                f"资料尚未处理完成（当前状态：{entry.status}），暂不能出题",
            )
        chunks = (
            db.query(KnowledgeChunk)
            .filter(KnowledgeChunk.entry_id == entry.id)
            .order_by(KnowledgeChunk.seq)
            .all()
        )
    else:
        chunks = (
            db.query(KnowledgeChunk)
            .join(KnowledgeEntry, KnowledgeEntry.id == KnowledgeChunk.entry_id)
            .filter(KnowledgeEntry.user_id == current_user.id)
            .all()
        )

    if not chunks:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "知识库为空，请先录入资料")

    chunk_likes = [
        ChunkLike(id=c.id, content=c.content, entry_id=c.entry_id) for c in chunks
    ]
    generator = QuestionGenerator(
        llm=get_llm(), embeddings=get_embeddings(), vector_store=get_vector_store()
    )
    outcome = generator.generate(
        chunk_likes,
        types=payload.types,
        count_per_type=payload.count_per_type,
        difficulty=payload.difficulty,
        user_id=current_user.id,
    )

    created_questions = []
    if outcome.drafts:
        created_questions = persist_drafts(
            db, current_user.id, outcome.drafts, get_embeddings(), get_vector_store()
        )
        refresh_entry_question_counts(db, [d.entry_id for d in outcome.drafts])

    return GenerateQuestionsOut(
        created=[_question_out(q) for q in created_questions],
        created_count=len(created_questions),
        skipped_count=outcome.skipped_count,
        mode=outcome.mode,
        message=outcome.message,
    )


@router.get("", response_model=QuestionListOut)
def list_questions(
    page: int = 1,
    size: int = 10,
    q_type: str = "",
    difficulty: str = "",
    entry_id: int | None = None,
    keyword: str = "",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(Question).filter(
        Question.user_id == current_user.id, Question.status == "active"
    )
    if q_type:
        query = query.filter(Question.q_type == q_type)
    if difficulty:
        query = query.filter(Question.difficulty == difficulty)
    if entry_id is not None:
        query = query.filter(Question.entry_id == entry_id)
    if keyword:
        query = query.filter(Question.content.like(f"%{keyword}%"))
    total = query.count()
    items = query.order_by(Question.id.desc()).offset((page - 1) * size).limit(size).all()
    return QuestionListOut(
        items=[_question_out(q) for q in items], total=total, page=page, size=size
    )


@router.get("/stats/overview", response_model=QuestionStatsOut)
def question_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    base = db.query(Question).filter(
        Question.user_id == current_user.id, Question.status == "active"
    )
    total = base.count()
    llm_count = base.filter(Question.source == "llm").count()
    type_rows = (
        base.with_entities(Question.q_type, func.count(Question.id))
        .group_by(Question.q_type)
        .all()
    )
    by_type = {"choice": 0, "fill": 0, "judge": 0}
    by_type.update({t: c for t, c in type_rows})
    difficulty_rows = (
        base.with_entities(Question.difficulty, func.count(Question.id))
        .group_by(Question.difficulty)
        .all()
    )
    by_difficulty = {"easy": 0, "medium": 0, "hard": 0}
    by_difficulty.update({d: c for d, c in difficulty_rows})
    entry_rows = (
        db.query(KnowledgeEntry.id, KnowledgeEntry.title, func.count(Question.id))
        .join(Question, Question.entry_id == KnowledgeEntry.id)
        .filter(Question.user_id == current_user.id, Question.status == "active")
        .group_by(KnowledgeEntry.id, KnowledgeEntry.title)
        .order_by(func.count(Question.id).desc())
        .all()
    )
    return QuestionStatsOut(
        total=total,
        llm_count=llm_count,
        rule_count=total - llm_count,
        by_type=by_type,
        by_difficulty=by_difficulty,
        by_entry=[
            {"entry_id": eid, "title": title, "count": count}
            for eid, title, count in entry_rows
        ],
    )


@router.get("/{question_id}", response_model=QuestionOut)
def question_detail(
    question_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    question = db.get(Question, question_id)
    if question is None or question.user_id != current_user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "题目不存在")
    return _question_out(question)


@router.delete("/{question_id}")
def delete_question(
    question_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from ..models import ExamPaperQuestion

    question = db.get(Question, question_id)
    if question is None or question.user_id != current_user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "题目不存在")
    referenced = (
        db.query(func.count(ExamPaperQuestion.id))
        .filter(ExamPaperQuestion.question_id == question.id)
        .scalar()
        or 0
    )
    if referenced:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "该题目已被考卷引用，暂不支持删除（可先删除对应考卷）",
        )
    get_vector_store().delete_question_vector(question.id)
    entry_id = question.entry_id
    db.delete(question)
    db.commit()
    refresh_entry_question_counts(db, [entry_id])
    return {"ok": True, "message": "已删除题目"}
