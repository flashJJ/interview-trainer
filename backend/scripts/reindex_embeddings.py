"""向量重建：切换 Embedding 提供方（维度可能变化）后，重建集合并全量重算。

背景：ChromaDB 的 collection 维度由**首次写入**决定。把内置哈希向量（384 维）
换成真实模型（如 qwen3-embedding 1024 维 / bge-m3 1024 维）后，直接写入会报
「Dimensionality of (1024) does not match collection dimensionality (384)」。

用法：
    python scripts/reindex_embeddings.py --dry-run   # 只体检：当前维度、目标维度、待处理数量
    python scripts/reindex_embeddings.py --reset     # 维度变化时：删集合 → 重算知识块与题目向量
    python scripts/reindex_embeddings.py             # 维度一致时：原地重算（upsert 覆盖）

设计要点：**只重算向量，不重新分块**。
- 重新分块会删掉旧 chunk 行、生成新主键，而检索评测用例的 expected_ids 记的是旧主键；
  一旦重分块，所有评测指标的 Recall 会直接掉成 0（连 BM25 也是 0）。
- 因此这里对现有 KnowledgeChunk / Question 逐条重算并 upsert，主键与用例都不动。

跑完请**重启后端服务**：进程内缓存的 collection 句柄在集合被删除后已失效。
"""

from __future__ import annotations

import argparse
import pathlib
import sys
import time

# 允许直接 `python scripts/reindex_embeddings.py` 运行（把 backend/ 加进 sys.path）
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from app.database import SessionLocal, init_db  # noqa: E402
from app.models import KnowledgeChunk, Question  # noqa: E402
from app.services.runtime import get_embeddings, get_vector_store  # noqa: E402

BATCH = 32


def main() -> int:
    parser = argparse.ArgumentParser(description="重建知识块与题目的向量")
    parser.add_argument("--reset", action="store_true", help="删除并重建集合（维度变化时必须）")
    parser.add_argument("--dry-run", action="store_true", help="只体检，不改数据")
    args = parser.parse_args()

    init_db()
    emb = get_embeddings()
    store = get_vector_store()

    target_dim = len(emb.embed("维度探针"))
    stored = store.stored_dims()
    print(f"[mode] {emb.mode} | 目标维度 {target_dim} | 存储维度 {stored}")

    mismatch = any(dim is not None and dim != target_dim for dim in stored.values())
    if mismatch and not args.reset:
        print("[abort] 存储维度与目标维度不一致：请加 --reset 重建集合后再写入")
        return 2

    db = SessionLocal()
    try:
        chunks = db.query(KnowledgeChunk).order_by(KnowledgeChunk.id).all()
        questions = db.query(Question).order_by(Question.id).all()
        if args.dry_run:
            print(f"[plan] 知识块 {len(chunks)} 个、题目 {len(questions)} 道"
                  f"{'（需要 --reset）' if mismatch else '（可直接原地重算）'}")
            return 0

        started = time.time()
        if args.reset:
            store.reset_collections()
            print("[reset] 已删除并重建 kb_chunks / questions 集合")

        # 知识块：原地重算，保留 chunk 主键（评测用例的 expected_ids 依赖它）
        for start in range(0, len(chunks), BATCH):
            batch = chunks[start:start + BATCH]
            vectors = emb.embed_batch([c.content for c in batch])
            for c, vec in zip(batch, vectors):
                vector_id = f"chunk_{c.id}"
                store.upsert_chunk(
                    vector_id=vector_id,
                    entry_id=c.entry_id,
                    seq=c.seq,
                    content=c.content,
                    embedding=vec,
                )
                c.vector_id = vector_id
            db.commit()
            print(f"  [chunk {min(start + BATCH, len(chunks))}/{len(chunks)}]")

        # 题目向量：去重依赖它，必须逐条重算（批量提交，避免长时间占用 SQLite 写锁）
        for start in range(0, len(questions), BATCH):
            batch = questions[start:start + BATCH]
            vectors = emb.embed_batch([q.content for q in batch])
            for q, vec in zip(batch, vectors):
                vector_id = f"question_{q.id}"
                store.upsert_question(
                    vector_id=vector_id,
                    question_id=q.id,
                    user_id=q.user_id,
                    entry_id=q.entry_id,
                    q_type=q.q_type,
                    content=q.content,
                    embedding=vec,
                )
                q.vector_id = vector_id
            db.commit()
            print(f"  [question {min(start + BATCH, len(questions))}/{len(questions)}]")

        counts = store.counts()
        print(f"[done] 耗时 {time.time() - started:.1f}s | 集合计数 {counts}")
        print("[next] 请重启后端服务（进程内 collection 句柄已失效），再跑检索评测对比指标")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
