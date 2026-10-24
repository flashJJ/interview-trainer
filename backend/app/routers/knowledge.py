"""知识库路由：录入 / 上传 / 列表 / 详情 / 重新处理 / 删除 / 语义检索 / 统计。"""

import os
import time

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..database import get_db
from ..dependencies import get_current_user
from ..models import KnowledgeEntry, KnowledgeChunk, Question, User
from ..schemas import (
    ChunkOut,
    KnowledgeDetailOut,
    KnowledgeEntryCreate,
    KnowledgeEntryOut,
    KnowledgeListOut,
    KnowledgeSearchIn,
    KnowledgeSearchOut,
    KnowledgeStatsOut,
    KnowledgeUrlIn,
    SearchHit,
)
from ..services import retrieval
from ..services.pipeline import process_entry
from ..services.runtime import get_vector_store

router = APIRouter(prefix="/knowledge", tags=["knowledge"])

_ALLOWED_EXTENSIONS = {".txt", ".md", ".pdf", ".docx"}
_MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10MB


def _derive_title(content: str) -> str:
    first_line = (content or "").strip().splitlines()[0] if content.strip() else ""
    title = first_line.strip()[:30] if first_line else ""
    return title or "未命名知识库"


def _extract_file_content(raw: bytes, ext: str) -> str:
    """按扩展名提取文件文本内容。"""
    if ext in (".txt", ".md"):
        return raw.decode("utf-8", errors="replace").strip()
    if ext == ".pdf":
        from ..services.importers import extract_pdf_text

        return extract_pdf_text(raw).strip()
    if ext == ".docx":
        from ..services.importers import extract_docx_text

        return extract_docx_text(raw).strip()
    raise ValueError(f"不支持的文件类型：{ext}")


def _create_and_process(db: Session, user: User, title: str, content: str, source_type: str) -> KnowledgeEntry:
    entry = KnowledgeEntry(
        user_id=user.id,
        title=title.strip() or _derive_title(content),
        source_type=source_type,
        content=content,
        status="processing",
        char_count=len(content),
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    process_entry(db, entry)
    db.refresh(entry)
    return entry


@router.post("/entries", response_model=KnowledgeEntryOut)
def create_entry(
    payload: KnowledgeEntryCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return _create_and_process(db, current_user, payload.title, payload.content, "text")


@router.post("/entries/upload", response_model=KnowledgeEntryOut)
async def upload_entry(
    file: UploadFile = File(...),
    title: str = Form(""),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in _ALLOWED_EXTENSIONS:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "仅支持 .txt / .md / .pdf / .docx 文件"
        )
    raw = await file.read()
    if len(raw) > _MAX_UPLOAD_BYTES:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "文件大小不能超过 10MB")
    try:
        content = _extract_file_content(raw, ext)
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    if len(content) < 30:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "文件内容太少（至少 30 字符）")
    file_title = title.strip() or os.path.splitext(file.filename or "未命名知识库")[0]
    return _create_and_process(db, current_user, file_title, content, "file")


@router.post("/entries/url", response_model=KnowledgeEntryOut)
def create_entry_from_url(
    payload: KnowledgeUrlIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """从网页链接录入：抓取页面并提取正文。"""
    from ..services.importers import fetch_url_text

    try:
        content = fetch_url_text(payload.url)
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    title = payload.title.strip() or _derive_title(content)
    return _create_and_process(db, current_user, title, content, "url")


@router.get("/entries", response_model=KnowledgeListOut)
def list_entries(
    page: int = 1,
    size: int = 10,
    status: str = "",
    keyword: str = "",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(KnowledgeEntry).filter(KnowledgeEntry.user_id == current_user.id)
    if status:
        query = query.filter(KnowledgeEntry.status == status)
    if keyword:
        query = query.filter(KnowledgeEntry.title.like(f"%{keyword}%"))
    total = query.count()
    items = (
        query.order_by(KnowledgeEntry.id.desc())
        .offset((page - 1) * size)
        .limit(size)
        .all()
    )
    # 题目计数实时校准（只统计已审核进入组卷池的题目）
    counts = dict(
        db.query(Question.entry_id, func.count(Question.id))
        .filter(
            Question.user_id == current_user.id,
            Question.status == "active",
            Question.review_status == "approved",
        )
        .group_by(Question.entry_id)
        .all()
    )
    for entry in items:
        entry.question_count = counts.get(entry.id, 0)
    db.commit()
    return KnowledgeListOut(items=items, total=total, page=page, size=size)


@router.get("/entries/{entry_id}", response_model=KnowledgeDetailOut)
def entry_detail(
    entry_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    entry = db.get(KnowledgeEntry, entry_id)
    if entry is None or entry.user_id != current_user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "知识条目不存在")
    chunks = (
        db.query(KnowledgeChunk)
        .filter(KnowledgeChunk.entry_id == entry.id)
        .order_by(KnowledgeChunk.seq)
        .all()
    )
    return KnowledgeDetailOut(entry=entry, chunks=chunks)


@router.post("/entries/{entry_id}/reprocess", response_model=KnowledgeEntryOut)
def reprocess_entry(
    entry_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    entry = db.get(KnowledgeEntry, entry_id)
    if entry is None or entry.user_id != current_user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "知识条目不存在")
    process_entry(db, entry)
    db.refresh(entry)
    return entry


@router.delete("/entries/{entry_id}")
def delete_entry(
    entry_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from ..models import ExamPaperQuestion

    entry = db.get(KnowledgeEntry, entry_id)
    if entry is None or entry.user_id != current_user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "知识条目不存在")
    referenced = (
        db.query(func.count(ExamPaperQuestion.id))
        .join(Question, Question.id == ExamPaperQuestion.question_id)
        .filter(Question.entry_id == entry.id)
        .scalar()
        or 0
    )
    if referenced:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"该资料下的 {referenced} 道题目已被考卷引用，暂不支持删除（请先删除相关考卷）",
        )
    store = get_vector_store()
    store.delete_entry_vectors(entry.id)
    store.delete_entry_question_vectors(entry.id)
    db.delete(entry)
    db.commit()
    return {"ok": True, "message": "已删除知识条目及其题目"}


@router.post("/search", response_model=KnowledgeSearchOut)
def search_knowledge(
    payload: KnowledgeSearchIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """知识库检索：默认混合检索（向量 + BM25 + RRF 融合）。

    mode 可切 vector / bm25 / hybrid —— 前两者主要用于在评测页对比效果，
    界面上也可以让用户直观看到"纯语义"与"纯关键词"的差异。
    """
    started = time.perf_counter()
    hits = retrieval.retrieve(
        db,
        current_user.id,
        payload.query,
        top_k=payload.top_k,
        mode=payload.mode,
        use_rewrite=payload.use_rewrite,
    )
    titles = dict(
        db.query(KnowledgeEntry.id, KnowledgeEntry.title)
        .filter(KnowledgeEntry.user_id == current_user.id)
        .all()
    )
    results = [
        SearchHit(
            chunk_id=hit.chunk_id,
            entry_id=hit.entry_id or 0,
            entry_title=titles.get(hit.entry_id, ""),
            seq=hit.seq,
            content=hit.content,
            score=round(hit.score, 6),
            vector_score=round(hit.vector_score, 4),
            bm25_score=round(hit.bm25_score, 4),
            channels=hit.channels,
        )
        for hit in hits
    ]
    return KnowledgeSearchOut(
        results=results,
        mode=payload.mode if payload.mode in retrieval.MODES else retrieval.MODE_HYBRID,
        used_rewrite=payload.use_rewrite,
        elapsed_ms=int((time.perf_counter() - started) * 1000),
    )


@router.get("/stats/overview", response_model=KnowledgeStatsOut)
def knowledge_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    entries = (
        db.query(KnowledgeEntry)
        .filter(KnowledgeEntry.user_id == current_user.id)
        .all()
    )
    entry_ids = [e.id for e in entries]
    chunk_count = 0
    vector_count = 0
    if entry_ids:
        chunk_count = (
            db.query(func.count(KnowledgeChunk.id))
            .filter(KnowledgeChunk.entry_id.in_(entry_ids))
            .scalar()
            or 0
        )
        vector_count = (
            db.query(func.count(KnowledgeChunk.id))
            .filter(
                KnowledgeChunk.entry_id.in_(entry_ids),
                KnowledgeChunk.vector_id != "",
            )
            .scalar()
            or 0
        )
    return KnowledgeStatsOut(
        entry_count=len(entries),
        ready_count=sum(1 for e in entries if e.status == "ready"),
        processing_count=sum(1 for e in entries if e.status in ("pending", "processing")),
        chunk_count=chunk_count,
        vector_count=vector_count,
    )
