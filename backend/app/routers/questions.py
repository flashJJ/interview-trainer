"""题库路由：AI 出题 / 列表 / 详情 / 编辑 / 删除 / 审核 / 统计。

审核流：新生成的题目进入待审核（pending），审核通过（approved）后才进入
组卷池；拒绝（rejected）的题目不出现在题库默认视图。
"""

import json
import re

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..database import get_db
from ..dependencies import get_current_user
from ..models import ExamPaperQuestion, KnowledgeEntry, KnowledgeChunk, Question, User
from ..schemas import (
    BatchReviewIn,
    GenerateQuestionsIn,
    GenerateQuestionsOut,
    QuestionListOut,
    QuestionOut,
    QuestionStatsOut,
    QuestionUpdateIn,
    ReviewActionIn,
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
        review_status=question.review_status,
        created_at=question.created_at,
    )


def _validate_question_payload(data: dict, q_type: str) -> str | None:
    """校验编辑后的题目合法性，返回错误信息（None 表示通过）。"""
    content = (data.get("content") or "").strip()
    if not (5 <= len(content) <= 600):
        return "题干长度需在 5~600 字符之间"
    if q_type == "choice":
        options = data.get("options") or []
        if not isinstance(options, list) or len(options) != 4:
            return "选择题必须恰好 4 个选项"
        if any(not str(o).strip() for o in options):
            return "选项不能为空"
        answer = str(data.get("answer") or "").strip().upper()
        if answer not in "ABCD":
            return "选择题答案必须是 A/B/C/D"
    elif q_type == "fill":
        if not re.search(r"_{3,}|（\s*）|\(\s*\)", content):
            return "填空题题干必须包含 ______ 空位"
        if not str(data.get("answer") or "").strip():
            return "填空题答案不能为空"
    elif q_type == "judge":
        if str(data.get("answer") or "").strip() not in ("正确", "错误"):
            return "判断题答案必须是「正确」或「错误」"
    if data.get("difficulty") and data["difficulty"] not in ("easy", "medium", "hard"):
        return "难度必须是 easy/medium/hard"
    return None


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
        message=f"{outcome.message}（新题待审核，通过后进入组卷池）",
    )


@router.get("", response_model=QuestionListOut)
def list_questions(
    page: int = 1,
    size: int = 10,
    q_type: str = "",
    difficulty: str = "",
    entry_id: int | None = None,
    keyword: str = "",
    review_status: str = "approved",  # approved | pending | rejected | all
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(Question).filter(
        Question.user_id == current_user.id, Question.status == "active"
    )
    if review_status and review_status != "all":
        query = query.filter(Question.review_status == review_status)
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
    approved = base.filter(Question.review_status == "approved").count()
    pending = base.filter(Question.review_status == "pending").count()
    rejected = base.filter(Question.review_status == "rejected").count()
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
        approved_count=approved,
        pending_count=pending,
        rejected_count=rejected,
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


@router.put("/{question_id}", response_model=QuestionOut)
def update_question(
    question_id: int,
    payload: QuestionUpdateIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """编辑题目内容（审核场景：修正后通过）。"""
    question = db.get(Question, question_id)
    if question is None or question.user_id != current_user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "题目不存在")

    data = payload.model_dump(exclude_none=True)
    merged = {
        "content": data.get("content", question.content),
        "options": data.get("options", question.options or []),
        "answer": data.get("answer", question.answer),
        "difficulty": data.get("difficulty", question.difficulty),
    }
    error = _validate_question_payload(merged, question.q_type)
    if error:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, error)

    if "content" in data:
        question.content = data["content"]
    if "options" in data and question.q_type == "choice":
        # 统一补全 A./B./C./D. 前缀，保证与答案字母对应
        cleaned = [re.sub(r"^[A-Da-d]\s*[.、:：]\s*", "", str(o).strip()) for o in data["options"]]
        question.options_json = json.dumps(
            [f"{'ABCD'[i]}. {text}" for i, text in enumerate(cleaned)], ensure_ascii=False
        )
    if "answer" in data:
        answer = str(data["answer"]).strip()
        if question.q_type == "choice":
            answer = answer.upper()[:1]
        question.answer = answer
    if "explanation" in data:
        question.explanation = data["explanation"]
    if "difficulty" in data:
        question.difficulty = data["difficulty"]
    db.commit()
    db.refresh(question)
    return _question_out(question)


@router.post("/{question_id}/review", response_model=QuestionOut)
def review_question(
    question_id: int,
    payload: ReviewActionIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """单题审核：approve 通过入组卷池 / reject 拒绝。"""
    question = db.get(Question, question_id)
    if question is None or question.user_id != current_user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "题目不存在")
    if payload.action not in ("approve", "reject"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "action 必须是 approve 或 reject")
    question.review_status = "approved" if payload.action == "approve" else "rejected"
    db.commit()
    db.refresh(question)
    return _question_out(question)


@router.post("/review/batch")
def batch_review(
    payload: BatchReviewIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """批量审核（如整份资料一键通过）。"""
    if payload.action not in ("approve", "reject"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "action 必须是 approve 或 reject")
    target = "approved" if payload.action == "approve" else "rejected"
    updated = (
        db.query(Question)
        .filter(
            Question.id.in_(payload.question_ids),
            Question.user_id == current_user.id,
        )
        .update({"review_status": target}, synchronize_session=False)
    )
    db.commit()
    return {"ok": True, "updated": updated, "message": f"已批量{('通过' if payload.action == 'approve' else '拒绝')} {updated} 道题"}


@router.delete("/{question_id}")
def delete_question(
    question_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    referenced = (
        db.query(func.count(ExamPaperQuestion.id))
        .filter(ExamPaperQuestion.question_id == question_id)
        .scalar()
        or 0
    )
    if referenced:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "该题目已被考卷引用，暂不支持删除（可先删除对应考卷）",
        )
    question = db.get(Question, question_id)
    if question is None or question.user_id != current_user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "题目不存在")
    get_vector_store().delete_question_vector(question.id)
    entry_id = question.entry_id
    db.delete(question)
    db.commit()
    refresh_entry_question_counts(db, [entry_id])
    return {"ok": True, "message": "已删除题目"}
