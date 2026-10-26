"""内置内容（知识库语料 + 精选题库）的幂等载入。

设计要点：
1. **幂等**：知识库按标题去重，题库按「题干 + 条目」去重；重复执行只补缺失部分。
2. **自动过审**：内置题默认 approved，直接进组卷池——开箱即用不该先过一遍审核流。
3. **来源标记**：`source="builtin"` / `source_type="builtin"`，与 LLM 生成、规则生成区分，
   让用户在题库里一眼看出哪些是随系统自带的、哪些是自己生成的。
4. **关联条目**：题目通过条目标题关联到知识库，这样掌握度可以按「资料」维度聚合，
   检索评测也能拿到对应的知识块。
"""

from __future__ import annotations

import json
import logging
import os
import sys
import threading
import time
from typing import Callable

logger = logging.getLogger(__name__)

# 后台载入的节流参数：每写这么多条就提交一次，并在批次之间让出写锁。
# 目的是避免长时间独占 SQLite 写锁，导致同一用户的同时段操作被阻塞。
_COMMIT_BATCH = 20
_LOAD_PACE_SEC = 0.05

from ..database import commit_with_retry
from ..models import KnowledgeChunk, KnowledgeEntry, Question, RetrievalEvalCase
from .pipeline import process_entry
from .runtime import get_embeddings, get_vector_store

# 内置语料放在 backend/data/builtin/，不跟随启动目录变化，这里显式补进 sys.path
_BACKEND_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _BACKEND_ROOT not in sys.path:
    sys.path.insert(0, _BACKEND_ROOT)


def _load_entry_specs() -> list[dict]:
    from data.builtin import knowledge

    return list(knowledge.BUILTIN_ENTRIES)


def _load_question_specs() -> list[dict]:
    """按技术域分文件存放的题库，汇总成一个列表。"""
    from data.builtin import (
        questions_ai,
        questions_basic,
        questions_db,
        questions_distributed,
        questions_frontend,
        questions_java,
        questions_ops,
        questions_python,
    )

    specs: list[dict] = []
    for module in (
        questions_java,
        questions_python,
        questions_db,
        questions_distributed,
        questions_ai,
        questions_frontend,
        questions_basic,
        questions_ops,
    ):
        specs.extend(getattr(module, "QUESTIONS", []))
    return specs


def load_builtin_knowledge(
    db, user_id: int, log: Callable[[str], None] = print
) -> dict:
    """载入内置知识库语料（分块 + 关键词 + 向量化），返回统计。"""
    created = skipped = 0
    for spec in _load_entry_specs():
        title = spec["title"]
        existing = (
            db.query(KnowledgeEntry)
            .filter(KnowledgeEntry.user_id == user_id, KnowledgeEntry.title == title)
            .first()
        )
        if existing is not None:
            skipped += 1
            continue
        entry = KnowledgeEntry(
            user_id=user_id,
            title=title,
            source_type="builtin",
            content=spec["content"],
            status="processing",
            char_count=len(spec["content"]),
        )
        db.add(entry)
        commit_with_retry(db)
        db.refresh(entry)
        process_entry(db, entry)
        db.refresh(entry)
        created += 1
        log(f"[builtin] 知识库「{title}」：{entry.chunk_count} 块，状态 {entry.status}")
    return {"created": created, "skipped": skipped}


def load_builtin_questions(
    db, user_id: int, log: Callable[[str], None] = print
) -> dict:
    """载入内置题库。题目按「条目标题」关联到知识库，找不到条目时留空。"""
    # 建立 条目标题 -> id 映射（含用户自己录入与系统内置的条目）
    entry_map = {
        row[0]: row[1]
        for row in db.query(KnowledgeEntry.title, KnowledgeEntry.id)
        .filter(KnowledgeEntry.user_id == user_id)
        .all()
    }
    embeddings = get_embeddings()
    store = get_vector_store()

    created = skipped = orphan = 0
    pending = 0  # 未提交的写入数，用于分批提交
    for spec in _load_question_specs():
        entry_id = entry_map.get(spec.get("entry", ""))
        if entry_id is None and spec.get("entry"):
            orphan += 1
        dup = (
            db.query(Question)
            .filter(
                Question.user_id == user_id,
                Question.content == spec["content"],
                Question.entry_id == entry_id,
            )
            .first()
        )
        if dup is not None:
            skipped += 1
            continue

        options = spec.get("options") or []
        question = Question(
            user_id=user_id,
            entry_id=entry_id,
            q_type=spec["q_type"],
            content=spec["content"],
            options_json=json.dumps(options, ensure_ascii=False),
            answer=spec["answer"],
            explanation=spec["explanation"],
            difficulty=spec.get("difficulty", "medium"),
            keywords_json=json.dumps(spec.get("keywords", []), ensure_ascii=False),
            source="builtin",
            review_status="approved",  # 内置题直接进组卷池
        )
        db.add(question)
        db.flush()
        vector_id = f"question_{question.id}"
        store.upsert_question(
            vector_id=vector_id,
            question_id=question.id,
            user_id=user_id,
            entry_id=entry_id,
            q_type=spec["q_type"],
            content=spec["content"],
            embedding=embeddings.embed(spec["content"]),
        )
        question.vector_id = vector_id
        created += 1
        pending += 1

        # 分批提交：后台载入与用户的正常操作会并发写同一个 SQLite 文件，
        # 一次攒几百条再提交会长时间占用写锁，让同用户其它请求直接 500。
        if pending >= _COMMIT_BATCH:
            commit_with_retry(db)
            pending = 0
            if _LOAD_PACE_SEC > 0:
                time.sleep(_LOAD_PACE_SEC)

    if pending:
        commit_with_retry(db)
    return {"created": created, "skipped": skipped, "orphan": orphan}


def load_builtin(db, user_id: int, log: Callable[[str], None] = print) -> dict:
    """按顺序载入内置知识库与题库（题库必须后于知识库，才能关联到条目）。"""
    knowledge_stat = load_builtin_knowledge(db, user_id, log)
    question_stat = load_builtin_questions(db, user_id, log)
    eval_stat = load_builtin_eval_cases(db, user_id, log)
    return {"knowledge": knowledge_stat, "questions": question_stat, "eval_cases": eval_stat}


def load_builtin_eval_cases(
    db, user_id: int, log: Callable[[str], None] = print
) -> dict:
    """载入内置检索评测用例（query → 条目知识块），返回统计。

    用例按 (user_id, query) 幂等去重；条目标题解析到该用户内置条目的全部知识块 id，
    作为评测的 expected_ids。条目找不到或没有知识块时跳过并记日志（正常不触发，
    因为 19 篇内置语料在 load_builtin_knowledge 阶段已分块）。
    """
    from data.builtin import eval_cases

    specs = list(eval_cases.BUILTIN_EVAL_CASES)
    # 标题 -> entry_id，以及 entry_id -> 该条目全部知识块 id
    entry_rows = (
        db.query(KnowledgeEntry.id, KnowledgeEntry.title)
        .filter(KnowledgeEntry.user_id == user_id)
        .all()
    )
    title_to_entry = {title: eid for eid, title in entry_rows}
    chunk_rows = (
        db.query(KnowledgeChunk.entry_id, KnowledgeChunk.id)
        .filter(KnowledgeChunk.entry_id.in_(list(title_to_entry.values())))
        .all()
    )
    chunks_by_entry: dict[int, list[int]] = {}
    for eid, cid in chunk_rows:
        chunks_by_entry.setdefault(int(eid), []).append(int(cid))

    created = skipped = orphan = 0
    for spec in specs:
        title = spec["entry"]
        eid = title_to_entry.get(title)
        if eid is None:
            orphan += 1
            log(f"[builtin-eval] 找不到条目「{title}」，跳过")
            continue
        chunk_ids = chunks_by_entry.get(int(eid), [])
        if not chunk_ids:
            orphan += 1
            log(f"[builtin-eval] 条目「{title}」尚未分块，跳过")
            continue
        query_text = spec["query"].strip()
        dup = (
            db.query(RetrievalEvalCase)
            .filter(RetrievalEvalCase.user_id == user_id, RetrievalEvalCase.query == query_text)
            .first()
        )
        if dup is not None:
            skipped += 1
            continue
        db.add(
            RetrievalEvalCase(
                user_id=user_id,
                query=query_text,
                expected_ids_json=json.dumps(chunk_ids, ensure_ascii=False),
                source="builtin",
                origin_chunk_id=0,
                note="内置预置",
            )
        )
        created += 1
    if created:
        commit_with_retry(db)
    return {"created": created, "skipped": skipped, "orphan": orphan}


def load_builtin_async(user_id: int) -> threading.Thread:
    """后台线程补齐某用户的内置内容，返回已启动的线程。

    注册流程不能阻塞：上百道题的向量化在开启远端 Embedding 时可能耗时数十秒，
    因此放到后台执行。载入是幂等的，失败也只记日志，不影响注册本身成功。
    """
    from ..database import SessionLocal

    def _run() -> None:
        db = SessionLocal()
        try:
            stat = load_builtin(db, user_id, log=lambda msg: logger.info(msg))
            logger.info("[builtin] 用户 %s 内置内容载入完成：%s", user_id, stat)
        except Exception as exc:  # noqa: BLE001 - 后台任务失败不应影响主流程
            logger.warning("[builtin] 用户 %s 内置内容载入失败：%s", user_id, exc)
        finally:
            db.close()

    thread = threading.Thread(target=_run, name=f"builtin-{user_id}", daemon=True)
    thread.start()
    return thread
