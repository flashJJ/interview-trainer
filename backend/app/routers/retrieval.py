"""检索评测路由：评测集管理 + 多模式评测运行 + 历史报告。

设计取舍：
- 评测集存库（而不是硬编码 JSON 文件），这样用户可以在界面上增删、也能针对自己的
  资料集评测；
- 每次运行保存完整快照（summary + 逐用例明细），便于回看"上次 Recall@5 是多少"，
  也让报告页能画出趋势。
"""

import json

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..database import commit_with_retry, get_db
from ..dependencies import get_current_user
from ..models import (
    KnowledgeChunk,
    KnowledgeEntry,
    RetrievalEvalCase,
    RetrievalEvalRun,
    User,
)
from ..schemas import (
    AutoBuildIn,
    AutoBuildOut,
    ChunkPickerItem,
    EvalCaseCreateIn,
    EvalCaseOut,
    EvalOverviewOut,
    EvalRunBrief,
    EvalRunIn,
    EvalRunOut,
)
from ..services import retrieval_eval

router = APIRouter(prefix="/retrieval", tags=["retrieval"])


def _case_out(db: Session, case: RetrievalEvalCase) -> EvalCaseOut:
    expected = case.expected_ids
    previews: list[str] = []
    if expected:
        rows = (
            db.query(KnowledgeChunk.id, KnowledgeChunk.content)
            .filter(KnowledgeChunk.id.in_(expected))
            .all()
        )
        previews = [(content or "")[:80] for _, content in rows]
    return EvalCaseOut(
        id=case.id,
        query=case.query,
        source=case.source,
        origin_chunk_id=case.origin_chunk_id or 0,
        note=case.note or "",
        created_at=case.created_at,
        expected_ids=expected,
        expected_preview=previews,
    )


@router.get("/overview", response_model=EvalOverviewOut)
def overview(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    case_count = (
        db.query(RetrievalEvalCase).filter(RetrievalEvalCase.user_id == current_user.id).count()
    )
    chunk_rows = (
        db.query(func.count(KnowledgeChunk.id), func.count(KnowledgeChunk.vector_id))
        .join(KnowledgeEntry, KnowledgeEntry.id == KnowledgeChunk.entry_id)
        .filter(KnowledgeEntry.user_id == current_user.id)
        .one()
    )
    latest = (
        db.query(RetrievalEvalRun)
        .filter(RetrievalEvalRun.user_id == current_user.id)
        .order_by(RetrievalEvalRun.id.desc())
        .first()
    )
    return EvalOverviewOut(
        case_count=int(case_count),
        chunk_count=int(chunk_rows[0] or 0),
        # ChromaDB 是进程级共享的，跨用户计数会失真，这里只统计本用户已建向量的块
        vector_count=int(chunk_rows[1] or 0),
        latest_run=_brief(latest) if latest else None,
    )


def _brief(run: RetrievalEvalRun) -> EvalRunBrief:
    return EvalRunBrief(
        id=run.id,
        case_count=run.case_count,
        top_k=run.top_k,
        use_rewrite=bool(run.use_rewrite),
        vector_weight=float(run.vector_weight or 1.0),
        elapsed_ms=run.elapsed_ms or 0,
        created_at=run.created_at,
        summary=run.summary,
    )


@router.get("/chunks", response_model=list[ChunkPickerItem])
def list_chunks(
    keyword: str = "",
    limit: int = 200,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """知识块候选（手工录入评测用例时选期望块用）。"""
    query = (
        db.query(
            KnowledgeChunk.id,
            KnowledgeChunk.entry_id,
            KnowledgeChunk.seq,
            KnowledgeChunk.content,
            KnowledgeEntry.title,
        )
        .join(KnowledgeEntry, KnowledgeEntry.id == KnowledgeChunk.entry_id)
        .filter(KnowledgeEntry.user_id == current_user.id)
    )
    if keyword.strip():
        query = query.filter(KnowledgeChunk.content.contains(keyword.strip()))
    rows = query.order_by(KnowledgeChunk.entry_id, KnowledgeChunk.seq).limit(
        max(1, min(limit, 500))
    )
    return [
        ChunkPickerItem(
            chunk_id=int(r[0]),
            entry_id=int(r[1]),
            seq=int(r[2]),
            entry_title=r[4] or "",
            preview=(r[3] or "")[:60],
        )
        for r in rows
    ]


@router.get("/cases", response_model=list[EvalCaseOut])
def list_cases(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    cases = (
        db.query(RetrievalEvalCase)
        .filter(RetrievalEvalCase.user_id == current_user.id)
        .order_by(RetrievalEvalCase.id.desc())
        .all()
    )
    return [_case_out(db, c) for c in cases]


@router.post("/cases", response_model=EvalCaseOut, status_code=status.HTTP_201_CREATED)
def create_case(
    payload: EvalCaseCreateIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    valid_ids = {
        int(r[0])
        for r in db.query(KnowledgeChunk.id).filter(KnowledgeChunk.id.in_(payload.expected_ids)).all()
    }
    missing = [i for i in payload.expected_ids if i not in valid_ids]
    if missing:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"期望块不存在：{missing}")
    case = RetrievalEvalCase(
        user_id=current_user.id,
        query=payload.query.strip(),
        expected_ids_json=json.dumps(sorted(valid_ids)),
        source="manual",
        origin_chunk_id=0,
        note=payload.note or "",
    )
    db.add(case)
    commit_with_retry(db)
    db.refresh(case)
    return _case_out(db, case)


@router.delete("/cases/{case_id}")
def delete_case(
    case_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    case = db.get(RetrievalEvalCase, case_id)
    if case is None or case.user_id != current_user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "评测用例不存在")
    db.delete(case)
    commit_with_retry(db)
    return {"ok": True}


@router.delete("/cases")
def clear_cases(
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    """清空当前用户的评测集（资料大改后重建评测集用；不影响历史运行记录）。"""
    deleted = (
        db.query(RetrievalEvalCase)
        .filter(RetrievalEvalCase.user_id == current_user.id)
        .delete(synchronize_session=False)
    )
    commit_with_retry(db)
    return {"ok": True, "deleted": int(deleted)}


@router.post("/cases/auto", response_model=AutoBuildOut)
def auto_build(
    payload: AutoBuildIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    created, skipped, total = retrieval_eval.auto_build_cases(
        db, current_user.id, payload.count, use_llm=payload.use_llm
    )
    if created == 0 and total == 0:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "知识库里还没有可用的知识块（或块都太短），请先录入并处理资料",
        )
    return AutoBuildOut(created=created, skipped=skipped, total_cases=total)


@router.post("/cases/builtin", response_model=AutoBuildOut)
def load_builtin_cases(
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    """幂等载入内置评测用例（开箱即用）。新用户注册时已自动载入；
    已清空用例或老用户可手动补齐。返回 (created/skipped/total)。"""
    from ..services.builtin import load_builtin_eval_cases

    stat = load_builtin_eval_cases(db, current_user.id)
    total = (
        db.query(RetrievalEvalCase)
        .filter(RetrievalEvalCase.user_id == current_user.id)
        .count()
    )
    return AutoBuildOut(
        created=stat["created"], skipped=stat["skipped"], total_cases=int(total)
    )


@router.post("/run", response_model=EvalRunOut)
def run_eval(
    payload: EvalRunIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    cases = (
        db.query(RetrievalEvalCase)
        .filter(RetrievalEvalCase.user_id == current_user.id)
        .order_by(RetrievalEvalCase.id)
        .all()
    )
    if not cases:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "评测集为空，请先生成或录入评测用例")

    summary, detail, elapsed_ms = retrieval_eval.run_evaluation(
        db,
        current_user.id,
        cases,
        top_k=payload.top_k,
        use_rewrite=payload.use_rewrite,
        include_llm_rewrite=payload.include_llm_rewrite,
        vector_weight=payload.vector_weight,
    )
    run = RetrievalEvalRun(
        user_id=current_user.id,
        case_count=len(cases),
        top_k=payload.top_k,
        use_rewrite=payload.use_rewrite,
        vector_weight=payload.vector_weight,
        summary_json=json.dumps(summary, ensure_ascii=False),
        detail_json=json.dumps(detail, ensure_ascii=False),
        elapsed_ms=elapsed_ms,
    )
    db.add(run)
    commit_with_retry(db)
    db.refresh(run)
    return EvalRunOut(
        id=run.id,
        case_count=run.case_count,
        top_k=run.top_k,
        use_rewrite=bool(run.use_rewrite),
        vector_weight=float(run.vector_weight or 1.0),
        elapsed_ms=run.elapsed_ms or 0,
        created_at=run.created_at,
        summary=summary,
        detail=detail,
    )


@router.get("/runs", response_model=list[EvalRunBrief])
def list_runs(
    limit: int = 10, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    runs = (
        db.query(RetrievalEvalRun)
        .filter(RetrievalEvalRun.user_id == current_user.id)
        .order_by(RetrievalEvalRun.id.desc())
        .limit(max(1, min(limit, 50)))
        .all()
    )
    return [_brief(r) for r in runs]


@router.get("/runs/{run_id}", response_model=EvalRunOut)
def get_run(
    run_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    run = db.get(RetrievalEvalRun, run_id)
    if run is None or run.user_id != current_user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "评测记录不存在")
    return EvalRunOut(
        id=run.id,
        case_count=run.case_count,
        top_k=run.top_k,
        use_rewrite=bool(run.use_rewrite),
        vector_weight=float(run.vector_weight or 1.0),
        elapsed_ms=run.elapsed_ms or 0,
        created_at=run.created_at,
        summary=run.summary,
        detail=run.detail,
    )
